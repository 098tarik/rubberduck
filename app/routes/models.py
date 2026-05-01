"""Model discovery API routes."""

import fastapi
import httpx

from app import config

router = fastapi.APIRouter()


@router.get("/models")
async def list_models() -> dict[str, object]:
    """Return available Ollama models for the frontend model picker."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.OLLAMA_URL}/api/tags",
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
        models = [
            item["name"]
            for item in payload.get("models", [])
            if item.get("name") and not item["name"].endswith(":cloud")
        ]
        return {"models": models, "default": config.DEFAULT_MODEL}
    except httpx.HTTPError as error:
        return {
            "models": [config.DEFAULT_MODEL],
            "default": config.DEFAULT_MODEL,
            "error": str(error),
        }
