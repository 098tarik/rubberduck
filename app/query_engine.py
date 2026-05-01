"""Session-scoped query engine for streaming chat responses."""

import asyncio
from collections.abc import AsyncIterator
import json

import httpx

from app import config, context, history, messages


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
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{config.OLLAMA_URL}/api/chat",
                    json={
                        "model": self.model,
                        "messages": ollama_messages,
                        "stream": True,
                    },
                    timeout=120.0,
                ) as response:
                    response.raise_for_status()
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
                            yield frame
                        if should_stop:
                            break

            if full_text:
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
