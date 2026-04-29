"""FastAPI application factory module for RubberDuck."""

import fastapi
import fastapi.responses
import fastapi.staticfiles

from rubberduck.app import routes


app = fastapi.FastAPI(title="RubberDuck")

app.include_router(routes.chat_router, prefix="/api")
app.include_router(routes.sessions_router, prefix="/api")
app.include_router(routes.models_router, prefix="/api")

app.mount(
    "/static",
    fastapi.staticfiles.StaticFiles(directory="."),
    name="static",
)


@app.get("/")
async def root() -> fastapi.responses.FileResponse:
    """Serve the main frontend page."""
    return fastapi.responses.FileResponse("./index.html")
