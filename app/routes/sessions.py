"""Session listing and retrieval API routes."""

import fastapi

from app import history, telemetry

router = fastapi.APIRouter()


@router.get("/sessions")
async def get_sessions() -> dict[str, list[dict[str, str]]]:
    """Return summary information for persisted chat sessions."""
    sessions = history.list_sessions()
    telemetry.record("sessions_listed", count=len(sessions))
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, object]:
    """Return the full stored transcript for one session."""
    messages = history.load_session(session_id)
    if not messages:
        raise fastapi.HTTPException(status_code=404, detail="Session not found")
    telemetry.record("session_viewed", session_id=session_id, message_count=len(messages))
    return {"session_id": session_id, "messages": messages}
