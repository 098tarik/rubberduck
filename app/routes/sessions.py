"""Session listing and retrieval API routes."""

import fastapi

from app import history

router = fastapi.APIRouter()


@router.get("/sessions")
async def get_sessions() -> dict[str, list[dict[str, str]]]:
    """Return summary information for persisted chat sessions."""
    return {"sessions": history.list_sessions()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, object]:
    """Return the full stored transcript for one session."""
    messages = history.load_session(session_id)
    if not messages:
        raise fastapi.HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": messages}
