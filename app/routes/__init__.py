"""Route exports for the FastAPI application package."""

from app.routes import chat, models, recommendations, sessions


chat_router = chat.router
models_router = models.router
sessions_router = sessions.router
recommendations_router = recommendations.router

__all__ = ["chat_router", "models_router", "sessions_router", "recommendations_router"]
