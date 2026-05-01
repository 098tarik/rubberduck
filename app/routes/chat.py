"""Chat API routes."""

import json
import uuid

import fastapi
import fastapi.responses
import pydantic

from app import config, query_engine, telemetry

router = fastapi.APIRouter()


class ChatRequest(pydantic.BaseModel):
    """Request body for the chat streaming endpoint."""

    session_id: str | None = None
    model: str | None = None
    message: str


def _is_cloud_model(model: str) -> bool:
    """Return True if the model name refers to a cloud-hosted model."""
    return model.endswith(":cloud")


@router.post("/chat")
async def chat(request: ChatRequest) -> fastapi.responses.StreamingResponse:
    """Start streaming a chat response for the current session."""
    session_id = request.session_id or str(uuid.uuid4())
    model = request.model or config.DEFAULT_MODEL

    if _is_cloud_model(model):
        telemetry.record("chat_error", session_id=session_id, model=model, reason="cloud_model_rejected")
        raise fastapi.HTTPException(
            status_code=400,
            detail="Cloud models are not supported. Please select a local Ollama model.",
        )

    is_new_session = request.session_id is None
    telemetry.record(
        "chat_started",
        session_id=session_id,
        model=model,
        new_session=is_new_session,
        message_length=len(request.message),
    )

    engine = query_engine.QueryEngine(session_id=session_id, model=model)

    async def _stream_with_telemetry():
        try:
            async for chunk in engine.query(request.message):
                yield chunk
            telemetry.record("chat_completed", session_id=session_id, model=model)
        except Exception:
            telemetry.record("chat_error", session_id=session_id, model=model, reason="unexpected_error")
            yield f"data: {json.dumps({'error': 'An unexpected error occurred.'})}\n\n"

    return fastapi.responses.StreamingResponse(
        _stream_with_telemetry(),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "Cache-Control": "no-cache",
        },
    )
