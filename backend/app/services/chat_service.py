"""Chat service: session management, memory, coordinator routing via LangGraph."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.agents import run_chat_turn
from app.core.exceptions import NotFoundError
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

logger = logging.getLogger("app.services.chat")

TITLE_MAX = 60

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (Devanagari script)",
    "te": "Telugu (Telugu script)",
    "ta": "Tamil (Tamil script)",
    "kn": "Kannada (Kannada script)",
    "mr": "Marathi (Devanagari script)",
}


def language_directive(lang_hint: str | None, user_language: str | None = None) -> str:
    """One-line instruction appended to the farmer context."""
    code = (lang_hint or user_language or "en").lower()
    name = LANGUAGE_NAMES.get(code)
    if not name:
        return ""
    return f"LANGUAGE: Reply in {name}. Keep technical terms understandable; use common English loanwords where farmers use them."


def _decision_context_block(db: Session | None, user: User) -> str | None:
    """Copilot tool-use (Part 15): pull REAL data the advisor can cite.

    Retrieves recorded expenses, last harvest, latest estimates and any open
    crop-health issue so questions like "how much did I spend on fertilizer?"
    are answered from records, not guesses. Returns a compact block or None.
    """
    if db is None:
        return None
    try:
        import uuid as uuidlib
        from datetime import date, timedelta

        from app.models.disease_report import DiseaseReport
        from app.models.expense import Expense
        from app.models.harvest import Harvest
        from app.models.profit_prediction import ProfitPrediction

        uid = uuidlib.UUID(str(user.id))
        lines: list[str] = []

        # Expenses by category (last 90 days)
        since = date.today() - timedelta(days=90)
        rows = (
            db.query(Expense.category, Expense.amount_inr)
            .filter(Expense.user_id == uid, Expense.spent_on >= since)
            .all()
        )
        if rows:
            by_cat: dict[str, float] = {}
            for cat, amt in rows:
                by_cat[cat] = by_cat.get(cat, 0) + float(amt or 0)
            total = sum(by_cat.values())
            breakdown = ", ".join(f"{k}: Rs.{v:,.0f}" for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]))
            lines.append(
                f"RECORDED EXPENSES (last 90 days): total Rs.{total:,.0f} — {breakdown}"
            )

        # Latest profit estimate
        est = (
            db.query(ProfitPrediction)
            .filter(ProfitPrediction.user_id == uid)
            .order_by(ProfitPrediction.created_at.desc())
            .first()
        )
        if est:
            lines.append(
                f"LATEST PROFIT ESTIMATE: {est.crop} — cost Rs.{float(est.total_cost or 0):,.0f}, "
                f"expected revenue Rs.{float(est.expected_revenue or 0):,.0f}, "
                f"expected profit Rs.{float(est.expected_profit or 0):,.0f} (AI estimate)"
            )

        # Last harvest (actual outcome)
        h = (
            db.query(Harvest)
            .filter(Harvest.user_id == uid)
            .order_by(Harvest.created_at.desc())
            .first()
        )
        if h:
            parts = [f"LAST HARVEST: {h.crop}"]
            if h.actual_yield_quintals is not None:
                parts.append(f"yield {float(h.actual_yield_quintals):.1f} q")
            if h.selling_price_per_quintal is not None:
                parts.append(f"price Rs.{float(h.selling_price_per_quintal):,.0f}/q")
            if h.revenue_inr is not None:
                parts.append(f"revenue Rs.{float(h.revenue_inr):,.0f}")
            lines.append(" ".join(parts) + " (actual recorded data)")

        # Open crop-health issue
        scan = (
            db.query(DiseaseReport)
            .filter(
                DiseaseReport.user_id == uid,
                DiseaseReport.is_healthy.is_(False),
                DiseaseReport.created_at >= date.today() - timedelta(days=30),
            )
            .order_by(DiseaseReport.created_at.desc())
            .first()
        )
        if scan:
            status = scan.followup_status or "open"
            lines.append(
                f"RECENT CROP HEALTH: possible {scan.disease_name} on {scan.crop} "
                f"({scan.confidence:.0f}% confidence, status {status}) — mention monitoring if relevant"
            )

        if not lines:
            return None
        return "FARM RECORDS (verified user data — cite these instead of guessing):\n" + "\n".join(lines)
    except Exception as e:
        logger.warning("Decision context block failed: %s", e)
        return None


def _crop_age_line(db: Session | None, user: User) -> str | None:
    """Crop-age line from the farm's planting_date, when actually recorded.

    Only computed when a real planting date exists — never guessed.
    """
    if db is None:
        return None
    try:
        from datetime import date

        from app.models.farm import Farm

        farm = (
            db.query(Farm)
            .filter(
                Farm.user_id == user.id,
                Farm.planting_date.isnot(None),
                Farm.current_crop.isnot(None),
            )
            .order_by(Farm.planting_date.desc())
            .first()
        )
        if not farm:
            return None
        days = (date.today() - farm.planting_date).days
        if days < 0:
            return None
        return (
            f"Current crop age: {farm.current_crop} sown {days} days ago "
            f"(planting date {farm.planting_date.isoformat()}) — use this to "
            "tailor growth-stage advice."
        )
    except Exception:
        return None


def build_farmer_context(user: User, db=None, language_hint: str | None = None) -> str:
    """Compact farmer profile block injected into agent prompts.
    Includes exact coordinates + precision when available."""
    if user.latitude is not None and user.longitude is not None:
        place = ", ".join(filter(None, [user.village, user.district, user.state])) or "saved pin"
        location = (
            f"Location: {place} — EXACT coordinates {float(user.latitude):.4f}, "
            f"{float(user.longitude):.4f} (source: {user.location_source or 'pin'})"
        )
    else:
        location = "Location: " + ", ".join(filter(None, [user.village, user.district, user.state])).strip() or "Location: unknown (district-level only)"
    parts = [
        f"Name: {user.name}",
        location,
        f"Farm size: {user.farm_size_acres} acres",
        f"Soil: {user.soil_type}",
        f"Water: {user.water_availability}",
    ]
    crop_age = _crop_age_line(db, user)
    if crop_age:
        parts.append(crop_age)
    records = _decision_context_block(db, user)
    if records:
        parts.append(records)
    directive = language_directive(language_hint, getattr(user, "language", None))
    if directive:
        parts.append(directive)
    return "\n".join(parts)


class ChatService:
    def __init__(self, db: Session):
        self.db = db

    def list_sessions(self, user_id: str) -> list[ChatSession]:
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == uuid.UUID(user_id))
            .order_by(ChatSession.updated_at.desc())
            .limit(50)
            .all()
        )

    def create_session(self, user_id: str, title: str = "New conversation") -> ChatSession:
        session = ChatSession(user_id=uuid.UUID(user_id), title=title[:TITLE_MAX])
        self.db.add(session)
        self.db.flush()
        return session

    def get_session(self, user_id: str, session_id: str) -> ChatSession:
        session = (
            self.db.query(ChatSession)
            .filter(
                ChatSession.id == uuid.UUID(session_id),
                ChatSession.user_id == uuid.UUID(user_id),
            )
            .first()
        )
        if not session:
            raise NotFoundError("Chat session not found")
        return session

    def get_messages(self, user_id: str, session_id: str) -> list[ChatMessage]:
        session = self.get_session(user_id, session_id)
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

    def delete_session(self, user_id: str, session_id: str) -> None:
        session = self.get_session(user_id, session_id)
        self.db.delete(session)

    def _prepare_turn(
        self, user: User, session_id: str | None, content: str
    ) -> tuple[ChatSession, list[dict], str]:
        """Shared preamble: resolve session, persist the user message, build history/context."""
        if session_id:
            session = self.get_session(str(user.id), session_id)
        else:
            title = content.strip()[:TITLE_MAX] or "New conversation"
            session = self.create_session(str(user.id), title)

        user_msg = ChatMessage(
            session_id=session.id,
            user_id=user.id,
            role="user",
            content=content,
        )
        self.db.add(user_msg)
        self.db.flush()

        history = [
            {"role": m.role, "content": m.content}
            for m in self.get_messages(str(user.id), str(session.id))[:-1][-12:]
        ]
        context = build_farmer_context(user, self.db)
        # Commit the turn now — see _prepare_turn_with_lang for why.
        self.db.commit()
        return session, history, context

    def _prepare_turn_with_lang(
        self, user: User, session_id: str | None, content: str, language: str | None
    ) -> tuple[ChatSession, ChatMessage, list[dict], str]:
        """Like _prepare_turn but with the client's language hint in context."""
        if session_id:
            session = self.get_session(str(user.id), session_id)
        else:
            title = content.strip()[:TITLE_MAX] or "New conversation"
            session = self.create_session(str(user.id), title)

        user_msg = ChatMessage(
            session_id=session.id,
            user_id=user.id,
            role="user",
            content=content,
        )
        self.db.add(user_msg)
        self.db.flush()

        history = [
            {"role": m.role, "content": m.content}
            for m in self.get_messages(str(user.id), str(session.id))[:-1][-12:]
        ]
        context = build_farmer_context(user, self.db, language_hint=language)
        # Commit the turn before the caller streams the answer: that stream can
        # hold this session open for many seconds (LLM latency), and an
        # uncommitted write blocks every other writer for the whole window.
        # Committing also makes the session id durable *before* it is sent to
        # the client, so a follow-up message can never reference a session that
        # was rolled back.
        self.db.commit()
        return session, user_msg, history, context

    def _persist_assistant(
        self, session: ChatSession, content: str, agent_used: str
    ) -> ChatMessage:
        assistant_msg = ChatMessage(
            session_id=session.id,
            user_id=session.user_id,
            role="assistant",
            content=content,
            agent=agent_used,
        )
        self.db.add(assistant_msg)
        session.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return assistant_msg

    async def send_message(
        self, user: User, session_id: str | None, content: str,
        forced_agent: str | None = None, language: str | None = None,
    ) -> tuple[ChatSession, ChatMessage, ChatMessage, dict]:
        """Persist user msg, run agent graph, persist assistant msg."""
        session, user_msg, history, context = self._prepare_turn_with_lang(user, session_id, content, language)

        if forced_agent:
            # Direct-to-agent mode (bypass coordinator routing)
            from app.ai.claude_client import get_claude
            from app.ai.prompts import (
                ADVISOR_SYSTEM,
                CROP_RECOMMENDATION_SYSTEM,
                MARKET_FORECAST_SYSTEM,
                PROFIT_OPTIMIZATION_SYSTEM,
                WEATHER_AGENT_SYSTEM,
            )

            system_map = {
                "crop": CROP_RECOMMENDATION_SYSTEM,
                "disease": None,
                "weather": WEATHER_AGENT_SYSTEM,
                "market": MARKET_FORECAST_SYSTEM,
                "profit": PROFIT_OPTIMIZATION_SYSTEM,
                "advisor": ADVISOR_SYSTEM,
            }
            system_map["disease"] = (
                "You are a plant pathologist helping via chat. Ask targeted diagnostic "
                "questions and give likely causes plus immediate steps."
            )
            system = system_map.get(forced_agent, ADVISOR_SYSTEM)
            claude = get_claude()
            response_text = claude.complete(
                system=system + "\n\nFARMER CONTEXT:\n" + context,
                messages=[{"role": "user", "content": content}],
                max_tokens=1400,
            )
            agent_used = forced_agent
            meta = {"intent": forced_agent}
        else:
            result = await run_chat_turn(
                user_id=str(user.id),
                farmer_context=context,
                history=history,
                new_message=content,
            )
            response_text = result["response"]
            agent_used = result.get("intent", "general_advice")
            meta = {"intent": result.get("intent"), "entities": result.get("entities")}

        assistant_msg = self._persist_assistant(session, response_text, agent_used)
        # Release the writer before returning — see stream_message for why.
        self.db.commit()
        return session, user_msg, assistant_msg, meta

    async def stream_message(
        self, user: User, session_id: str | None, content: str,
        forced_agent: str | None = None, language: str | None = None,
    ):
        """Streaming variant: yields SSE-formatted dicts via the router.

        Flow: resolve session + persist user msg, run the routing graph
        (coordinator + specialist) with the specialist output STREAMED when
        possible, persist the full assistant msg at the end, emit done event
        with ids so the client can continue the conversation immediately.
        Falls back to non-streaming send_message on any streaming failure.
        """
        session, _user_msg, history, context = self._prepare_turn_with_lang(user, session_id, content, language)
        yield {"type": "meta", "session_id": str(session.id)}

        agent_used = forced_agent or "general_advice"
        response_text = ""

        try:
            if forced_agent:
                from app.ai.claude_client import get_claude
                from app.ai.prompts import (
                    ADVISOR_SYSTEM,
                    CROP_RECOMMENDATION_SYSTEM,
                    MARKET_FORECAST_SYSTEM,
                    PROFIT_OPTIMIZATION_SYSTEM,
                    WEATHER_AGENT_SYSTEM,
                )

                system_map = {
                    "crop": CROP_RECOMMENDATION_SYSTEM,
                    "disease": "You are a plant pathologist helping via chat. Ask targeted diagnostic questions and give likely causes plus immediate steps.",
                    "weather": WEATHER_AGENT_SYSTEM,
                    "market": MARKET_FORECAST_SYSTEM,
                    "profit": PROFIT_OPTIMIZATION_SYSTEM,
                    "advisor": ADVISOR_SYSTEM,
                }
                system = system_map.get(forced_agent, ADVISOR_SYSTEM)
                claude = get_claude()
                agent_used = forced_agent
                yield {"type": "agent", "agent": agent_used}
                async for delta in claude.astream(
                    system=system + "\n\nFARMER CONTEXT:\n" + context,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=1400,
                ):
                    response_text += delta
                    yield {"type": "delta", "text": delta}
            else:
                # Route first (coordinator is a fast model call), then stream
                # the specialist's answer with live weather data when relevant.
                from app.ai.agents import classify_intent, stream_specialist_turn

                intent, entities = await classify_intent(context, history, content)
                agent_used = intent
                yield {"type": "agent", "agent": intent}
                async for delta in stream_specialist_turn(
                    intent=intent,
                    entities=entities,
                    farmer_context=context,
                    history=history,
                    user_message=content,
                    user_id=str(user.id),
                ):
                    response_text += delta
                    yield {"type": "delta", "text": delta}
        except Exception as e:
            logger.warning("Streaming turn failed (%s); falling back to non-streaming", e)
            # Non-streaming fallback for the same turn
            result = await run_chat_turn(
                user_id=str(user.id),
                farmer_context=context,
                history=history,
                new_message=content,
            )
            response_text = result["response"]
            agent_used = result.get("intent", "general_advice")
            yield {"type": "agent", "agent": agent_used}
            yield {"type": "delta", "text": response_text}

        from app.ai.agents import sanitize_chat_output

        response_text = sanitize_chat_output(response_text) or response_text
        assistant_msg = self._persist_assistant(session, response_text, agent_used)
        # Commit here instead of trusting the request dependency to do it after
        # the response: this generator drives a StreamingResponse, and a write
        # transaction still open once it returns pins SQLite's single writer
        # lock for the life of the process — after which every other write
        # (including new chat sessions) fails with "database is locked".
        self.db.commit()
        yield {
            "type": "done",
            "session_id": str(session.id),
            "message_id": str(assistant_msg.id),
            "agent": agent_used,
        }
