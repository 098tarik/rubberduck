"""Tests for the messages module."""

import datetime
import uuid

from app.messages import AssistantMessage, BaseMessage, UserMessage


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
