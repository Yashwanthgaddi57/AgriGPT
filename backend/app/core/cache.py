"""Cache helpers: Redis when available, in-process dict fallback otherwise.

No Docker / no Redis -> automatically uses a process-local TTL dict so the
API stays fast and functional. Redis is transparently re-probed after
REDIS_RETRY_SECONDS when it comes back.
"""
import json
import time
from typing import Any

from app.core.config import settings

_client = None
_redis_dead_until = 0.0
REDIS_RETRY_SECONDS = 30.0

# Fallback store: key -> (expires_at_monotonic, value)
_memory_store: dict[str, tuple[float, str]] = {}


def _get_client():
    global _client, _redis_dead_until
    now = time.monotonic()
    if _client is not None:
        return _client
    if now < _redis_dead_until:
        return None
    try:
        import redis

        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=0.25,
            socket_timeout=0.25,
            decode_responses=True,
        )
        client.ping()
        _client = client
        return _client
    except Exception:
        _redis_dead_until = now + REDIS_RETRY_SECONDS
        return None


def _mem_get(key: str) -> Any | None:
    entry = _memory_store.get(key)
    if not entry:
        return None
    expires_at, raw = entry
    if expires_at < time.monotonic():
        _memory_store.pop(key, None)
        return None
    return json.loads(raw)


def cache_get(key: str) -> Any | None:
    client = _get_client()
    if client is not None:
        try:
            raw = client.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            pass
    return _mem_get(key)


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    payload = json.dumps(value, default=str)
    client = _get_client()
    if client is not None:
        try:
            client.setex(key, ttl_seconds, payload)
            return
        except Exception:
            pass
    _memory_store[key] = (time.monotonic() + ttl_seconds, payload)
    # Opportunistic cleanup
    if len(_memory_store) > 512:
        now = time.monotonic()
        for k in [k for k, (exp, _) in _memory_store.items() if exp < now][:256]:
            _memory_store.pop(k, None)


def cache_delete_prefix(prefix: str) -> None:
    client = _get_client()
    if client is not None:
        try:
            for key in client.scan_iter(match=f"{prefix}*"):
                client.delete(key)
        except Exception:
            pass
    for key in [k for k in _memory_store if k.startswith(prefix)]:
        _memory_store.pop(key, None)
