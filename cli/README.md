# 🦆 rubberduck CLI

A barebones terminal chat client for [Ollama](https://ollama.com), inspired by
the GitHub Copilot CLI.  No web server, no browser — just a prompt.

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) installed and running with at least one model

```bash
ollama pull deepseek-r1:8b
```

## Install

```bash
cd cli
pip install -e .
```

## Usage

### Interactive REPL

```bash
duck
```

```
🦆 RubberDuck CLI  (model: deepseek-r1:8b  session: a3f2c1b0)
Type /quit to exit, /new for a new session, or /help for commands.

you> explain recursion in one sentence
🦆  Recursion is when a function calls itself to solve smaller instances of the
    same problem until it reaches a base case.

you>
```

### Single-shot prompt

```bash
duck "what is the airspeed velocity of an unladen swallow?"
```

## Commands

| Command | Description |
|---------|-------------|
| `/new` | Start a new session (clears history) |
| `/model <name>` | Switch to a different Ollama model |
| `/history` | Print all messages in the current session |
| `/help` | Show command list |
| `/quit` | Exit |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `deepseek-r1:8b` | Default model |
| `SESSIONS_DIR` | `~/.rubberduck/sessions` | Where sessions are saved |

```bash
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=llama3
duck
```
