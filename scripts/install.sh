#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"

say() {
  printf "\n==> %s\n" "$1"
}

warn() {
  printf "\n[warning] %s\n" "$1"
}

die() {
  printf "\n[error] %s\n" "$1" >&2
  exit 1
}

require_python() {
  command -v python3 >/dev/null 2>&1 || die "python3 is required (Python 3.11+)."
  local version
  version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  local major minor
  major="${version%%.*}"
  minor="${version##*.}"
  if (( major < 3 || (major == 3 && minor < 11) )); then
    die "Python ${version} detected. Python 3.11+ is required."
  fi
}

setup_venv() {
  if [[ ! -d "${VENV_DIR}" ]]; then
    say "Creating virtual environment at ${VENV_DIR}"
    python3 -m venv "${VENV_DIR}"
  else
    say "Using existing virtual environment at ${VENV_DIR}"
  fi

  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
}

check_ollama() {
  if ! command -v ollama >/dev/null 2>&1; then
    warn "Ollama is not installed. Install it from https://ollama.com/download before running chats."
    return
  fi

  if ! ollama list >/dev/null 2>&1; then
    warn "Ollama is installed but not running. Start it with: ollama serve"
    return
  fi

  local model_count
  model_count="$(ollama list | tail -n +2 | sed '/^\s*$/d' | wc -l | tr -d ' ')"
  if [[ "${model_count}" == "0" ]]; then
    warn "No Ollama models found. Pull one with: ollama pull deepseek-r1:8b"
  fi
}

main() {
  say "RubberDuck installer"
  require_python
  check_ollama

  setup_venv

  say "Upgrading pip"
  python -m pip install --upgrade pip

  say "Installing RubberDuck"
  (
    cd "${ROOT_DIR}"
    python -m pip install .
  )

  say "Installation complete"
  cat <<'EOF'
Next steps:
1) Activate the virtualenv (if not already active):
   source .venv/bin/activate
2) Start the app:
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
3) Open:
   http://localhost:8000
EOF
}

main "$@"
