"""Typed chat message models."""

import base64
import datetime
import uuid
from typing import Literal

import pydantic


MAX_TEXT_ATTACHMENT_CHARS = 100_000
MAX_IMAGE_ATTACHMENT_BYTES = 5 * 1024 * 1024


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


class Attachment(pydantic.BaseModel):
    """Structured attachment content that can be sent alongside a user message."""

    name: str = pydantic.Field(min_length=1, max_length=255)
    media_type: str = pydantic.Field(min_length=1, max_length=255)
    kind: Literal["text", "image"]
    content: str = pydantic.Field(min_length=1)

    @pydantic.model_validator(mode="after")
    def validate_attachment(self) -> "Attachment":
        """Validate attachment shape and size based on attachment kind."""
        if self.kind == "image":
            if not self.media_type.startswith("image/"):
                raise ValueError("Image attachments must use an image media type.")
            try:
                decoded = base64.b64decode(self.content, validate=True)
            except ValueError as error:
                raise ValueError("Image attachments must contain valid base64 data.") from error
            if len(decoded) > MAX_IMAGE_ATTACHMENT_BYTES:
                raise ValueError("Image attachments must be 5 MB or smaller.")
            return self

        if len(self.content) > MAX_TEXT_ATTACHMENT_CHARS:
            raise ValueError("Text attachments must be 100,000 characters or smaller.")
        return self


class UserMessage(BaseMessage):
    """A message authored by the user."""

    role: Literal["user"] = "user"
    content: str = ""
    attachments: list[Attachment] = pydantic.Field(default_factory=list)

    @pydantic.model_validator(mode="after")
    def validate_message_content(self) -> "UserMessage":
        """Require either text content or at least one attachment."""
        if self.content.strip() or self.attachments:
            return self
        raise ValueError("User messages must include text or at least one attachment.")


class AssistantMessage(BaseMessage):
    """A message authored by the assistant."""

    role: Literal["assistant"] = "assistant"
    content: str


Message = UserMessage | AssistantMessage
