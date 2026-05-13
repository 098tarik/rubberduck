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
OLLAMA_SETTLE_DELAY_SECONDS = 0.2
PROCESS_OUTPUT_LOG_LIMIT = 2_000
OLLAMA_DIAGNOSTIC_TIMEOUT_SECONDS = 3.0
OLLAMA_DIAGNOSTIC_POLL_INTERVAL_SECONDS = 0.1


def _local_app_data_dir() -> pathlib.Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return pathlib.Path(local_app_data)
    fallback = pathlib.Path.home() / "AppData" / "Local"
    print(f"[RubberDuck] Warning: LOCALAPPDATA not set, using fallback path: {fallback}")
    LOGGER.warning("LOCALAPPDATA was not set; using fallback directory %s", fallback)
    return fallback


def _configure_file_logging() -> pathlib.Path:
    local_app_data = _local_app_data_dir()
    app_home = local_app_data / "RubberDuck"
    app_home.mkdir(parents=True, exist_ok=True)

    log_path = pathlib.Path(
        os.getenv("RUBBERDUCK_LOG", str(app_home / "rubberduck.log"))
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("rubberduck")
    resolved_log_path = log_path.resolve()
    if not any(
        isinstance(handler, RotatingFileHandler)
        and pathlib.Path(handler.baseFilename).resolve() == resolved_log_path
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
    local_app_data = _local_app_data_dir()
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


def _collect_ollama_startup_diagnostics(ollama_cmd: str) -> tuple[str, str]:
    """Try one short-lived foreground run to capture immediate startup errors.

    If the process exits within OLLAMA_DIAGNOSTIC_TIMEOUT_SECONDS its stdout/stderr
    are returned for error logging.  If the process is *still alive* after the
    timeout it is left running — it may have become the actual server — and empty
    strings are returned so the caller can re-check _ollama_is_running().
    """
    def _as_text(value: str | bytes | None) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value or ""

    try:
        proc = subprocess.Popen(
            [ollama_cmd, "serve"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError:
        LOGGER.exception("Failed to execute Ollama diagnostic command.")
        return "", ""

    leave_running = False
    try:
        deadline = time.monotonic() + OLLAMA_DIAGNOSTIC_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                # Exited quickly — drain pipes with a safety timeout to avoid
                # blocking on unexpectedly large buffered output.
                try:
                    stdout, stderr = proc.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, stderr = proc.communicate()
                return _as_text(stdout).strip(), _as_text(stderr).strip()
            time.sleep(OLLAMA_DIAGNOSTIC_POLL_INTERVAL_SECONDS)

        # Still alive after the timeout window — the process likely started
        # successfully.  Leave it running so it can serve requests; the caller
        # will re-check _ollama_is_running() before declaring failure.
        leave_running = True
        LOGGER.warning(
            "Ollama diagnostic did not exit within %.1fs; process appears healthy "
            "and will continue running as the server.",
            OLLAMA_DIAGNOSTIC_TIMEOUT_SECONDS,
        )
        return "", ""
    except Exception:
        if not leave_running:
            proc.kill()
        raise


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
        running = _ollama_is_running()
        if running:
            LOGGER.info("Ollama service became ready on attempt %s.", attempt)
            return True
        if process.poll() is not None:
            # If another Ollama instance is already serving, treat startup as healthy.
            if _ollama_is_running():
                # 0.2 seconds is enough to avoid transient false positives right after
                # process exit without slowing startup in the common case.
                time.sleep(OLLAMA_SETTLE_DELAY_SECONDS)
                if _ollama_is_running():
                    LOGGER.info(
                        "Spawned ollama process exited early on attempt %s, but service is already reachable.",
                        attempt,
                    )
                    return True
            LOGGER.warning(
                "Spawned ollama process exited early with code %s (attempt %s).",
                process.returncode,
                attempt,
            )
            stdout_text, stderr_text = _collect_ollama_startup_diagnostics(ollama_cmd)
            if stdout_text:
                LOGGER.error(
                    "Ollama diagnostic stdout: %s",
                    stdout_text[:PROCESS_OUTPUT_LOG_LIMIT],
                )
            if stderr_text:
                LOGGER.error(
                    "Ollama diagnostic stderr: %s",
                    stderr_text[:PROCESS_OUTPUT_LOG_LIMIT],
                )
            if not stdout_text and not stderr_text:
                LOGGER.warning(
                    "No diagnostic output captured; the diagnostic process may have started "
                    "successfully. Rechecking service reachability."
                )
            # The diagnostic probe may have become the running server (transient
            # crash on the original process, successful restart during diagnostics).
            time.sleep(OLLAMA_SETTLE_DELAY_SECONDS)
            if _ollama_is_running():
                LOGGER.info(
                    "Ollama service became reachable after diagnostic probe; "
                    "treating startup as successful."
                )
                return True
            LOGGER.error(
                "Spawned ollama process exited and service is still unreachable after "
                "diagnostic; check manual command: \"%s serve\"",
                ollama_cmd,
            )
            return False
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

    LOGGER.info("Starting uvicorn. Log file: %s", log_path)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
