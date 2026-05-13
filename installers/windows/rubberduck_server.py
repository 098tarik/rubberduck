"""Windows launcher entrypoint for RubberDuck server binary.

This module is used by PyInstaller to build RubberDuckServer.exe.
It sets writable paths under LOCALAPPDATA, then starts uvicorn.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


LOGGER = logging.getLogger("rubberduck.launcher")


def _configure_file_logging() -> pathlib.Path:
    local_app_data = pathlib.Path(os.getenv("LOCALAPPDATA", str(pathlib.Path.home())))
    app_home = local_app_data / "RubberDuck"
    app_home.mkdir(parents=True, exist_ok=True)

    log_path = pathlib.Path(
        os.getenv("RUBBERDUCK_LOG", str(app_home / "rubberduck.log"))
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("rubberduck")
    if not any(
        isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(log_path)
        for handler in root.handlers
    ):
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )
        root.addHandler(file_handler)
    root.setLevel(logging.INFO)
    root.propagate = False

    LOGGER.info("Launcher logging initialized at %s", log_path)
    print(f"[RubberDuck] Writing launcher logs to: {log_path}")
    return log_path


def _set_runtime_paths() -> None:
    local_app_data = pathlib.Path(os.getenv("LOCALAPPDATA", str(pathlib.Path.home())))
    app_home = local_app_data / "RubberDuck"
    sessions_dir = app_home / "sessions"
    telemetry_log = app_home / "telemetry.jsonl"
    launcher_log = app_home / "rubberduck.log"

    sessions_dir.mkdir(parents=True, exist_ok=True)
    app_home.mkdir(parents=True, exist_ok=True)

    # Ensure writes do not go to Program Files.
    os.environ.setdefault("SESSIONS_DIR", str(sessions_dir))
    os.environ.setdefault("TELEMETRY_LOG", str(telemetry_log))
    os.environ.setdefault("RUBBERDUCK_LOG", str(launcher_log))


def _set_working_directory() -> None:
    if getattr(sys, "frozen", False):
        exe_dir = pathlib.Path(sys.executable).resolve().parent
        bundled_repo = exe_dir / "repo"
        if bundled_repo.exists():
            os.chdir(bundled_repo)
            LOGGER.info("Working directory set to bundled repo: %s", bundled_repo)
        else:
            os.chdir(exe_dir)
            LOGGER.info("Working directory set to executable directory: %s", exe_dir)


def _pick_port(default: int = 8000) -> int:
    env_port = os.getenv("RUBBERDUCK_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sock.connect_ex(("127.0.0.1", default)) != 0:
            return default

    return default + 1


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _ollama_is_running(timeout: float = 2.0) -> bool:
    if _http_ok("http://127.0.0.1:11434/api/tags", timeout=timeout):
        return True

    try:
        req = urllib.request.Request("http://127.0.0.1:11434/", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                return False
            body = response.read().decode("utf-8", errors="replace")
            return "ollama is running" in body.lower()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _which_ollama() -> str | None:
    direct = shutil.which("ollama")
    if direct:
        return direct

    # Common Windows install locations
    candidates = [
        pathlib.Path(os.getenv("ProgramFiles", "")) / "Ollama" / "ollama.exe",
        pathlib.Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _run_command(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=False,
    )


def _install_ollama() -> bool:
    print("[RubberDuck] Ollama not detected. Installing automatically...")
    LOGGER.info("Ollama not detected. Attempting automatic installation.")

    winget = shutil.which("winget")
    if winget:
        try:
            _run_command(
                [
                    winget,
                    "install",
                    "-e",
                    "--id",
                    "Ollama.Ollama",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
            LOGGER.info("Ollama installed successfully via winget.")
            return True
        except subprocess.CalledProcessError:
            print("[RubberDuck] winget install failed, trying Chocolatey...")
            LOGGER.error("winget install failed; trying Chocolatey.")

    choco = shutil.which("choco")
    if choco:
        try:
            _run_command([choco, "install", "ollama", "-y"])
            LOGGER.info("Ollama installed successfully via Chocolatey.")
            return True
        except subprocess.CalledProcessError:
            print("[RubberDuck] Chocolatey install failed.")
            LOGGER.error("Chocolatey install failed.")

    print("[RubberDuck] Could not auto-install Ollama. Please install from https://ollama.com/download/windows")
    LOGGER.error("Could not auto-install Ollama with winget/choco.")
    return False


def _start_ollama(ollama_cmd: str) -> bool:
    if _ollama_is_running():
        LOGGER.info("Detected already-running Ollama service before launch attempt.")
        return True

    print("[RubberDuck] Starting Ollama...")
    LOGGER.info("Starting Ollama via command: %s serve", ollama_cmd)
    try:
        process = subprocess.Popen(
            [ollama_cmd, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except OSError:
        LOGGER.exception("Failed to spawn 'ollama serve'.")
        return False

    # Wait up to 25s for API readiness
    for attempt in range(1, 26):
        if _ollama_is_running():
            LOGGER.info("Ollama service became ready on attempt %s.", attempt)
            return True
        if process.poll() is not None:
            LOGGER.warning(
                "Spawned ollama process exited early with code %s (attempt %s).",
                process.returncode,
                attempt,
            )
            if not _ollama_is_running():
                LOGGER.error(
                    "Spawned ollama process exited and service is still unreachable; stopping retries."
                )
                break
        time.sleep(1)

    if _ollama_is_running():
        LOGGER.info("Ollama service detected as running after startup wait window.")
        return True
    LOGGER.error("Ollama did not become ready after startup wait window.")
    return False


def _pull_model(ollama_cmd: str, model: str) -> bool:
    print(f"[RubberDuck] Ensuring Ollama model is available: {model}")
    LOGGER.info("Ensuring Ollama model is available: %s", model)
    try:
        _run_command([ollama_cmd, "pull", model])
        LOGGER.info("Model pull succeeded for %s", model)
        return True
    except subprocess.CalledProcessError:
        LOGGER.exception("Model pull failed for %s", model)
        return False


def _bootstrap_ollama_and_model() -> None:
    LOGGER.info("Starting Ollama bootstrap flow.")
    ollama_cmd = _which_ollama()
    if not ollama_cmd:
        if not _install_ollama():
            return
        ollama_cmd = _which_ollama()
        if not ollama_cmd:
            print("[RubberDuck] Ollama install completed but binary was not found in PATH.")
            LOGGER.error("Ollama install completed but binary was still not found.")
            return

    LOGGER.info("Using Ollama executable: %s", ollama_cmd)
    if not _start_ollama(ollama_cmd):
        print("[RubberDuck] Unable to start Ollama automatically. Please run 'ollama serve' manually.")
        LOGGER.error("Unable to start or detect running Ollama service.")
        return

    model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    if not _pull_model(ollama_cmd, model):
        print(f"[RubberDuck] Failed to pull model '{model}'. You can run: ollama pull {model}")
        LOGGER.error("Failed to pull model %s", model)


def main() -> None:
    _set_runtime_paths()
    log_path = _configure_file_logging()
    _set_working_directory()
    LOGGER.info("Runtime startup initiated.")
    _bootstrap_ollama_and_model()

    host = os.getenv("RUBBERDUCK_HOST", "127.0.0.1")
    port = _pick_port(8000)
    LOGGER.info("Server configuration resolved: host=%s port=%s", host, port)

    from app import app
    import uvicorn

    if os.getenv("RUBBERDUCK_OPEN_BROWSER", "1") == "1":
        try:
            webbrowser.open(f"http://{host}:{port}")
            LOGGER.info("Browser launch requested for http://%s:%s", host, port)
        except Exception:
            LOGGER.exception("Failed to launch browser.")

    LOGGER.info("Starting uvicorn. Logs file: %s", log_path)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
