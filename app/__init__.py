"""FastAPI application factory module for RubberDuck."""

import hashlib
import pathlib
import sys

import fastapi
import fastapi.responses
import fastapi.staticfiles

from app import routes


app = fastapi.FastAPI(title="RubberDuck")


def _frontend_candidates() -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(pathlib.Path(meipass))
    candidates.append(pathlib.Path(__file__).resolve().parent.parent)
    candidates.append(pathlib.Path.cwd())
    return candidates


def _frontend_missing_message() -> str:
    searched = ", ".join(str(path) for path in _frontend_candidates())
    return (
        "Could not locate frontend assets (expected index.html and assets/). "
        f"Searched: {searched}. Ensure frontend build artifacts are present."
    )


def _resolve_frontend_root() -> pathlib.Path:
    """Resolve frontend root in priority order: _MEIPASS, source tree, then CWD.

    Returns the first location containing both index.html and assets/.
    Raises FileNotFoundError if no valid frontend root is found.
    """
    for base in _frontend_candidates():
        if (base / "index.html").is_file() and (base / "assets").is_dir():
            return base

    raise FileNotFoundError(_frontend_missing_message())


def _try_frontend_root() -> pathlib.Path | None:
    try:
        return _resolve_frontend_root()
    except FileNotFoundError:
        return None


_OPTIONAL_FRONTEND_ROOT = _try_frontend_root()

app.include_router(routes.chat_router, prefix="/api")
app.include_router(routes.sessions_router, prefix="/api")
app.include_router(routes.models_router, prefix="/api")
app.include_router(routes.recommendations_router, prefix="/api")

if _OPTIONAL_FRONTEND_ROOT is not None:
    app.mount(
        "/static",
        fastapi.staticfiles.StaticFiles(directory=str(_OPTIONAL_FRONTEND_ROOT)),
        name="static",
    )

_STATIC_ASSETS = [
    "/static/assets/css/index.css",
    "/static/assets/js/app.js",
]


def _file_hash(url_path: str) -> str:
    """Return the first 8 hex digits of the SHA-256 hash of the file at url_path."""
    if _OPTIONAL_FRONTEND_ROOT is None:
        raise FileNotFoundError(_frontend_missing_message())
    # url_path starts with "/static/", which maps to the repo root via the mount
    fs_path = _OPTIONAL_FRONTEND_ROOT / url_path.removeprefix("/static/").lstrip("/")
    try:
        return hashlib.sha256(fs_path.read_bytes()).hexdigest()[:8]
    except OSError:
        return "0"


@app.get("/")
async def root() -> fastapi.responses.HTMLResponse:
    """Serve the main frontend page with cache-busted static asset URLs."""
    if _OPTIONAL_FRONTEND_ROOT is None:
        raise fastapi.HTTPException(
            status_code=500,
            detail=_frontend_missing_message(),
        )
    html = (_OPTIONAL_FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")

    for asset_url in _STATIC_ASSETS:
        digest = _file_hash(asset_url)
        html = html.replace(f'"{asset_url}"', f'"{asset_url}?v={digest}"')

    return fastapi.responses.HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )
