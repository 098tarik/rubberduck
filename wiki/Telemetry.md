# Telemetry

RubberDuck records lightweight, **local-only** usage events to a
newline-delimited JSON file (`telemetry.jsonl` by default). No data is sent to
any external service.

## Log location

The file path is controlled by the `TELEMETRY_LOG` environment variable:

```bash
export TELEMETRY_LOG=/var/log/rubberduck/telemetry.jsonl
```

Default: `./telemetry.jsonl` (relative to the working directory).

## Record format

Each line is a JSON object with at least two fields:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `string` | ISO 8601 UTC timestamp of the event |
| `event` | `string` | Snake-case event name |

Additional fields depend on the event type (see below).

### Example record

```json
{"timestamp": "2024-06-01T12:34:05.123456+00:00", "event": "chat_completed", "session_id": "550e8400-e29b-41d4-a716-446655440000", "model": "deepseek-r1:8b"}
```

## Recorded events

| Event | Extra fields | Description |
|-------|-------------|-------------|
| `chat_started` | `session_id`, `model`, `new_session`, `message_length` | A `/chat` request was received |
| `chat_completed` | `session_id`, `model` | The model finished streaming a response |
| `chat_error` | `session_id`, `model`, `reason` | An error occurred during a chat request |
| `models_listed` | `count` | `GET /models` returned successfully |
| `models_listed_error` | `reason` | `GET /models` could not reach Ollama |
| `sessions_listed` | `count` | `GET /sessions` was called |
| `session_viewed` | `session_id`, `message_count` | `GET /sessions/{id}` was called |

## Querying the log

Because each line is valid JSON, you can use
[`jq`](https://jqlang.github.io/jq/) to analyse the file.

```bash
# Count events by type
jq -r '.event' telemetry.jsonl | sort | uniq -c | sort -rn

# Show all chat_completed events
jq 'select(.event == "chat_completed")' telemetry.jsonl

# Count chats per model
jq -r 'select(.event == "chat_completed") | .model' telemetry.jsonl \
  | sort | uniq -c | sort -rn

# Show errors
jq 'select(.event == "chat_error")' telemetry.jsonl

# Sessions created today (UTC)
jq -r 'select(.event == "chat_started" and .new_session == true) | .timestamp' \
  telemetry.jsonl | grep "^$(date -u +%Y-%m-%d)"
```

## Error handling

The telemetry module never raises an exception. If the log file cannot be
written (for example due to a permissions error), a Python warning is emitted
and execution continues normally.

## Disabling telemetry

There is no built-in toggle, but you can point `TELEMETRY_LOG` at `/dev/null`
to suppress all writes:

```bash
export TELEMETRY_LOG=/dev/null
```
