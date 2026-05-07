"""Tests for the messages module."""

import base64
import datetime
import uuid

import pytest

from app.messages import AssistantMessage, Attachment, BaseMessage, UserMessage


def test_user_message_role():
    msg = UserMessage(content="hello")
    assert msg.role == "user"


def test_user_message_content():
    msg = UserMessage(content="test content")
    assert msg.content == "test content"


def test_assistant_message_role():
    msg = AssistantMessage(content="hi there")
    assert msg.role == "assistant"


def test_assistant_message_content():
    msg = AssistantMessage(content="response text")
    assert msg.content == "response text"


def test_base_message_id_is_uuid():
    msg = UserMessage(content="x")
    # Should not raise
    uuid.UUID(msg.id)


def test_base_message_each_has_unique_id():
    msg1 = UserMessage(content="a")
    msg2 = UserMessage(content="b")
    assert msg1.id != msg2.id


def test_base_message_timestamp_is_iso8601():
    msg = UserMessage(content="x")
    # Should parse without error
    dt = datetime.datetime.fromisoformat(msg.timestamp)
    assert dt.tzinfo is not None


def test_base_message_custom_id():
    msg = UserMessage(id="custom-id", content="x")
    assert msg.id == "custom-id"


def test_base_message_custom_timestamp():
    ts = "2024-01-01T00:00:00+00:00"
    msg = UserMessage(timestamp=ts, content="x")
    assert msg.timestamp == ts


def test_user_message_model_dump_contains_role():
    msg = UserMessage(content="hello")
    data = msg.model_dump()
    assert data["role"] == "user"
    assert data["content"] == "hello"
    assert "id" in data
    assert "timestamp" in data


def test_assistant_message_model_dump_contains_role():
    msg = AssistantMessage(content="hi")
    data = msg.model_dump()
    assert data["role"] == "assistant"
    assert data["content"] == "hi"


def test_user_message_can_include_attachments():
    msg = UserMessage(
        content="please review these",
        attachments=[
            Attachment(
                name="notes.md",
                media_type="text/markdown",
                kind="text",
                content="# Notes",
            )
        ],
    )

    dumped = msg.model_dump()
    assert dumped["attachments"][0]["name"] == "notes.md"


def test_user_message_requires_text_or_attachments():
    with pytest.raises(ValueError):
        UserMessage(content="   ")


def test_attachment_rejects_invalid_image_payload():
    with pytest.raises(ValueError):
        Attachment(
            name="duck.png",
            media_type="image/png",
            kind="image",
            content="not-base64",
        )


def test_attachment_accepts_base64_image_payload():
    msg = Attachment(
        name="duck.png",
        media_type="image/png",
        kind="image",
        content=base64.b64encode(b"png-bytes").decode("ascii"),
    )
    assert msg.kind == "image"
