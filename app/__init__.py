"""FastAPI application factory module for RubberDuck."""

import hashlib
import pathlib

import fastapi
import fastapi.responses
import fastapi.staticfiles

from app import routes


app = fastapi.FastAPI(title="RubberDuck")

app.include_router(routes.chat_router, prefix="/api")
app.include_router(routes.sessions_router, prefix="/api")
app.include_router(routes.models_router, prefix="/api")

app.mount(
    "/static",
    fastapi.staticfiles.StaticFiles(directory="."),
    name="static",
)

_STATIC_ASSETS = [
    "/static/assets/css/index.css",
    "/static/assets/js/app.js",
]


def _file_hash(url_path: str) -> str:
    """Return the first 8 hex digits of the SHA-256 hash of the file at url_path."""
    # url_path starts with "/static/", which maps to the repo root via the mount
    fs_path = pathlib.Path(".") / url_path.removeprefix("/static/").lstrip("/")
    try:
        return hashlib.sha256(fs_path.read_bytes()).hexdigest()[:8]
    except OSError:
        return "0"


@app.get("/")
async def root() -> fastapi.responses.HTMLResponse:
    """Serve the main frontend page with cache-busted static asset URLs."""
    html = pathlib.Path("./index.html").read_text()

    for asset_url in _STATIC_ASSETS:
        digest = _file_hash(asset_url)
        html = html.replace(f'"{asset_url}"', f'"{asset_url}?v={digest}"')

    return fastapi.responses.HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
