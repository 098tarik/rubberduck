# Getting Started

This page walks you through installing RubberDuck and chatting with your first
local model.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.11+** | Earlier versions are not supported |
| **Ollama** | Must be installed and running locally |
| **At least one model** | Pull a model with `ollama pull <name>` |

### Install Ollama

Follow the instructions at <https://ollama.com/download> for your operating
system, then verify it is running:

```bash
ollama list
```

### Pull a model

```bash
ollama pull deepseek-r1:8b
```

Any model available on the [Ollama library](https://ollama.com/library) works.
Smaller models (≤ 8 B parameters) respond faster on consumer hardware.

## Install RubberDuck

```bash
git clone https://github.com/098tarik/rubberduck.git
cd rubberduck
pip install -r requirements.txt
```

## Run the server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open <http://localhost:8000> in your browser.

## First chat

1. The model picker at the top of the page shows all models pulled into Ollama.
2. Select a model, type a message, and press **Enter** or click **Send**.
3. The assistant streams its reply word-by-word directly in the browser.
4. Your conversation is saved automatically and appears in the session list on
   the left.

## Switching models mid-conversation

You can change the model between messages using the dropdown. Each message is
sent with whichever model is currently selected, so you can compare models
within the same session.

## Starting a new session

Click **New chat** in the sidebar to start a fresh conversation. Previous
sessions are preserved and can be reopened at any time.

## Next steps

- [Configuration](Configuration) — change the Ollama URL, default model, or
  storage paths
- [Memory](Memory) — give RubberDuck persistent instructions via `RUBBERDUCK.md`
- [Deployment](Deployment) — run with Docker or deploy to Kubernetes
