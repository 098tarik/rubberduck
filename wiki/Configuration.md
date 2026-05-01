# Configuration

RubberDuck is configured entirely through environment variables. There are no
config files to edit.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Base URL of the Ollama server |
| `OLLAMA_MODEL` | `deepseek-r1:8b` | Default model selected on page load |
| `SESSIONS_DIR` | `./sessions` | Directory where chat transcripts are saved |
| `TELEMETRY_LOG` | `./telemetry.jsonl` | Path of the newline-delimited JSON telemetry file |

## Setting variables

### Inline (single run)

```bash
OLLAMA_URL=http://192.168.1.10:11434 \
OLLAMA_MODEL=llama3:8b \
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Exported in your shell

```bash
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=deepseek-r1:8b
export SESSIONS_DIR=/var/lib/rubberduck/sessions
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker

Pass variables with `-e` flags:

```bash
docker run --rm -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=deepseek-r1:8b \
  rubberduck
```

### Kubernetes

Set them in the `env` section of `ci/deployment.yaml`:

```yaml
env:
  - name: OLLAMA_URL
    value: "http://ollama-service:11434"
  - name: OLLAMA_MODEL
    value: "deepseek-r1:8b"
```

## Connecting to a remote Ollama instance

Set `OLLAMA_URL` to any reachable Ollama endpoint:

```bash
export OLLAMA_URL=http://my-gpu-server:11434
```

Make sure the remote machine allows connections on port `11434` and has the
desired model pulled.

## Session storage

Chat transcripts are stored as JSON files in `SESSIONS_DIR`. Each file is named
after the session UUID (e.g. `550e8400-e29b-41d4-a716-446655440000.json`).

The directory is created automatically on startup if it does not exist.
Sessions are capped at the 100 most recent messages to keep files small.

## See also

- [Memory](Memory) — `RUBBERDUCK.md` custom instructions
- [Telemetry](Telemetry) — what is written to `TELEMETRY_LOG`
