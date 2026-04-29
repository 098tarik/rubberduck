# 🦆 rubberduck.ai

Local AI chat assistant powered by FastAPI, Ollama, and a small web UI.

## Quick Start

```bash
python3 -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000

## Docker

```bash
docker build -f ci/Dockerfile -t rubberduck .
docker run --rm -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=deepseek-r1:8b \
  rubberduck
```

## GitHub Packaging

This repository is now structured for GitHub-based builds and deployment:

- Docker build config: [ci/Dockerfile](ci/Dockerfile)
- Python dependencies: [requirements.txt](requirements.txt)
- GitHub Actions workflow: [.github/workflows/deploy.yml](.github/workflows/deploy.yml)
- Kubernetes manifest template: [ci/deployment.yaml](ci/deployment.yaml)

## GitHub Secrets Required

Add these repository secrets before enabling the workflow:

- `PI_HOST`
- `PI_USER`
- `PI_SSH_KEY`
- `TS_AUTHKEY`

## Deploy to K3s via GitHub Actions

Push to `main` and the workflow will:

1. Build the Docker image.
2. Push it to GitHub Container Registry.
3. Connect to your Pi over Tailscale.
4. Apply the Kubernetes deployment.

## Manual Kubernetes Manifest

If you want to deploy manually, update the image in [ci/deployment.yaml](ci/deployment.yaml)
to your actual GitHub Container Registry path, for example:

```text
ghcr.io/your-user-or-org/your-repo:latest
```

Then apply it:

```bash
kubectl apply -f ci/deployment.yaml
```
