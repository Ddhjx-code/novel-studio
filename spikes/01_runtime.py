"""Spike 0.1 — OpenHarness 嵌入式跑通

目的：验证 build_runtime + QueryEngine.submit_message 能在普通 Python 进程里跑，
不需要 TUI / subprocess / oh CLI。

验证点：
  1. build_runtime 接受 cwd / model / api_key / base_url / api_format 参数
  2. submit_message 返回 AsyncIterator[StreamEvent]
  3. 能正确收到 AssistantTextDelta（流式文本）和 AssistantTurnComplete（结束信号）
  4. 整个调用过程脱离 TUI / 交互式输入

运行：
  .venv/bin/python spikes/01_runtime.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
    StatusEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from openharness.ui.runtime import build_runtime, close_runtime, start_runtime

from _common import LLMConfig, load_env


SPIKE_PROMPT = "用一句中文介绍你自己（不超过 20 字），不要用工具。"


async def run_spike() -> int:
    load_env()
    cfg = LLMConfig.from_env()
    print(cfg.banner())
    print(f"[INFO] cwd={Path.cwd()}")
    print()

    t0 = time.monotonic()
    bundle = await build_runtime(
        cwd=str(Path.cwd()),
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        api_format=cfg.api_format,
        max_turns=3,
        include_project_memory=False,
    )
    print(f"[OK] build_runtime in {time.monotonic() - t0:.2f}s, session_id={bundle.session_id}")
    print(f"[OK] tools loaded: {len(bundle.tool_registry.list_tools())}")

    await start_runtime(bundle)

    text_chunks: list[str] = []
    tool_calls: list[str] = []
    turn_completed = False
    errors: list[str] = []

    print(f"[INFO] submitting prompt: {SPIKE_PROMPT!r}")
    print("[INFO] streaming events ↓")
    print("-" * 60)

    try:
        async for event in bundle.engine.submit_message(SPIKE_PROMPT):
            if isinstance(event, AssistantTextDelta):
                print(event.text, end="", flush=True)
                text_chunks.append(event.text)
            elif isinstance(event, ToolExecutionStarted):
                print(f"\n[tool.start] {event.tool_name} input={event.tool_input}")
                tool_calls.append(event.tool_name)
            elif isinstance(event, ToolExecutionCompleted):
                print(f"[tool.end]   {event.tool_name} is_error={event.is_error}")
            elif isinstance(event, AssistantTurnComplete):
                print(f"\n[turn.complete] usage={event.usage}")
                turn_completed = True
                break
            elif isinstance(event, ErrorEvent):
                print(f"\n[error] {event.message}")
                errors.append(event.message)
            elif isinstance(event, StatusEvent):
                print(f"\n[status] {event.message}")
    finally:
        await close_runtime(bundle)

    print("-" * 60)
    print()
    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    full_text = "".join(text_chunks).strip()
    print(f"  text deltas:             {len(text_chunks)} 段，共 {len(full_text)} 字")
    print(f"  tool calls:              {len(tool_calls)} ({tool_calls})")
    print(f"  AssistantTurnComplete:   {'✅' if turn_completed else '❌'}")
    print(f"  errors:                  {len(errors)}")
    print()
    print(f"  完整回复: {full_text!r}")
    print()

    if turn_completed and full_text and not errors:
        print("[PASS] spike 0.1 通过：build_runtime + submit_message 嵌入式调用可行")
        return 0
    print("[FAIL] spike 0.1 失败")
    return 1


if __name__ == "__main__":
    # 让 _common 可被同目录脚本 import
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(asyncio.run(run_spike()))
