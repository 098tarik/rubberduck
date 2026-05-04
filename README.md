# 🦆 rubberduck.ai

`rubberduck.ai` is a small local chat app that talks to an Ollama model.
It gives you a simple web interface where you can ask questions, keep chat
history, switch models, render Markdown, and view code blocks with syntax
highlighting.

# Rubberduck Web Service
<img width="1137" height="505" alt="image" src="https://github.com/user-attachments/assets/42ab9679-80ea-450a-a4eb-374b9c7e08c4" />

# Rubberduck CLI
<img width="1011" height="383" alt="image" src="https://github.com/user-attachments/assets/3716a054-98e4-40ba-94b6-e8327cf83e49" />

## What this project does

- Runs a FastAPI server
- Connects to a local Ollama instance
- Streams model responses to the browser
- Saves chat sessions locally
- Shows responses in a clean web UI

## Requirements

Before you start, make sure you have:

- Python 3.11+
- [Ollama](https://ollama.com/download) installed and running
- At least one Ollama model pulled locally

## Run locally

### macOS

1. Install Python 3.11+ via [Homebrew](https://brew.sh):

```bash
brew install python@3.11
```

2. Install [Ollama](https://ollama.com/download) and pull a model:

```bash
brew install ollama
ollama serve &
ollama pull deepseek-r1:8b
```

3. Clone the repository and install dependencies:

```bash
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

4. Start the app:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

5. Open `http://localhost:8000` in your browser.

---

### Linux

1. Install Python 3.11+ using your package manager, for example on Debian/Ubuntu:

```bash
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip -y
```

2. Install [Ollama](https://ollama.com/download):

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull deepseek-r1:8b
```

3. Clone the repository and install dependencies:

```bash
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
python3 -m venv .venv && source .venv/bin/activate
pip install .
```

4. Start the app:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

5. Open `http://localhost:8000` in your browser.

---

### Windows

1. Download and install Python 3.11+ from [python.org](https://www.python.org/downloads/).
   Make sure to check **"Add Python to PATH"** during installation.

2. Download and install [Ollama for Windows](https://ollama.com/download/windows).
   Ollama starts automatically after installation.

3. Open **PowerShell** and pull a model:

```powershell
ollama pull deepseek-r1:8b
```

4. Clone the repository and install dependencies:

```powershell
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install .
```

   > If you see an execution-policy error, run:
   > `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

5. Start the app:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

6. Open `http://localhost:8000` in your browser.

---

Any model from the [Ollama library](https://ollama.com/library) works. Smaller
models (≤ 8 B parameters) respond faster on consumer hardware.

## Configuration

The app uses these environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | URL of your Ollama server |
| `OLLAMA_MODEL` | `deepseek-r1:8b` | Default model to use |
| `SESSIONS_DIR` | current directory | Folder used to store chat history |

**macOS / Linux:**

```bash
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=deepseek-r1:8b
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Windows (PowerShell):**

```powershell
$env:OLLAMA_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "deepseek-r1:8b"
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Windows (Command Prompt):**

```cmd
set OLLAMA_URL=http://localhost:11434
set OLLAMA_MODEL=deepseek-r1:8b
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
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=deepseek-r1:8b \
  rubberduck
```

**Windows (PowerShell):**

```powershell
docker run --rm -p 8000:8000 `
  -e OLLAMA_URL=http://host.docker.internal:11434 `
  -e OLLAMA_MODEL=deepseek-r1:8b `
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
