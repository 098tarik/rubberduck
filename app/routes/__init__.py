"""Route exports for the FastAPI application package."""

from rubberduck.app.routes import sessions
from rubberduck.app.routes import chat, models


chat_router = chat.router
models_router = models.router
sessions_router = sessions.router

__all__ = ["chat_router", "models_router", "sessions_router"]
