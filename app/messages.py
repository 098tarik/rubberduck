"""Typed chat message models."""

import datetime
import uuid
from typing import Literal

import pydantic


def _generate_message_id() -> str:
    """Return a unique identifier for a persisted message."""
    return str(uuid.uuid4())


def _utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class BaseMessage(pydantic.BaseModel):
    """Base fields shared by all chat messages."""

    id: str = pydantic.Field(default_factory=_generate_message_id)
    timestamp: str = pydantic.Field(default_factory=_utc_timestamp)


class UserMessage(BaseMessage):
    """A message authored by the user."""

    role: Literal["user"] = "user"
    content: str


class AssistantMessage(BaseMessage):
    """A message authored by the assistant."""

    role: Literal["assistant"] = "assistant"
    content: str


Message = UserMessage | AssistantMessage
