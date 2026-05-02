# 🦆 rubberduck.ai

`rubberduck.ai` is a small local chat app that talks to an Ollama model.
It gives you a simple web interface where you can ask questions, keep chat
history, switch models, render Markdown, and view code blocks with syntax
highlighting.

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

1. Clone the repository:

```bash
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
```

2. Install and start Ollama, then pull a model:

```bash
ollama pull deepseek-r1:8b
```

Any model from the [Ollama library](https://ollama.com/library) works. Smaller
models (≤ 8 B parameters) respond faster on consumer hardware.

3. Install Python dependencies:

```bash
pip install .
```

4. Start the app:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

5. Open the app in your browser:

```text
http://localhost:8000
```

## Configuration

The app uses these environment variables:

- `OLLAMA_URL` - URL of your Ollama server
- `OLLAMA_MODEL` - default model to use
- `SESSIONS_DIR` - folder used to store chat history

Example:

```bash
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=deepseek-r1:8b
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Run with Docker

Build the image:

```bash
docker build -f ci/Dockerfile -t rubberduck .
```

Run the container:

```bash
docker run --rm -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=deepseek-r1:8b \
  rubberduck
```

Then open:

```text
http://localhost:8000
```

## Project structure

- [main.py](main.py) - app entry point
- [app](app) - backend server code
- [assets](assets) - frontend CSS and JavaScript
- [index.html](index.html) - main web page
- [requirements.txt](requirements.txt) - Python dependencies
- [ci](ci) - container and deployment files

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
