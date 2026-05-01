# Memory

RubberDuck supports a simple **memory** mechanism: a plain Markdown file called
`RUBBERDUCK.md` that is automatically injected into every system prompt.

## How it works

On every chat request, `app/context.py` checks whether a file named
`RUBBERDUCK.md` exists in the current working directory. If it does, the file's
contents are appended to the system prompt that is sent to Ollama:

```
You are RubberDuck, a helpful and friendly AI assistant. Keep responses concise and helpful.
Current date/time (UTC): 2024-06-01 12:00

--- Memory (RUBBERDUCK.md) ---
<contents of RUBBERDUCK.md>
```

This means the model sees your custom instructions on every turn of every
conversation.

## Creating the memory file

Create `RUBBERDUCK.md` in the same directory where you run `uvicorn`:

```bash
cat > RUBBERDUCK.md << 'EOF'
## My preferences

- Always respond in British English.
- Format code examples using Python unless I specify otherwise.
- When explaining a concept, give a one-sentence summary first.
EOF
```

The file is read fresh on each request, so changes take effect immediately
without restarting the server.

## What to put in RUBBERDUCK.md

The memory file is freeform Markdown. Useful things to include:

- **Personal preferences** — tone, language, response length
- **Project context** — the programming language and frameworks you use, naming
  conventions, architecture notes
- **Recurring facts** — your name, role, or anything you often have to repeat
- **Behavioural rules** — "Always show the full file when editing code", "Never
  use abbreviations"

## Example

```markdown
## About me
I am a Python backend developer working on a FastAPI service.

## Preferences
- Keep answers concise; expand only when I ask for more detail.
- Default to Python 3.12 idioms.
- Use type hints in all code examples.

## Project context
The service uses PostgreSQL via asyncpg, Redis for caching, and Celery for
background tasks. Deployments target Kubernetes on GKE.
```

## Disabling memory

Simply delete or rename `RUBBERDUCK.md`. If the file does not exist, the system
prompt is sent without a memory block.

## Docker and Kubernetes

When running in a container, mount `RUBBERDUCK.md` as a volume:

```bash
docker run --rm -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -v $(pwd)/RUBBERDUCK.md:/app/RUBBERDUCK.md:ro \
  rubberduck
```

In Kubernetes, use a `ConfigMap`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rubberduck-memory
data:
  RUBBERDUCK.md: |
    ## Project context
    We build microservices with Go and deploy on AWS EKS.
```

Then mount it in the deployment:

```yaml
volumeMounts:
  - name: memory
    mountPath: /app/RUBBERDUCK.md
    subPath: RUBBERDUCK.md
volumes:
  - name: memory
    configMap:
      name: rubberduck-memory
```
