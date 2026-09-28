"""AI Farm Copilot chat endpoints."""
import json
import logging
import uuid as uuidlib

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, DBSession
from app.core.plans_service import check_chat_quota
from app.schemas.ai_features import ChatMessageCreate, ChatMessageOut, ChatSessionCreate, ChatSessionOut
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger("app.api.chat")


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(user: CurrentUser, db: DBSession):
    return ChatService(db).list_sessions(str(user.id))


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(payload: ChatSessionCreate, user: CurrentUser, db: DBSession):
    return ChatService(db).create_session(str(user.id), payload.title)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def get_messages(session_id: str, user: CurrentUser, db: DBSession):
    return ChatService(db).get_messages(str(user.id), session_id)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, user: CurrentUser, db: DBSession):
    ChatService(db).delete_session(str(user.id), session_id)


@router.post("/messages")
async def send_message(payload: ChatMessageCreate, user: CurrentUser, db: DBSession):
    """Send a message; the coordinator agent routes to specialists."""
    check_chat_quota(db, user)
    session, user_msg, assistant_msg, meta = await ChatService(db).send_message(
        user=user,
        session_id=payload.session_id,
        content=payload.content,
        forced_agent=payload.agent,
        language=payload.language,
    )
    return {
        "session_id": str(session.id),
        "message": assistant_msg,
        "agent": meta.get("intent"),
    }


@router.post("/messages/stream")
async def send_message_stream(payload: ChatMessageCreate, user: CurrentUser, db: DBSession):
    """SSE streaming variant of /messages.

    Events: meta (session_id), agent (which specialist answered), delta
    (text chunks), done (final ids). Errors degrade to a full-message
    delta via the service's non-streaming fallback.
    """
    check_chat_quota(db, user)

    async def event_gen():
        try:
            async for event in ChatService(db).stream_message(
                user=user,
                session_id=payload.session_id,
                content=payload.content,
                forced_agent=payload.agent,
                language=payload.language,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:
            # Last-resort guard: never leave the stream open. Log the real
            # error server-side only — str(e) can leak internals (SQL/stack
            # details) to the client, so send a generic message instead.
            logger.exception("Chat stream failed for user %s", user.id)
            yield f"data: {json.dumps({'type': 'error', 'message': 'Something went wrong. Please try again in a moment.'})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
