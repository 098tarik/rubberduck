"""Model discovery API routes."""

import fastapi

from app import runtime, telemetry

router = fastapi.APIRouter()


@router.get("/models")
async def list_models() -> dict[str, object]:
    """Return the auto-selected embedded runtime model."""
    selected_model = await runtime.ensure_ready()
    telemetry.record("models_listed", count=1, selected_model=selected_model.name)
    return {
        "models": [selected_model.name],
        "default": selected_model.name,
        "runtime": "embedded-llama.cpp",
    }
