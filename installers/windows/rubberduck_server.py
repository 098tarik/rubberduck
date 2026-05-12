"""Windows launcher entrypoint for RubberDuck server binary.

This module is used by PyInstaller to build RubberDuckServer.exe.
It sets writable paths under LOCALAPPDATA, then starts uvicorn.
"""

from __future__ import annotations

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


def _set_runtime_paths() -> None:
    local_app_data = pathlib.Path(os.getenv("LOCALAPPDATA", pathlib.Path.home()))
    app_home = local_app_data / "RubberDuck"
    sessions_dir = app_home / "sessions"
    telemetry_log = app_home / "telemetry.jsonl"

    sessions_dir.mkdir(parents=True, exist_ok=True)
    app_home.mkdir(parents=True, exist_ok=True)

    # Ensure writes do not go to Program Files.
    os.environ.setdefault("SESSIONS_DIR", str(sessions_dir))
    os.environ.setdefault("TELEMETRY_LOG", str(telemetry_log))


def _set_working_directory() -> None:
    if getattr(sys, "frozen", False):
        exe_dir = pathlib.Path(sys.executable).resolve().parent
        bundled_repo = exe_dir / "repo"
        if bundled_repo.exists():
            os.chdir(bundled_repo)
        else:
            os.chdir(exe_dir)


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
            return True
        except subprocess.CalledProcessError:
            print("[RubberDuck] winget install failed, trying Chocolatey...")

    choco = shutil.which("choco")
    if choco:
        try:
            _run_command([choco, "install", "ollama", "-y"])
            return True
        except subprocess.CalledProcessError:
            print("[RubberDuck] Chocolatey install failed.")

    print("[RubberDuck] Could not auto-install Ollama. Please install from https://ollama.com/download/windows")
    return False


def _start_ollama(ollama_cmd: str) -> bool:
    if _http_ok("http://127.0.0.1:11434/api/tags"):
        return True

    print("[RubberDuck] Starting Ollama...")
    try:
        subprocess.Popen(
            [ollama_cmd, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except OSError:
        return False

    # Wait up to 25s for API readiness
    for _ in range(25):
        if _http_ok("http://127.0.0.1:11434/api/tags"):
            return True
        time.sleep(1)

    return False


def _pull_model(ollama_cmd: str, model: str) -> bool:
    print(f"[RubberDuck] Ensuring Ollama model is available: {model}")
    try:
        _run_command([ollama_cmd, "pull", model])
        return True
    except subprocess.CalledProcessError:
        return False


def _bootstrap_ollama_and_model() -> None:
    ollama_cmd = _which_ollama()
    if not ollama_cmd:
        if not _install_ollama():
            return
        ollama_cmd = _which_ollama()
        if not ollama_cmd:
            print("[RubberDuck] Ollama install completed but binary was not found in PATH.")
            return

    if not _start_ollama(ollama_cmd):
        print("[RubberDuck] Unable to start Ollama automatically. Please run 'ollama serve' manually.")
        return

    model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    if not _pull_model(ollama_cmd, model):
        print(f"[RubberDuck] Failed to pull model '{model}'. You can run: ollama pull {model}")


def main() -> None:
    _set_runtime_paths()
    _set_working_directory()
    _bootstrap_ollama_and_model()

    host = os.getenv("RUBBERDUCK_HOST", "127.0.0.1")
    port = _pick_port(8000)

    from app import app
    import uvicorn

    if os.getenv("RUBBERDUCK_OPEN_BROWSER", "1") == "1":
        try:
            webbrowser.open(f"http://{host}:{port}")
        except Exception:
            pass

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
