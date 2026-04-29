"""Chat API routes."""

import uuid

import fastapi
import fastapi.responses
import pydantic

from rubberduck.app import query_engine
from rubberduck.app import config

router = fastapi.APIRouter()


class ChatRequest(pydantic.BaseModel):
    """Request body for the chat streaming endpoint."""

    session_id: str | None = None
    model: str | None = None
    message: str


@router.post("/chat")
async def chat(request: ChatRequest) -> fastapi.responses.StreamingResponse:
    """Start streaming a chat response for the current session."""
    session_id = request.session_id or str(uuid.uuid4())
    model = request.model or config.DEFAULT_MODEL
    engine = query_engine.QueryEngine(session_id=session_id, model=model)

    return fastapi.responses.StreamingResponse(
        engine.query(request.message),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
        },
    )
