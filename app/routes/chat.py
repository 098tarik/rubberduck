"""Chat API routes."""

import json
import logging
import uuid

import fastapi
import fastapi.responses
import pydantic

from app import abort, config, query_engine, telemetry

router = fastapi.APIRouter()
LOGGER = logging.getLogger("rubberduck.routes.chat")


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
    LOGGER.info("Cancel request received for request_id=%s cancelled=%s", request_id, cancelled)
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
    LOGGER.info(
        "Chat request started request_id=%s session_id=%s model=%s message_length=%s",
        request_id,
        session_id,
        model,
        len(request.message),
    )

    if _is_cloud_model(model):
        telemetry.record("chat_error", session_id=session_id, model=model, reason="cloud_model_rejected")
        LOGGER.warning(
            "Rejected cloud model for request_id=%s session_id=%s model=%s",
            request_id,
            session_id,
            model,
        )
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
            LOGGER.info(
                "Chat request completed request_id=%s session_id=%s requested_model=%s final_model=%s",
                request_id,
                session_id,
                model,
                engine.model,
            )
        except Exception:
            telemetry.record(
                "chat_error",
                session_id=session_id,
                requested_model=model,
                model=engine.model,
                reason="unexpected_error",
            )
            LOGGER.exception(
                "Unexpected chat error request_id=%s session_id=%s requested_model=%s current_model=%s",
                request_id,
                session_id,
                model,
                engine.model,
            )
            yield f"data: {json.dumps({'error': 'An unexpected error occurred.'})}\n\n"
        finally:
            abort.cleanup_abort_controller(request_id)
            LOGGER.info("Cleaned up chat request controller request_id=%s", request_id)

    return fastapi.responses.StreamingResponse(
        _stream_with_telemetry(),
        media_type="text/event-stream",
        headers={
            "X-Session-Id": session_id,
            "X-Request-Id": request_id,
            "Cache-Control": "no-cache",
        },
    )
