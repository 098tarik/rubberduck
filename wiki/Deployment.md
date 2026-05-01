# Deployment

RubberDuck ships with a `Dockerfile` and a Kubernetes `deployment.yaml` so you
can move from a local `uvicorn` process to a containerised deployment with
minimal effort.

---

## Docker

### Build the image

```bash
docker build -f ci/Dockerfile -t rubberduck .
```

### Run the container

```bash
docker run --rm -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=deepseek-r1:8b \
  rubberduck
```

> **Note:** `host.docker.internal` resolves to the host machine inside Docker
> on macOS and Windows. On Linux, use `--network=host` or the host's LAN IP
> instead.

Open <http://localhost:8000> in your browser.

### Persist sessions between container restarts

Mount a host directory into the container:

```bash
docker run --rm -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=deepseek-r1:8b \
  -v /var/lib/rubberduck/sessions:/app/sessions \
  rubberduck
```

---

## GitHub Actions (automated)

The repository includes `.github/workflows/deploy.yml`. When you push to
`main` it will:

1. Build the Docker image.
2. Push it to GitHub Container Registry (`ghcr.io`).
3. Copy `ci/deployment.yaml` to your server over SSH.
4. Apply the manifest with `kubectl`.

### Required repository secrets

| Secret | Description |
|--------|-------------|
| `PI_HOST` | Hostname or IP of your deployment server |
| `PI_USER` | SSH username |
| `PI_SSH_KEY` | Private SSH key (the public key must be authorised on the server) |
| `TS_AUTHKEY` | Tailscale auth key (used to connect the runner to your private network) |

Add these under **Settings → Secrets and variables → Actions** in your GitHub
repository.

---

## Kubernetes (manual)

Edit `ci/deployment.yaml` and set the image to your registry path:

```yaml
image: ghcr.io/your-user-or-org/rubberduck:latest
```

Apply the manifest:

```bash
kubectl apply -f ci/deployment.yaml
```

### Environment variables in the manifest

```yaml
env:
  - name: OLLAMA_URL
    value: "http://ollama-service:11434"
  - name: OLLAMA_MODEL
    value: "deepseek-r1:8b"
  - name: SESSIONS_DIR
    value: "/data/sessions"
```

Mount a `PersistentVolumeClaim` at `/data/sessions` to keep session history
across pod restarts.

---

## Connecting to Ollama

RubberDuck needs to reach an Ollama server. Common setups:

| Scenario | `OLLAMA_URL` |
|----------|--------------|
| Ollama on the same machine (bare metal) | `http://localhost:11434` |
| Ollama on the host from Docker | `http://host.docker.internal:11434` |
| Ollama as a separate Kubernetes service | `http://ollama-service:11434` |
| Ollama on a remote GPU server | `http://192.168.1.50:11434` |

---

## See also

- [Configuration](Configuration) — full list of environment variables
- [Getting Started](Getting-Started) — run locally without Docker
