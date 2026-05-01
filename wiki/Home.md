# 🦆 RubberDuck Wiki

Welcome to the RubberDuck wiki. RubberDuck is a lightweight local chat app that
connects your browser to a locally running [Ollama](https://ollama.com) model.
You get a clean web interface with chat history, model switching, Markdown
rendering, and syntax-highlighted code blocks — all without sending your data to
the cloud.

## Pages

| Page | Description |
|------|-------------|
| [Getting Started](Getting-Started) | Install dependencies and run the app for the first time |
| [Configuration](Configuration) | Environment variables that control app behaviour |
| [Architecture](Architecture) | Code layout, data flow, and design decisions |
| [API Reference](API-Reference) | REST endpoints exposed by the FastAPI server |
| [Deployment](Deployment) | Run with Docker or deploy to Kubernetes |
| [Memory](Memory) | Persist custom instructions via `RUBBERDUCK.md` |
| [Telemetry](Telemetry) | Local usage logging with JSONL telemetry |

## Quick start

```bash
# 1. Pull a model
ollama pull deepseek-r1:8b

# 2. Install Python deps
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 4. Open in browser
open http://localhost:8000
```

## Project links

- [Source code](https://github.com/098tarik/rubberduck)
- [README](https://github.com/098tarik/rubberduck/blob/main/README.md)
- [Open an issue](https://github.com/098tarik/rubberduck/issues)
