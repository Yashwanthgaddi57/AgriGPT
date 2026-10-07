"""LangGraph multi-agent architecture.

Agents:
  1. Crop Recommendation Agent
  2. Disease Detection Agent (text mode; vision handled by disease service)
  3. Weather Agent
  4. Market Forecast Agent
  5. Profit Optimization Agent
  6. Agriculture Advisor Agent
  + Coordinator Agent: routes user requests and merges specialist responses.

Graph flow:
  START -> coordinator -> (conditional) -> specialist -> merge -> END
  coordinator -> (direct answer) -> END
"""
import logging
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.ai.claude_client import get_claude
from app.ai.prompts import (
    ADVISOR_SYSTEM,
    CHAT_RESPONSE_RULES,
    COORDINATOR_SYSTEM,
    CROP_RECOMMENDATION_SYSTEM,
    MARKET_FORECAST_SYSTEM,
    NEARBY_SERVICES_SYSTEM,
    PROFIT_OPTIMIZATION_SYSTEM,
    WEATHER_AGENT_SYSTEM,
)
from app.services.weather_service import get_weather_summary_for_agent

logger = logging.getLogger("app.ai.agents")

INTENT_TO_AGENT = {
    "crop_recommendation": "crop",
    "disease_detection": "disease",
    "weather": "weather",
    "market": "market",
    "profit_optimization": "profit",
    "nearby_services": "nearby",
    "general_advice": "advisor",
}


# ----------------------------------------------------------------------
# Shared graph state
# ----------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    user_id: str
    farmer_context: str
    intent: str
    entities: dict
    language: str
    specialist_outputs: dict
    final_response: str
    needs_specialist: bool
    direct_answer: str


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # Anthropic-style content blocks
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def _last_user_text(state: AgentState) -> str:
    msgs = state.get("messages") or []
    for m in reversed(msgs):
        role = m.get("role", "user") if isinstance(m, dict) else getattr(m, "type", "user")
        if role in ("user", "human"):
            return _to_text(m.get("content") if isinstance(m, dict) else getattr(m, "content", ""))
    return ""


def _recent_history(state: AgentState, n: int = 8) -> list[dict]:
    msgs = state.get("messages") or []
    out: list[dict] = []
    for m in msgs[-n:]:
        if isinstance(m, dict):
            role, content = m.get("role", "user"), m.get("content", "")
        else:
            role, content = getattr(m, "type", "user"), getattr(m, "content", "")
        role = "assistant" if role in ("assistant", "ai") else "user"
        out.append({"role": role, "content": _to_text(content)})
    return out or [{"role": "user", "content": _last_user_text(state) or "Hello"}]


# ----------------------------------------------------------------------
# Nodes
# ----------------------------------------------------------------------
def coordinator_node(state: AgentState) -> dict:
    """Classify intent, extract entities, optionally answer directly."""
    claude = get_claude()
    user_text = _last_user_text(state)
    context_block = f"FARMER CONTEXT:\n{state.get('farmer_context', 'none')}\n\nMESSAGE:\n{user_text}"
    try:
        result = claude.complete_fast_json(
            system=COORDINATOR_SYSTEM,
            messages=[{"role": "user", "content": context_block}],
            max_tokens=400,
        )
    except Exception as e:  # fail open to advisor
        logger.warning("Coordinator fallback to advisor: %s", e)
        return {
            "intent": "general_advice",
            "entities": {},
            "language": "en",
            "needs_specialist": True,
            "direct_answer": "",
        }

    needs = bool(result.get("needs_specialist", True))
    update: dict[str, Any] = {
        "intent": result.get("intent", "general_advice"),
        "entities": result.get("entities") or {},
        "language": result.get("language", "en"),
        "needs_specialist": needs,
        "direct_answer": "" if needs else result.get("direct_answer", ""),
    }
    if not needs and update["direct_answer"]:
        update["final_response"] = update["direct_answer"]
    return update


def route_by_intent(state: AgentState) -> str:
    if not state.get("needs_specialist", True):
        return "done"
    return INTENT_TO_AGENT.get(state.get("intent", "general_advice"), "advisor")


def crop_node(state: AgentState) -> dict:
    claude = get_claude()
    answer = claude.complete(
        system=CROP_RECOMMENDATION_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nThis is a chat context: present the analysis as friendly prose with the numeric "
          "rigor (investment, revenue, profit, risk, confidence) woven into sentences or a table.",
        messages=[
            {"role": "user", "content": f"FARMER CONTEXT:\n{state.get('farmer_context', 'none')}"},
            *_recent_history(state),
            {"role": "user", "content": _last_user_text(state)},
        ],
        max_tokens=1400,
    )
    return {"specialist_outputs": {"crop_recommendation": answer}}


def disease_node(state: AgentState) -> dict:
    claude = get_claude()
    answer = claude.complete(
        system=(
            "You are a plant pathologist helping via chat (no image provided). Ask targeted "
            "diagnostic questions (which crop, what symptoms, since when, spread pattern, weather) "
            "and give the most likely causes plus immediate containment steps. Keep it practical "
            "for Indian farming conditions."
        ),
        messages=_recent_history(state),
        max_tokens=1000,
    )
    return {"specialist_outputs": {"disease_detection": answer}}


def weather_node(state: AgentState) -> dict:
    claude = get_claude()
    user_text = _last_user_text(state)
    entities = state.get("entities") or {}
    location = entities.get("location") or ""
    summary = get_weather_summary_for_agent(state.get("user_id", ""), location)
    answer = claude.complete(
        system=WEATHER_AGENT_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nYou are in CHAT mode: the JSON schema above is for internal reference only. "
          "Answer in friendly prose using the forecast numbers.",
        messages=[
            {
                "role": "user",
                "content": (
                    f"FARMER CONTEXT:\n{state.get('farmer_context', 'none')}\n\n"
                    f"7-DAY FORECAST DATA (Open-Meteo):\n{summary}\n\n"
                    f"FARMER QUESTION: {user_text}"
                ),
            }
        ],
        max_tokens=900,
    )
    return {"specialist_outputs": {"weather": answer}}


def market_node(state: AgentState) -> dict:
    claude = get_claude()
    user_text = _last_user_text(state)
    crop = (state.get("entities") or {}).get("crop") or "the crop in question"
    answer = claude.complete(
        system=MARKET_FORECAST_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nYou are in CHAT mode: the JSON schema above is for internal reference only. "
          "Answer in friendly prose with the trend/forecast numbers included.",
        messages=[
            {
                "role": "user",
                "content": (
                    f"FARMER CONTEXT:\n{state.get('farmer_context', 'none')}\n\n"
                    f"Note: live mandi feed is unavailable in this chat; use typical seasonal "
                    f"price ranges for the crop. Crop in focus: {crop}.\n\n"
                    f"FARMER QUESTION: {user_text}"
                ),
            }
        ],
        max_tokens=900,
    )
    return {"specialist_outputs": {"market": answer}}


def profit_node(state: AgentState) -> dict:
    claude = get_claude()
    user_text = _last_user_text(state)
    answer = claude.complete(
        system=PROFIT_OPTIMIZATION_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nYou are in CHAT mode: the JSON schema above is for internal reference only. "
          "If cost details are missing, state assumptions briefly, then present the projection "
          "as prose/tables — never as JSON.",
        messages=[
            {"role": "user", "content": f"FARMER CONTEXT:\n{state.get('farmer_context', 'none')}"},
            {"role": "user", "content": f"QUESTION: {user_text}"},
        ],
        max_tokens=1200,
    )
    return {"specialist_outputs": {"profit_optimization": answer}}


async def _nearby_results_text(user_id: str, entities: dict, query: str) -> str:
    """Real nearby-service results for the assistant — never hallucinated.

    Returns a compact block the model must quote from: name, category, true
    distance, address and only those contact fields the data actually has.
    """
    from app.core.database import get_session_factory
    from app.models.user import User
    from app.services.agri_services import (
        CATEGORY_LABELS,
        categories_from_search,
        nearby_agri_services,
    )
    from app.services.location_service import resolve_location

    db = get_session_factory()()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return "NO PROFILE: cannot resolve the farmer's location."
        loc = resolve_location(db, user)

        cats = categories_from_search(query)
        if not cats and entities.get("category"):
            cats = categories_from_search(str(entities["category"]))

        radius_km = 25
        results = await nearby_agri_services(
            db,
            loc.latitude,
            loc.longitude,
            radius_km=radius_km,
            categories=cats,
            search=entities.get("search") or None,
            limit=8,
        )
        if not results:
            return (
                f"NO RESULTS within {radius_km} km of {loc.label}. "
                "Tell the farmer nothing was found and suggest a larger radius or a nearby town."
            )

        lines = [f"SEARCHED AROUND: {loc.label} ({radius_km} km radius). REAL RESULTS:"]
        for i, r in enumerate(results, 1):
            parts = [
                f"{i}. {r['name']} [{CATEGORY_LABELS.get(r['category'], r['category'])}]",
                f"{r['distance_km']} km away",
            ]
            address = ", ".join(
                filter(None, [r.get("address"), r.get("city"), r.get("district"), r.get("state")])
            )
            if address:
                parts.append(address)
            if r.get("phone"):
                parts.append(f"phone {r['phone']}")
            if r.get("website"):
                parts.append(f"website {r['website']}")
            if r.get("opening_hours"):
                parts.append(f"open {r['opening_hours']}")
            parts.append(f"source {r.get('source')}")
            lines.append(" | ".join(parts))
        return "\n".join(lines)
    except Exception as e:  # fail-soft: never break chat on a map lookup
        logger.warning("Nearby services lookup failed: %s", e)
        return "LOOKUP FAILED: tell the farmer the nearby-services map is temporarily unavailable."
    finally:
        db.close()


async def nearby_node(state: AgentState) -> dict:
    """Answer nearby-shop questions from the real directory + OSM data."""
    claude = get_claude()
    user_text = _last_user_text(state)
    data = await _nearby_results_text(
        state.get("user_id", ""), state.get("entities") or {}, user_text
    )
    answer = claude.complete(
        system=NEARBY_SERVICES_SYSTEM + CHAT_RESPONSE_RULES,
        messages=[
            {
                "role": "user",
                "content": (
                    f"FARMER CONTEXT:\n{state.get('farmer_context', 'none')}\n\n"
                    f"{data}\n\nFARMER QUESTION: {user_text}"
                ),
            }
        ],
        max_tokens=900,
    )
    return {"specialist_outputs": {"nearby_services": answer}}


def advisor_node(state: AgentState) -> dict:
    claude = get_claude()
    answer = claude.complete(
        system=ADVISOR_SYSTEM + CHAT_RESPONSE_RULES + "\n\nFARMER CONTEXT:\n" + (state.get("farmer_context") or "none"),
        messages=_recent_history(state),
        max_tokens=1400,
    )
    return {"specialist_outputs": {"advisor": answer}}


def sanitize_chat_output(text: str) -> str:
    """Final guard for chat: strip residual JSON blobs / code fences that
    sometimes leak from schema-trained specialist prompts."""
    import re as _re

    if not text:
        return text
    cleaned = text.strip()
    # Remove fenced code blocks (```json ... ``` or ``` ... ```)
    cleaned = _re.sub(r"```[a-zA-Z]*\s*.*?```", "", cleaned, flags=_re.DOTALL)
    # Remove raw JSON-looking blocks ({...} spanning 2+ lines with quoted keys)
    def _json_block(m):
        blob = m.group(0)
        if '"' in blob and ":" in blob:
            return ""
        return blob
    cleaned = _re.sub(r"\{[^{}]*\}", _json_block, cleaned, flags=_re.DOTALL)
    # Tidy whitespace left behind
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or text.strip()


def merge_node(state: AgentState) -> dict:
    """Combine specialist outputs into one farmer-friendly response."""
    outs = state.get("specialist_outputs") or {}

    if not outs:
        if state.get("direct_answer"):
            return {"final_response": sanitize_chat_output(state["direct_answer"])}
        # Fallback: advisor answers directly
        claude = get_claude()
        answer = claude.complete(
            system=ADVISOR_SYSTEM + CHAT_RESPONSE_RULES + "\n\nFARMER CONTEXT:\n" + (state.get("farmer_context") or "none"),
            messages=_recent_history(state),
            max_tokens=1200,
        )
        return {"final_response": sanitize_chat_output(answer)}

    if len(outs) == 1:
        return {"final_response": sanitize_chat_output(next(iter(outs.values())))}

    claude = get_claude()
    combined = "\n\n---\n\n".join(f"[{name}]\n{text}" for name, text in outs.items())
    answer = claude.complete(
        system=(
            "You are the AgriGPT Coordinator. Multiple specialist agents answered the farmer's "
            "question. Merge their outputs into ONE clear, well-structured answer in the farmer's "
            "language. Remove repetition, keep all concrete numbers and advice, use short sections "
            "with bold headers or bullets where helpful. Do not output JSON or code blocks. "
            "Do not mention agents or internals."
        ),
        messages=[
            {"role": "user", "content": f"ORIGINAL QUESTION:\n{_last_user_text(state)}\n\nSPECIALIST OUTPUTS:\n{combined}"}
        ],
        max_tokens=1600,
    )
    return {"final_response": sanitize_chat_output(answer)}


# ----------------------------------------------------------------------
# Graph assembly
# ----------------------------------------------------------------------
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("coordinator", coordinator_node)
    g.add_node("crop", crop_node)
    g.add_node("disease", disease_node)
    g.add_node("weather", weather_node)
    g.add_node("market", market_node)
    g.add_node("profit", profit_node)
    g.add_node("nearby", nearby_node)
    g.add_node("advisor", advisor_node)
    g.add_node("merge", merge_node)

    g.add_edge(START, "coordinator")
    g.add_conditional_edges(
        "coordinator",
        route_by_intent,
        {
            "crop": "crop",
            "disease": "disease",
            "weather": "weather",
            "market": "market",
            "profit": "profit",
            "nearby": "nearby",
            "advisor": "advisor",
            "done": END,
        },
    )
    for specialist in ("crop", "disease", "weather", "market", "profit", "nearby", "advisor"):
        g.add_edge(specialist, "merge")
    g.add_edge("merge", END)
    return g.compile()


agrigpt_graph = build_graph()


# ----------------------------------------------------------------------
# Streaming support (used by chat_service.stream_message / SSE endpoint)
# ----------------------------------------------------------------------
async def classify_intent(farmer_context: str, history: list[dict], new_message: str) -> tuple[str, dict]:
    """Coordinator classification only (no direct-answer generation)."""
    claude = get_claude()
    context_block = f"FARMER CONTEXT:\n{farmer_context}\n\nMESSAGE:\n{new_message}"
    try:
        result = await claude.acomplete_fast_json(
            system=COORDINATOR_SYSTEM,
            messages=[{"role": "user", "content": context_block}],
            max_tokens=400,
        )
        intent = result.get("intent", "general_advice")
        return INTENT_TO_AGENT.get(intent, "general_advice"), result.get("entities") or {}
    except Exception as e:
        logger.warning("classify_intent fallback to advisor: %s", e)
        return "general_advice", {}


def specialist_system_for(intent: str) -> str:
    """System prompt for a specialist in streaming chat mode."""
    system_map = {
        "crop_recommendation": CROP_RECOMMENDATION_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nThis is a chat context: present the analysis as friendly prose with the numeric "
          "rigor (investment, revenue, profit, risk, confidence) woven into sentences or a table.",
        "disease_detection": (
            "You are a plant pathologist helping via chat (no image provided). Ask targeted "
            "diagnostic questions (which crop, what symptoms, since when, spread pattern, weather) "
            "and give the most likely causes plus immediate containment steps. Keep it practical "
            "for Indian farming conditions."
        ),
        "weather": WEATHER_AGENT_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nYou are in CHAT mode: the JSON schema above is for internal reference only. "
          "Answer in friendly prose using the forecast numbers.",
        "market": MARKET_FORECAST_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nYou are in CHAT mode: the JSON schema above is for internal reference only. "
          "Answer in friendly prose with the trend/forecast numbers included.",
        "profit_optimization": PROFIT_OPTIMIZATION_SYSTEM
        + CHAT_RESPONSE_RULES
        + "\nYou are in CHAT mode: the JSON schema above is for internal reference only. "
          "If cost details are missing, state assumptions briefly, then present the projection "
          "as prose/tables — never as JSON.",
        # Accept both the raw intent and the mapped agent name.
        "nearby_services": NEARBY_SERVICES_SYSTEM + CHAT_RESPONSE_RULES,
        "nearby": NEARBY_SERVICES_SYSTEM + CHAT_RESPONSE_RULES,
        "general_advice": ADVISOR_SYSTEM + CHAT_RESPONSE_RULES,
    }
    return system_map.get(intent, ADVISOR_SYSTEM + CHAT_RESPONSE_RULES)


async def stream_specialist_turn(
    intent: str,
    entities: dict,
    farmer_context: str,
    history: list[dict],
    user_message: str,
    user_id: str,
):
    """Yield text deltas for one specialist answer.

    Mirrors the graph nodes' prompt construction (weather injects live data,
    market notes the data situation) so streaming and non-streaming paths
    produce equivalent answers.
    """
    claude = get_claude()
    system = specialist_system_for(intent)

    if intent in ("nearby_services", "nearby"):
        data = await _nearby_results_text(user_id, entities or {}, user_message)
        messages = [
            {
                "role": "user",
                "content": (
                    f"FARMER CONTEXT:\n{farmer_context}\n\n{data}\n\n"
                    f"FARMER QUESTION: {user_message}"
                ),
            }
        ]
        async for delta in claude.astream(
            system=NEARBY_SERVICES_SYSTEM + CHAT_RESPONSE_RULES,
            messages=messages,
            max_tokens=900,
        ):
            yield delta
        return
    if intent == "weather":
        location = (entities or {}).get("location") or ""
        summary = await get_weather_summary_for_agent(user_id, location)
        user_block = (
            f"FARMER CONTEXT:\n{farmer_context}\n\n"
            f"7-DAY FORECAST DATA (Open-Meteo):\n{summary}\n\n"
            f"FARMER QUESTION: {user_message}"
        )
        messages = [{"role": "user", "content": user_block}]
    elif intent == "market":
        crop = (entities or {}).get("crop") or "the crop in question"
        user_block = (
            f"FARMER CONTEXT:\n{farmer_context}\n\n"
            f"Note: live mandi feed is unavailable in this chat; use typical seasonal "
            f"price ranges for the crop. Crop in focus: {crop}.\n\n"
            f"FARMER QUESTION: {user_message}"
        )
        messages = [{"role": "user", "content": user_block}]
    elif intent in ("crop_recommendation", "profit_optimization"):
        messages = [
            {"role": "user", "content": f"FARMER CONTEXT:\n{farmer_context}"},
            *_recent_history({"messages": history}),
            {"role": "user", "content": user_message},
        ]
    else:
        # advisor / disease: conversational history
        messages = _recent_history({"messages": history}) + [
            {"role": "user", "content": user_message}
        ]
        if intent == "general_advice":
            messages[0] = {
                "role": "user",
                "content": f"FARMER CONTEXT:\n{farmer_context}\n\n{messages[0]['content']}",
            }

    max_tokens = 1400 if intent in ("crop_recommendation", "general_advice") else 1000
    async for delta in claude.astream(
        system=system + "\n\nFARMER CONTEXT:\n" + farmer_context if intent == "general_advice" else system,
        messages=messages,
        max_tokens=max_tokens,
    ):
        yield delta


async def run_chat_turn(
    user_id: str,
    farmer_context: str,
    history: list[dict],
    new_message: str,
) -> dict:
    """Run one chat turn through the graph. Returns final state fields."""
    config = {"recursion_limit": 25}
    initial: AgentState = {
        "messages": [*_recent_history({"messages": history}), {"role": "user", "content": new_message}],
        "user_id": user_id,
        "farmer_context": farmer_context,
        "specialist_outputs": {},
    }
    final = await agrigpt_graph.ainvoke(initial, config=config)
    response = sanitize_chat_output(final.get("final_response", ""))
    return {
        "intent": final.get("intent", "general_advice"),
        "response": response,
        "entities": final.get("entities") or {},
    }
