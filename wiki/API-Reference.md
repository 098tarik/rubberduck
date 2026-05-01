# API Reference

RubberDuck exposes a small REST API served by FastAPI. All endpoints return JSON
unless otherwise noted.

The interactive API docs (Swagger UI) are available at
`http://localhost:8000/docs` when the server is running.

---

## `POST /chat`

Start or continue a chat session. The response is a
[Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
stream.

### Request body

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "deepseek-r1:8b",
  "message": "Explain bubble sort in plain English."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | `string` | ✅ | The user's message |
| `session_id` | `string` | No | UUID of an existing session. Omit to start a new session |
| `model` | `string` | No | Ollama model name. Falls back to `OLLAMA_MODEL` if omitted |

### Response headers

| Header | Description |
|--------|-------------|
| `X-Session-Id` | UUID of the session (new or existing) |
| `Content-Type` | `text/event-stream` |

### SSE frames

Each frame is a `data:` line followed by two newlines.

**Text chunk** — sent while the model is generating:

```
data: {"text": "Bubble sort is..."}
```

**Done** — sent once when generation is complete:

```
data: [DONE]
```

**Error** — sent if an unexpected error occurs:

```
data: {"error": "An unexpected error occurred."}
```

### Error responses

| Status | Reason |
|--------|--------|
| `400` | A `:cloud`-suffixed model name was provided. Only local Ollama models are supported |

---

## `GET /models`

Return the list of models available in the local Ollama instance.

### Response

```json
{
  "models": ["deepseek-r1:8b", "llama3:8b"],
  "default": "deepseek-r1:8b"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `models` | `string[]` | All locally available model names |
| `default` | `string` | Value of the `OLLAMA_MODEL` environment variable |
| `error` | `string` | Present only if Ollama could not be reached |

---

## `GET /sessions`

Return lightweight metadata for every persisted chat session, sorted by most
recently updated first.

### Response

```json
{
  "sessions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "preview": "Explain bubble sort in plain English.",
      "updated_at": "2024-06-01T12:34:56.789+00:00"
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Session UUID |
| `preview` | `string` | First 80 characters of the first user message, or `"(empty)"` |
| `updated_at` | `string` | ISO 8601 UTC timestamp of the last write |

---

## `GET /sessions/{session_id}`

Return the full stored transcript for one session.

### Path parameters

| Parameter | Description |
|-----------|-------------|
| `session_id` | UUID of the session |

### Response

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "id": "a1b2c3d4-...",
      "timestamp": "2024-06-01T12:34:00.000+00:00",
      "role": "user",
      "content": "Explain bubble sort in plain English."
    },
    {
      "id": "e5f6a7b8-...",
      "timestamp": "2024-06-01T12:34:05.123+00:00",
      "role": "assistant",
      "content": "Bubble sort is a simple sorting algorithm..."
    }
  ]
}
```

### Error responses

| Status | Reason |
|--------|--------|
| `404` | No session with the given ID exists |
