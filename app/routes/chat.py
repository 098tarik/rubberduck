"""Chat API routes."""

import json
import uuid

import fastapi
import fastapi.responses
import pydantic

from app import abort, config, query_engine, telemetry

router = fastapi.APIRouter()


class ChatRequest(pydantic.BaseModel):
    """Request body for the chat streaming endpoint."""

    session_id: str | None = None
    model: str | None = None
    message: str


def _is_cloud_model(model: str) -> bool:
    """Return True if the model name refers to a cloud-hosted model."""
    return model.endswith(":cloud")


@router.post("/chat/{request_id}/cancel")
async def cancel_chat(request_id: str) -> dict[str, bool]:
    """Cancel an in-flight streaming chat request by its request ID."""
    cancelled = abort.request_abort(request_id)
    if not cancelled:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Request not found or already completed.",
        )
    return {"cancelled": True}


@router.post("/chat")
async def chat(request: ChatRequest) -> fastapi.responses.StreamingResponse:
    """Start streaming a chat response for the current session."""
    session_id = request.session_id or str(uuid.uuid4())
    request_id = str(uuid.uuid4())
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

    abort_event = abort.create_abort_controller(request_id)
    engine = query_engine.QueryEngine(session_id=session_id, model=model)

    async def _stream_with_telemetry():
        try:
            async for chunk in engine.query(request.message, abort_event):
                yield chunk
            telemetry.record(
                "chat_completed",
                session_id=session_id,
                requested_model=model,
                model=engine.model,
            )
        except Exception:
            telemetry.record(
                "chat_error",
                session_id=session_id,
                requested_model=model,
                model=engine.model,
                reason="unexpected_error",
            )
            yield f"data: {json.dumps({'error': 'An unexpected error occurred.'})}\n\n"
        finally:
            abort.cleanup_abort_controller(request_id)

    return fastapi.responses.StreamingResponse(
        _stream_with_telemetry(),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "X-Request-Id": request_id,
            "Cache-Control": "no-cache",
        },
    )
