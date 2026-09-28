"""Unified Claude client with provider routing.

Two providers, one interface:
  - "anthropic": direct Anthropic API (sk-ant- key) via the anthropic SDK
  - "bedrock":   AWS Bedrock InvokeModel API with an API key (bearer token),
                  no boto3/AWS SDK required — plain HTTPS via httpx.

Both speak the same Anthropic Messages payload shape, so prompts, JSON
extraction, vision, and usage tracking work identically.
"""
import asyncio
import base64
import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AIError

logger = logging.getLogger("app.ai")

_anthropic_client = None

# Shared keep-alive HTTP session for Bedrock (saves TLS handshake per call)
_http: httpx.Client | None = None


def _get_http() -> httpx.Client:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.Client(timeout=120)
    return _http


BEDROCK_INVOKE_URL = "https://bedrock-runtime.{region}.amazonaws.com/model/{model_id}/invoke"

# Fast model for high-frequency control tasks (routing, quick judgments).
# Falls back to the primary model when unavailable.
FAST_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic

        if not settings.ANTHROPIC_API_KEY or settings.ANTHROPIC_API_KEY.startswith("sk-ant-your"):
            raise AIError("ANTHROPIC_API_KEY is not configured")
        _anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def _bedrock_api_key() -> str | None:
    key = (settings.BEDROCK_API_KEY or "").strip()
    if not key or key.startswith("your-"):
        return None
    return key


def bedrock_enabled() -> bool:
    if _bedrock_api_key():
        return True
    return False


def ai_configured() -> bool:
    """True when any provider has a usable key."""
    if bedrock_enabled():
        return True
    return bool(settings.ANTHROPIC_API_KEY) and not settings.ANTHROPIC_API_KEY.startswith("sk-ant-your")


def _bedrock_invoke(
    system: str,
    messages: list[dict],
    max_tokens: int,
    temperature: float,
    model_id: str | None = None,
) -> dict:
    """Call Bedrock InvokeModel with the Anthropic Messages schema."""
    key = _bedrock_api_key()
    if not key:
        raise AIError("BEDROCK_API_KEY is not configured")

    # Model IDs are URL-path-safe in Bedrock (they contain ':' and '.')
    model_id = model_id or settings.BEDROCK_MODEL_ID
    url = BEDROCK_INVOKE_URL.format(region=settings.BEDROCK_REGION, model_id=model_id)

    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
    }
    # Newer Claude models on Bedrock reject the deprecated temperature param.
    _model_lower = model_id.lower()
    if not any(
        tag in _model_lower
        for tag in (
            "claude-sonnet-5",
            "claude-opus-4-6",
            "claude-opus-5",
            "claude-opus-4-7",
            "claude-opus-4-8",
            "claude-fable",
            "haiku-4-5",
        )
    ):
        body["temperature"] = temperature

    try:
        resp = _get_http().post(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=body,
            timeout=120,
        )
    except httpx.HTTPError as e:
        raise AIError(f"Bedrock request failed: {e}") from e

    if resp.status_code == 403:
        raise AIError("Bedrock rejected the API key (403). Check BEDROCK_API_KEY and model access.")
    if resp.status_code == 404:
        raise AIError(f"Bedrock model not found: {model_id}. Check BEDROCK_MODEL_ID for region {settings.BEDROCK_REGION}.")
    if resp.status_code == 429:
        raise AIError("Bedrock throttled the request (429). Retry shortly.")
    if resp.status_code >= 400:
        raise AIError(f"Bedrock error {resp.status_code}: {resp.text[:300]}")

    try:
        return resp.json()
    except json.JSONDecodeError as e:
        raise AIError("Bedrock returned non-JSON response") from e


def _bedrock_image_block(image_b64: str, media_type: str) -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
    }


def _repair_truncated_json(fragment: str) -> str | None:
    """Salvage a JSON object cut off by the token limit.

    Strategy: walk backwards over structural cut points (outside strings,
    not dangling on `,`/`:`), close the still-open brackets, and accept the
    first prefix that parses as a dict. Bounded scan keeps it cheap.
    """
    if not fragment.startswith(("{", "[")):
        return None
    closers = {"{": "}", "[": "]"}
    n = len(fragment)
    candidates: list[str] = []
    for cut in range(n, max(0, n - 500), -1):
        prefix = fragment[:cut].rstrip()
        if not prefix or prefix[-1] in ",:":
            continue  # dangling separator or half-written key/value
        if prefix.count('"') % 2 == 1:
            continue  # cut inside a string literal
        candidates.append(prefix)
        if len(candidates) >= 80:
            break
    for prefix in candidates:
        stack: list[str] = []
        in_string = False
        escape = False
        for ch in prefix:
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch in "{[":
                stack.append(ch)
            elif ch in "}]" and stack:
                stack.pop()
        if in_string or stack and stack[-1] not in closers:
            continue
        candidate = prefix + "".join(closers[c] for c in reversed(stack))
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return candidate
        except json.JSONDecodeError:
            continue
    return None


def extract_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output (handles ```json fences
    and repairs responses cut off by the token limit)."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    if start == -1:
        raise AIError("AI response did not contain JSON")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError as e:
                    raise AIError("AI returned malformed JSON") from e
    # Unbalanced -> the model hit max_tokens mid-JSON. Attempt repair.
    repaired = _repair_truncated_json(text[start:])
    if repaired:
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                logger.warning("Repaired truncated JSON from model output")
                return data
        except json.JSONDecodeError:
            pass
    # Balanced but malformed (e.g. trailing commas) -> strip and retry once.
    import re as _re

    cleaned = _re.sub(r",(\s*[}\]])", r"\1", text[start:])
    if cleaned != text[start:]:
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                logger.warning("Repaired malformed JSON (trailing commas) from model output")
                return data
        except json.JSONDecodeError:
            pass
    raise AIError("AI response JSON was truncated")


class ClaudeClient:
    """Provider-agnostic Claude client with logging + token capture."""

    def __init__(self):
        self.model = settings.BEDROCK_MODEL_ID if bedrock_enabled() else settings.ANTHROPIC_MODEL
        self.last_usage: dict = {}

    def _track(self, usage: dict | Any) -> None:
        if isinstance(usage, dict):
            self.last_usage = {
                "prompt_tokens": usage.get("input_tokens", 0) or 0,
                "completion_tokens": usage.get("output_tokens", 0) or 0,
            }
        else:
            self.last_usage = {
                "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
            }

    def _extract_text(self, response: dict | Any) -> str:
        """Extract text from either Bedrock dict or Anthropic SDK response."""
        if isinstance(response, dict):
            content = response.get("content", [])
            return "".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        return "".join(
            b.text for b in getattr(response, "content", []) if getattr(b, "type", "") == "text"
        )

    def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int | None = None,
        temperature: float | None = None,
        model_id: str | None = None,
    ) -> str:
        max_toks = max_tokens or settings.AI_MAX_TOKENS
        temp = settings.AI_TEMPERATURE if temperature is None else temperature

        if bedrock_enabled():
            response = _bedrock_invoke(system, messages, max_toks, temp, model_id)
            self._track(response.get("usage", {}))
        else:
            response = _get_anthropic_client().messages.create(
                model=self.model,
                system=system,
                messages=messages,
                max_tokens=max_toks,
                temperature=temp,
            )
            self._track(response.usage)

        text = self._extract_text(response)
        if not text:
            raise AIError("AI returned an empty response")
        return text

    def complete_stream(self, system: str, messages: list[dict], **kwargs):
        """Yield text deltas from the primary provider.

        Direct Anthropic path uses the SDK's streaming context manager.
        Bedrock path falls back to a single chunk (Bedrock streaming needs a
        different invoke-with-response-stream call; not wired here).
        Raises AIError on failure so callers can degrade gracefully.
        """
        if bedrock_enabled():
            text = self.complete(system, messages, **kwargs)  # one payload
            yield text
            return
        max_toks = kwargs.get("max_tokens") or settings.AI_MAX_TOKENS
        temp = settings.AI_TEMPERATURE if kwargs.get("temperature") is None else kwargs["temperature"]
        try:
            with _get_anthropic_client().messages.stream(
                model=kwargs.get("model_id") or self.model,
                system=system,
                messages=messages,
                max_tokens=max_toks,
                temperature=temp,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except AIError:
            raise
        except Exception as e:
            logger.warning("Streaming failed (%s); caller should fall back to complete()", e)
            raise AIError("AI streaming unavailable") from e

    def complete_json(self, system: str, messages: list[dict], **kwargs) -> dict[str, Any]:
        raw = self.complete(system, messages, **kwargs)
        return extract_json(raw)

    def complete_fast_json(self, system: str, messages: list[dict], **kwargs) -> dict[str, Any]:
        """Latency-critical routing: try the fast model, fall back to primary."""
        try:
            raw = self.complete(system, messages, model_id=FAST_MODEL_ID, **kwargs)
            return extract_json(raw)
        except AIError:
            logger.warning("Fast model unavailable; falling back to primary", exc_info=True)
            return self.complete_json(system, messages, **kwargs)

    # ---------- async wrappers ----------
    # The sync SDK/httpx calls above block the thread they run on. They must
    # never run on the event loop thread, or one slow AI call freezes every
    # concurrent request. These wrappers push the blocking call onto a worker
    # thread (FastAPI handlers can simply `await claude.acomplete_json(...)`).

    async def acomplete(self, system: str, messages: list[dict], **kwargs) -> str:
        return await asyncio.to_thread(self.complete, system, messages, **kwargs)

    async def acomplete_json(self, system: str, messages: list[dict], **kwargs) -> dict[str, Any]:
        raw = await self.acomplete(system, messages, **kwargs)
        return extract_json(raw)

    async def acomplete_fast_json(self, system: str, messages: list[dict], **kwargs) -> dict[str, Any]:
        """Latency-critical async routing: fast model first, primary as fallback."""
        try:
            raw = await self.acomplete(system, messages, model_id=FAST_MODEL_ID, **kwargs)
            return extract_json(raw)
        except AIError:
            logger.warning("Fast model unavailable; falling back to primary", exc_info=True)
            return await self.acomplete_json(system, messages, **kwargs)

    async def astream(self, system: str, messages: list[dict], **kwargs):
        """Async token streaming for the chat UI.

        Bedrock path returns one big text (no SSE wired), so it is split into
        word chunks with a tiny sleep — progressive rendering without blocking
        the loop. Anthropic path streams via the SDK inside a worker thread and
        forwards deltas over a queue, so the event loop stays free.
        """
        if bedrock_enabled():
            text = await self.acomplete(system, messages, **kwargs)
            buf = ""
            for word in text.split(" "):
                buf += word + " "
                if len(buf) >= 12:
                    yield buf
                    buf = ""
                    await asyncio.sleep(0.02)
            if buf:
                yield buf
            return

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        DONE = object()

        def _produce() -> None:
            try:
                for delta in self.complete_stream(system, messages, **kwargs):
                    loop.call_soon_threadsafe(queue.put_nowait, delta)
            except Exception as e:  # noqa: BLE001 — surfaced to the consumer below
                logger.warning("Streaming failed (%s)", e)
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, DONE)

        import threading

        threading.Thread(target=_produce, daemon=True).start()
        while True:
            item = await queue.get()
            if item is DONE:
                break
            if isinstance(item, Exception):
                raise AIError("AI streaming unavailable") from item
            yield item

    def vision_json(
        self,
        system: str,
        prompt: str,
        image_b64: str,
        media_type: str = "image/jpeg",
        **kwargs,
    ) -> dict[str, Any]:
        messages = [
            {
                "role": "user",
                "content": [
                    _bedrock_image_block(image_b64, media_type),
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        raw = self.complete(system, messages, **kwargs)
        return extract_json(raw)


def get_claude() -> ClaudeClient:
    if not ai_configured():
        raise AIError(
            "AI is not configured. Set BEDROCK_API_KEY (AWS Bedrock) or ANTHROPIC_API_KEY (direct)."
        )
    return ClaudeClient()
