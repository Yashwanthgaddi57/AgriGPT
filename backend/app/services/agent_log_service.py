"""Agent log persistence for LangGraph observability."""
import uuid

from sqlalchemy.orm import Session

from app.models.agent_log import AgentLog


def log_agent_run(
    db: Session,
    agent: str,
    action: str,
    user_id: str | None = None,
    input_data: dict | None = None,
    output_data: dict | None = None,
    latency_ms: int | None = None,
    tokens: int | None = None,
    error: str | None = None,
    level: str = "info",
) -> None:
    try:
        db.add(
            AgentLog(
                user_id=uuid.UUID(user_id) if user_id else None,
                agent=agent,
                level=level,
                action=action,
                input=input_data,
                output=output_data,
                latency_ms=latency_ms,
                tokens=tokens,
                error=error,
            )
        )
        db.flush()
    except Exception:
        pass  # never break the request because of observability
