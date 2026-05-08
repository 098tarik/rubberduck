# 🦆 rubberduck.ai

`rubberduck.ai` is a small local chat app that talks to an embedded `llama.cpp` model.
It gives you a simple web interface where you can ask questions, keep chat
history, switch models, render Markdown, and view code blocks with syntax
highlighting.

# Rubberduck Web Service
<img width="1137" height="505" alt="image" src="https://github.com/user-attachments/assets/42ab9679-80ea-450a-a4eb-374b9c7e08c4" />

# Rubberduck CLI
<img width="1011" height="383" alt="image" src="https://github.com/user-attachments/assets/3716a054-98e4-40ba-94b6-e8327cf83e49" />

## What this project does

- Runs a FastAPI server
- Starts a local bundled `llama.cpp` server
- Streams model responses to the browser
- Saves chat sessions locally
- Downloads one recommended GGUF model on first launch
- Shows responses in a clean web UI with no model picker

## Requirements

Before you start, make sure you have:

- Python 3.11+
- A `llama-server` binary available at `./runtime/llama-server` (or set `LLAMA_CPP_SERVER_BIN`)
- Internet access for first launch model download

## Run locally

### macOS

1. Install Python 3.11+ via [Homebrew](https://brew.sh):

```bash
brew install python@3.11
```

2. Clone the repository and install dependencies:

```bash
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

3. Start the app:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

4. Open `http://localhost:8000` in your browser.

---

### Linux

1. Install Python 3.11+ using your package manager, for example on Debian/Ubuntu:

```bash
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip -y
```

2. Clone the repository and install dependencies:

```bash
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

3. Start the app:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

4. Open `http://localhost:8000` in your browser.

---

### Windows

1. Download and install Python 3.11+ from [python.org](https://www.python.org/downloads/).
   Make sure to check **"Add Python to PATH"** during installation.

2. Clone the repository and install dependencies:

```powershell
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install .
```

   > If you see an execution-policy error, run:
   > `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

3. Start the app:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

4. Open `http://localhost:8000` in your browser.

---

On first launch, RubberDuck auto-detects your hardware and downloads exactly one recommended model.

## Configuration

The app uses these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLAMA_CPP_SERVER_BIN` | `./runtime/llama-server` | Path to bundled llama.cpp server binary |
| `LLAMA_SERVER_HOST` | `127.0.0.1` | Host for local llama.cpp server |
| `LLAMA_SERVER_PORT` | `8080` | Port for local llama.cpp server |
| `LLAMA_SERVER_URL` | `http://127.0.0.1:8080/v1` | OpenAI-compatible llama.cpp API base URL |
| `MODELS_DIR` | `./models` | Directory where first-launch model is downloaded |
| `SESSIONS_DIR` | current directory | Folder used to store chat history |

**macOS / Linux:**

```bash
export LLAMA_CPP_SERVER_BIN=./runtime/llama-server
export MODELS_DIR=./models
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Windows (PowerShell):**

```powershell
$env:LLAMA_CPP_SERVER_BIN = ".\runtime\llama-server.exe"
$env:MODELS_DIR = ".\models"
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Windows (Command Prompt):**

```cmd
set LLAMA_CPP_SERVER_BIN=.\runtime\llama-server.exe
set MODELS_DIR=.\models
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Run with Docker

Build the image:

```bash
docker build -f ci/Dockerfile -t rubberduck .
```

Run the container:

**macOS / Linux:**

```bash
docker run --rm -p 8000:8000 \
  -e LLAMA_CPP_SERVER_BIN=/app/runtime/llama-server \
  -e MODELS_DIR=/app/models \
  rubberduck
```

**Windows (PowerShell):**

```powershell
docker run --rm -p 8000:8000 `
  -e LLAMA_CPP_SERVER_BIN=/app/runtime/llama-server `
  -e MODELS_DIR=/app/models `
  rubberduck
```

Then open:

```text
http://localhost:8000
```

## CLI

A terminal chat client is also available. See [cli/README.md](cli/README.md) for installation and usage instructions.

## Project structure

- [main.py](main.py) - app entry point
- [app](app) - backend server code
- [assets](assets) - frontend CSS and JavaScript
- [index.html](index.html) - main web page
- [requirements.txt](requirements.txt) - Python dependencies
- [ci](ci) - container and deployment files
- [cli](cli) - terminal chat client

## Deploy from GitHub

This repo includes:

- [ci/Dockerfile](ci/Dockerfile)
- [ci/deployment.yaml](ci/deployment.yaml)
- [.github/workflows/deploy.yml](.github/workflows/deploy.yml)

If you want GitHub Actions to deploy this app for you, add these repository
secrets:

- `PI_HOST`
- `PI_USER`
- `PI_SSH_KEY`
- `TS_AUTHKEY`

Then pushing to `main` will:

1. Build the Docker image
2. Push it to GitHub Container Registry
3. Copy the deployment manifest to your server
4. Apply the Kubernetes deployment

## Manual deployment

If you want to deploy manually, edit the image in
[ci/deployment.yaml](ci/deployment.yaml) so it points to your container image,
for example:

```text
ghcr.io/your-user-or-org/your-repo:latest
```

Then apply it:

```bash
kubectl apply -f ci/deployment.yaml
```
