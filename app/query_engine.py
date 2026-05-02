"""Session-scoped query engine for streaming chat responses."""

import asyncio
from collections.abc import AsyncIterator
import json

import httpx

from app import config, context, history, messages


STREAM_STATUS_LABELS = {
    "preparing": "Preparing context...",
    "connecting": "Contacting Ollama...",
    "waiting": "Waiting for first token...",
    "responding": "Streaming response...",
}

MEMORY_ERROR_FRAGMENT = "model requires more system memory"


class QueryEngine:
    """Manage chat history and stream responses from Ollama."""

    def __init__(self, session_id: str, model: str = config.DEFAULT_MODEL):
        """Initialize a query engine for a single session."""
        self.session_id = session_id
        self.model = model
        self._messages: history.SessionMessages = history.load_session(session_id)

    def append(self, message: dict[str, object]) -> None:
        """Append a message and immediately persist session history."""
        self._messages.append(message)
        history.save_session(self.session_id, self._messages)

    def get_history(self) -> history.SessionMessages:
        """Return a shallow copy of the current session history."""
        return list(self._messages)

    @staticmethod
    def _status_frame(
        phase: str,
        *,
        label: str | None = None,
        model: str | None = None,
        requested_model: str | None = None,
        reason: str | None = None,
    ) -> str:
        """Build an SSE frame that describes the current streaming phase."""
        status_payload: dict[str, str] = {
            "phase": phase,
            "label": label or STREAM_STATUS_LABELS[phase],
        }
        if model is not None:
            status_payload["model"] = model
        if requested_model is not None:
            status_payload["requested_model"] = requested_model
        if reason is not None:
            status_payload["reason"] = reason

        return (
            "data: "
            + json.dumps(
                {
                    "status": status_payload,
                }
            )
            + "\n\n"
        )

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract the most useful Ollama error message from a failed response."""
        raw_text = response.text
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return raw_text

        return str(payload.get("error") or raw_text)

    @staticmethod
    def _is_memory_pressure_error(error_text: str) -> bool:
        """Return True when Ollama reports the model will not fit in RAM."""
        return MEMORY_ERROR_FRAGMENT in error_text.lower()

    @staticmethod
    def _local_models_from_payload(payload: dict[str, object]) -> list[dict[str, object]]:
        """Extract local Ollama models sorted from smallest to largest."""
        local_models: list[dict[str, object]] = []
        for item in payload.get("models", []):
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            if not isinstance(name, str) or not name or name.endswith(":cloud"):
                continue
            size = item.get("size")
            local_models.append(
                {
                    "name": name,
                    "size": size if isinstance(size, int) else 0,
                }
            )

        return sorted(local_models, key=lambda item: (item["size"], item["name"]))

    async def _find_smaller_model(
        self,
        client: httpx.AsyncClient,
        current_model: str,
    ) -> str | None:
        """Return the next smaller installed local model, if one exists."""
        response = await client.get(f"{config.OLLAMA_URL}/api/tags", timeout=10.0)
        response.raise_for_status()
        models = self._local_models_from_payload(response.json())

        current_entry = next(
            (item for item in models if item["name"] == current_model),
            None,
        )
        if current_entry is not None:
            for item in models:
                if item["name"] != current_model and item["size"] < current_entry["size"]:
                    return str(item["name"])

        for item in models:
            if item["name"] != current_model:
                return str(item["name"])

        return None

    async def query(
        self,
        user_content: str,
        abort_event: asyncio.Event | None = None,
    ) -> AsyncIterator[str]:
        """Stream a single assistant response as Server-Sent Events.

        Args:
            user_content: The newest user message to append to the session.
            abort_event: Optional event that, when set, cancels the in-flight
                request after the current streaming chunk.

        Yields:
            SSE data frames containing streamed text chunks or an error payload.
        """
        user_msg = messages.UserMessage(content=user_content)
        self.append(user_msg.model_dump())

        system_context = context.build_system_context()
        ollama_messages = self._build_ollama_messages(system_context)

        full_text = ""
        aborted = False
        yielded_response_status = False
        try:
            yield self._status_frame("preparing")
            async with httpx.AsyncClient() as client:
                active_model = self.model
                tried_fallback = False

                while True:
                    yield self._status_frame("connecting", model=active_model)
                    async with client.stream(
                        "POST",
                        f"{config.OLLAMA_URL}/api/chat",
                        json={
                            "model": active_model,
                            "messages": ollama_messages,
                            "stream": True,
                        },
                        timeout=120.0,
                    ) as response:
                        if response.is_error:
                            await response.aread()
                            error_text = self._extract_error_message(response)
                            if not tried_fallback and self._is_memory_pressure_error(error_text):
                                fallback_model = await self._find_smaller_model(
                                    client,
                                    active_model,
                                )
                                if fallback_model is not None:
                                    tried_fallback = True
                                    active_model = fallback_model
                                    yield self._status_frame(
                                        "preparing",
                                        label=f"Switching to {fallback_model} to fit memory...",
                                        model=fallback_model,
                                        requested_model=self.model,
                                        reason="memory",
                                    )
                                    continue

                            response.raise_for_status()

                        self.model = active_model
                        yield self._status_frame("waiting", model=active_model)
                        async for line in response.aiter_lines():
                            if abort_event and abort_event.is_set():
                                aborted = True
                                break

                            if not line:
                                continue

                            full_text, should_stop, frame = self._parse_stream_line(
                                line,
                                full_text,
                            )
                            if frame is not None:
                                if not yielded_response_status and '"text":' in frame:
                                    yield self._status_frame("responding", model=active_model)
                                    yielded_response_status = True
                                yield frame
                            if should_stop:
                                break
                        break

            asst_msg = messages.AssistantMessage(content=full_text)
            self.append(asst_msg.model_dump())

            if aborted:
                yield "data: [DONE]\n\n"

        except httpx.HTTPError as error:
            yield f"data: {json.dumps({'error': str(error)})}\n\n"

    def _build_ollama_messages(
        self,
        system_context: str,
    ) -> list[dict[str, str]]:
        """Build the message payload sent to the Ollama chat API."""
        return [
            {"role": "system", "content": system_context},
            *[
                {"role": message["role"], "content": message["content"]}
                for message in self._messages
            ],
        ]

    @staticmethod
    def _parse_stream_line(
        line: str,
        full_text: str,
    ) -> tuple[str, bool, str | None]:
        """Convert one Ollama stream line into an SSE frame."""
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return full_text, False, None

        if payload.get("done"):
            return full_text, True, "data: [DONE]\n\n"

        text = payload.get("message", {}).get("content", "")
        if not text:
            return full_text, False, None

        full_text += text
        return full_text, False, f"data: {json.dumps({'text': text})}\n\n"
