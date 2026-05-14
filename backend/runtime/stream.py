"""Convert OpenHarness StreamEvent objects to JSON-serializable dicts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    CompactProgressEvent,
    ErrorEvent,
    StatusEvent,
    StreamEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def serialize_event(event: StreamEvent) -> dict[str, Any]:
    ts = _now_iso()

    if isinstance(event, AssistantTextDelta):
        return {"type": "agent.text", "data": {"text": event.text}, "ts": ts}

    if isinstance(event, AssistantTurnComplete):
        return {
            "type": "agent.turn_complete",
            "data": {
                "text": event.message.text,
                "usage": {
                    "input_tokens": event.usage.input_tokens,
                    "output_tokens": event.usage.output_tokens,
                },
            },
            "ts": ts,
        }

    if isinstance(event, ToolExecutionStarted):
        return {
            "type": "agent.tool_start",
            "data": {"tool_name": event.tool_name, "tool_input": event.tool_input},
            "ts": ts,
        }

    if isinstance(event, ToolExecutionCompleted):
        return {
            "type": "agent.tool_end",
            "data": {
                "tool_name": event.tool_name,
                "output": event.output,
                "is_error": event.is_error,
            },
            "ts": ts,
        }

    if isinstance(event, ErrorEvent):
        return {
            "type": "error",
            "data": {"message": event.message, "recoverable": event.recoverable},
            "ts": ts,
        }

    if isinstance(event, StatusEvent):
        return {"type": "status", "data": {"message": event.message}, "ts": ts}

    if isinstance(event, CompactProgressEvent):
        return {
            "type": "compact",
            "data": {
                "phase": event.phase,
                "trigger": event.trigger,
                "message": event.message,
            },
            "ts": ts,
        }

    return {"type": "unknown", "data": {"repr": repr(event)}, "ts": ts}
