from __future__ import annotations

from unittest.mock import MagicMock

from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    StatusEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)

from backend.runtime.stream import serialize_event


def test_serialize_text_delta():
    event = AssistantTextDelta(text="hello")
    result = serialize_event(event)
    assert result["type"] == "agent.text"
    assert result["data"]["text"] == "hello"
    assert "ts" in result


def test_serialize_turn_complete():
    msg = MagicMock()
    msg.text = "final text"
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    event = AssistantTurnComplete(message=msg, usage=usage)
    result = serialize_event(event)
    assert result["type"] == "agent.turn_complete"
    assert result["data"]["text"] == "final text"
    assert result["data"]["usage"] == {"input_tokens": 100, "output_tokens": 50}


def test_serialize_tool_started():
    event = ToolExecutionStarted(tool_name="Read", tool_input={"file_path": "/tmp/x"})
    result = serialize_event(event)
    assert result["type"] == "agent.tool_start"
    assert result["data"]["tool_name"] == "Read"
    assert result["data"]["tool_input"] == {"file_path": "/tmp/x"}


def test_serialize_tool_completed():
    event = ToolExecutionCompleted(tool_name="Read", output="contents", is_error=False)
    result = serialize_event(event)
    assert result["type"] == "agent.tool_end"
    assert result["data"]["tool_name"] == "Read"
    assert result["data"]["output"] == "contents"
    assert result["data"]["is_error"] is False


def test_serialize_tool_completed_error():
    event = ToolExecutionCompleted(tool_name="Bash", output="not found", is_error=True)
    result = serialize_event(event)
    assert result["data"]["is_error"] is True


def test_serialize_error_event():
    event = ErrorEvent(message="boom", recoverable=False)
    result = serialize_event(event)
    assert result["type"] == "error"
    assert result["data"]["message"] == "boom"
    assert result["data"]["recoverable"] is False


def test_serialize_status_event():
    event = StatusEvent(message="loading tools")
    result = serialize_event(event)
    assert result["type"] == "status"
    assert result["data"]["message"] == "loading tools"


def test_serialize_compact_event():
    event = CompactProgressEvent(phase="compact_start", trigger="auto", message="compacting")
    result = serialize_event(event)
    assert result["type"] == "compact"
    assert result["data"]["phase"] == "compact_start"
    assert result["data"]["trigger"] == "auto"
