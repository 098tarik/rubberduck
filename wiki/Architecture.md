# Architecture

This page describes how RubberDuck is structured, how data flows through the
system, and the design decisions behind the code.

## Repository layout

```
rubberduck/
├── main.py              # App entry point (imports app from the app package)
├── index.html           # Single-page frontend
├── assets/              # Frontend CSS and JavaScript
├── app/
│   ├── __init__.py      # FastAPI app factory, router registration
│   ├── config.py        # Environment variable parsing
│   ├── context.py       # System prompt builder (reads RUBBERDUCK.md)
│   ├── history.py       # Session persistence (load / save / list)
│   ├── messages.py      # Pydantic models: UserMessage, AssistantMessage
│   ├── query_engine.py  # Chat loop: builds Ollama payload, streams SSE
│   ├── telemetry.py     # Append-only JSONL usage log
│   ├── tools.py         # Abstract Tool base class
│   └── routes/
│       ├── chat.py      # POST /chat
│       ├── models.py    # GET /models
│       └── sessions.py  # GET /sessions, GET /sessions/{id}
├── ci/
│   ├── Dockerfile
│   └── deployment.yaml
└── tests/
```

## Request lifecycle

```
Browser
  │
  │  POST /chat  { session_id?, model?, message }
  ▼
chat.py (route)
  │  creates QueryEngine(session_id, model)
  │
  ▼
query_engine.py
  │  loads history from disk
  │  appends UserMessage
  │  builds system prompt (context.py)
  │  POSTs to Ollama /api/chat  (streaming)
  │
  ▼
Ollama (local)
  │  streams JSON lines
  │
  ▼
query_engine.py
  │  converts each line to an SSE frame  →  yields to StreamingResponse
  │  on done: appends AssistantMessage, saves session
  │
  ▼
Browser
  receives  data: {"text": "..."}  frames
  renders Markdown in real-time
```

## Key components

### `QueryEngine`

`app/query_engine.py` is the heart of the app. For each incoming chat request
it:

1. Loads the stored message history for the session.
2. Appends the new user message and persists it immediately.
3. Builds the Ollama request: a system prompt from `context.py` followed by the
   full conversation history.
4. Opens a streaming HTTP connection to Ollama and yields SSE frames to the
   browser as they arrive.
5. Once streaming is complete, appends the assembled assistant reply and saves
   the session again.

### `history.py`

Stateless helpers that read and write JSON files in `SESSIONS_DIR`. Sessions are
stored as plain lists of message objects. The 100-message cap is enforced on
every write.

### `context.py`

Builds the system prompt sent with every Ollama request. It always includes the
current UTC time and, if the file `RUBBERDUCK.md` exists in the working
directory, appends its contents as a **Memory** block. See [Memory](Memory) for
details.

### `messages.py`

Pydantic models for `UserMessage` and `AssistantMessage`. Both carry an `id`
(UUID) and a `timestamp` (ISO 8601 UTC) generated at creation time.

### `telemetry.py`

Thin append-only logger. Every meaningful action (chat started, chat completed,
models listed, etc.) is written as a JSON object to `TELEMETRY_LOG`. The module
never raises — logging failures are caught and emitted as Python warnings only.

### `tools.py`

Defines an abstract `Tool` base class for future tool-use / function-calling
support.

## Frontend

`index.html` and `assets/` implement a single-page app with no build step. The
frontend:

- fetches available models from `GET /models` on load
- posts messages to `POST /chat` and reads the SSE stream
- renders assistant responses using a Markdown library with syntax highlighting
- maintains a sidebar showing previous sessions fetched from `GET /sessions`

## Data flow diagram

```
┌─────────────┐    HTTP/SSE    ┌──────────────────┐    HTTP    ┌────────────┐
│   Browser   │◄──────────────►│  FastAPI server  │◄──────────►│   Ollama   │
│ index.html  │                │  (uvicorn)       │            │ (local)    │
└─────────────┘                └──────────────────┘            └────────────┘
                                        │
                                        │ JSON files
                                        ▼
                               ┌──────────────────┐
                               │  SESSIONS_DIR/   │
                               │  *.json          │
                               └──────────────────┘
```
