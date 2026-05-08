"""Session-scoped query engine for streaming chat responses."""

import asyncio
from collections.abc import AsyncIterator
import json

import httpx

from app import abort, config, context, history, messages


STREAM_STATUS_LABELS = {
    "preparing": "Preparing context...",
    "connecting": "Starting local model...",
    "waiting": "Waiting for first token...",
    "responding": "Streaming response...",
}


class QueryEngine:
    """Manage chat history and stream responses from llama.cpp."""

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
        """Extract the most useful runtime error message from a failed response."""
        raw_text = response.text
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return raw_text

        if isinstance(payload, dict):
            if payload.get("error"):
                return str(payload["error"])
            choices = payload.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    message = first.get("message")
                    if isinstance(message, dict) and message.get("content"):
                        return str(message["content"])
        return raw_text

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
                yield self._status_frame("connecting", model=active_model)
                async with client.stream(
                    "POST",
                    f"{config.LLAMA_SERVER_URL}/chat/completions",
                    json={
                        "model": active_model,
                        "messages": ollama_messages,
                        "stream": True,
                    },
                    timeout=120.0,
                ) as response:
                    if isinstance(abort_event, abort.AbortController):
                        abort_event.add_callback(response.aclose)

                    if response.is_error:
                        await response.aread()
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
        """Build the message payload sent to llama.cpp chat completions API."""
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
        """Convert one llama.cpp stream line into an app SSE frame."""
        stripped_line = line.strip()
        if not stripped_line.startswith("data:"):
            return full_text, False, None

        payload_text = stripped_line.removeprefix("data:").strip()
        if payload_text == "[DONE]":
            return full_text, True, "data: [DONE]\n\n"

        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return full_text, False, None

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return full_text, False, None
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return full_text, False, None
        delta = first_choice.get("delta")
        if not isinstance(delta, dict):
            return full_text, False, None
        text = delta.get("content", "")
        if not text:
            return full_text, False, None

        full_text += text
        return full_text, False, f"data: {json.dumps({'text': text})}\n\n"
