from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)


@pytest.fixture
def fake_events() -> list:
    msg = MagicMock()
    msg.text = "Hello world!"
    usage = MagicMock()
    usage.input_tokens = 10
    usage.output_tokens = 5
    return [
        AssistantTextDelta(text="Hello "),
        AssistantTextDelta(text="world!"),
        ToolExecutionStarted(tool_name="Read", tool_input={"file_path": "/tmp/t"}),
        ToolExecutionCompleted(tool_name="Read", output="ok", is_error=False),
        AssistantTurnComplete(message=msg, usage=usage),
    ]


@pytest.fixture
def mock_build_runtime(fake_events):
    bundle = MagicMock()
    bundle.session_id = "mock-sid"
    bundle.engine._permission_checker._settings.mode = None

    async def mock_submit(prompt):
        for event in fake_events:
            yield event

    bundle.engine.submit_message = mock_submit
    build = AsyncMock(return_value=bundle)
    return build, bundle


@pytest.fixture
def mock_close_runtime():
    return AsyncMock()
