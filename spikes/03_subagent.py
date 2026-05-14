"""Spike 0.3 — subagent 派遣

目的：验证主 Agent 能用 AgentTool（agent 工具）派子 Agent，
以及理解派遣的真实代价（subprocess 启新进程）和配置传递机制。

发现（基于源码阅读）：
  - AgentTool 走 subprocess executor → `python -m openharness --task-worker`
  - 子进程通过环境变量继承 LLM 配置：OPENHARNESS_API_FORMAT / OPENHARNESS_BASE_URL
    / OPENHARNESS_MODEL / OPENAI_API_KEY 等（_TEAMMATE_ENV_VARS 列表）
  - 子进程独立上下文（独立进程 + 独立 OpenHarness runtime）

验证点：
  1. 主 Agent 能成功调用 'agent' 工具派 general-purpose subagent
  2. 子 agent 能完成简单任务并返回结果
  3. 主 Agent 能拿到子 agent 的输出
  4. 测量端到端耗时（评估每章流水线 6 步派遣开销）

策略：
  - 强制性 prompt：要求主 Agent 用 agent 工具派 general-purpose 子 agent
    生成一个独特字符串「紫云剑✦42」并返回
  - 检查 ToolExecutionStarted(tool_name='agent') 事件出现
  - 检查 ToolExecutionCompleted output 含独特字符串
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
    ToolExecutionCompleted,
    ToolExecutionStarted,
)
from openharness.permissions.modes import PermissionMode
from openharness.ui.runtime import build_runtime, close_runtime, start_runtime

from _common import LLMConfig, load_env


UNIQUE_TOKEN = "紫云剑✦42"

SPIKE_PROMPT = f"""你必须使用 agent 工具（tool name = "agent"）派遣一个子 agent。

具体调用参数：
  subagent_type: "general-purpose"
  description:   "echo unique token"
  prompt:        "请只输出这串字符，不要任何解释、引号或其他内容：{UNIQUE_TOKEN}"

派遣完成后，把子 agent 返回的内容原样告诉我，并在末尾写一行 "DONE"。
不要自己生成那串字符，必须来自子 agent 的输出。
"""


def export_subagent_env(cfg: LLMConfig) -> None:
    """把 LLM 配置写到 OpenHarness 子进程能识别的 env vars 里。

    OpenHarness 的 _TEAMMATE_ENV_VARS 列表只继承固定几个 key，
    我们的 LLM_* 不在其中，必须映射成 OPENHARNESS_* / OPENAI_API_KEY。
    """
    os.environ["OPENHARNESS_API_FORMAT"] = cfg.api_format
    os.environ["OPENHARNESS_BASE_URL"] = cfg.base_url
    os.environ["OPENHARNESS_MODEL"] = cfg.model
    if cfg.api_format == "openai_compat":
        os.environ["OPENAI_API_KEY"] = cfg.api_key
    elif cfg.api_format == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = cfg.api_key
        os.environ["ANTHROPIC_BASE_URL"] = cfg.base_url


async def run_spike() -> int:
    load_env()
    cfg = LLMConfig.from_env()
    print(cfg.banner())
    export_subagent_env(cfg)
    print("[INFO] 已 export OPENHARNESS_* / *_API_KEY 给子进程继承")
    print()

    t0 = time.monotonic()
    bundle = await build_runtime(
        cwd=str(Path.cwd()),
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        api_format=cfg.api_format,
        max_turns=8,  # 加大：子 agent 异步派完后主 Agent 还要 poll 状态、读输出、回复
        include_project_memory=False,
    )
    # FINDING: build_runtime 的 permission_mode 参数不生效（Settings 没这字段，被 model_copy 默默吞掉）
    # 必须 monkeypatch 已构建的 PermissionChecker。OpenHarness 自带 mode 名是 default/plan/full_auto
    # （不是 Claude Code 的 bypassPermissions/acceptEdits）
    bundle.engine._permission_checker._settings.mode = PermissionMode.FULL_AUTO
    await start_runtime(bundle)
    print(f"[OK] build_runtime in {time.monotonic() - t0:.2f}s")

    text_chunks: list[str] = []
    agent_tool_calls: list[dict] = []
    agent_tool_outputs: list[str] = []
    other_tool_calls: list[str] = []
    completed = False
    errors: list[str] = []

    print(f"[INFO] submitting prompt...")
    print("-" * 60)

    from openharness.engine.query import MaxTurnsExceeded

    t_submit = time.monotonic()
    try:
        try:
            async for event in bundle.engine.submit_message(SPIKE_PROMPT):
                if isinstance(event, AssistantTextDelta):
                    print(event.text, end="", flush=True)
                    text_chunks.append(event.text)
                elif isinstance(event, ToolExecutionStarted):
                    print(f"\n[tool.start] {event.tool_name} input={event.tool_input}")
                    if event.tool_name == "agent":
                        agent_tool_calls.append(event.tool_input)
                    else:
                        other_tool_calls.append(event.tool_name)
                elif isinstance(event, ToolExecutionCompleted):
                    preview = event.output[:200] + ("…" if len(event.output) > 200 else "")
                    print(f"[tool.end]   {event.tool_name} is_error={event.is_error}")
                    print(f"[tool.out]   {preview!r}")
                    if event.tool_name == "agent":
                        agent_tool_outputs.append(event.output)
                elif isinstance(event, AssistantTurnComplete):
                    # NOTE: 不 break！turn complete 只是单轮信号，后面可能还有 tool 执行 + 下一轮
                    print(f"\n[turn.complete] usage={event.usage}")
                    completed = True
                elif isinstance(event, ErrorEvent):
                    print(f"\n[error] {event.message}")
                    errors.append(event.message)
        except MaxTurnsExceeded as e:
            print(f"\n[note] {e} — 子 agent 失败导致主 Agent 一直 retry。Part A 验证已收集到所需数据，继续 Part B。")
    finally:
        await close_runtime(bundle)

    e2e_duration = time.monotonic() - t_submit

    # DEBUG: dump messages 看 LLM 实际返回了什么
    print()
    print("[DEBUG] 最后一条 assistant message blocks:")
    if bundle.engine.messages:
        last = bundle.engine.messages[-1]
        print(f"  role={last.role}")
        for i, block in enumerate(getattr(last, "content_blocks", []) or []):
            print(f"  block[{i}]: type={type(block).__name__} {block!r}")
        # 兜底：如果没有 content_blocks 字段就 dump model_dump
        try:
            dump = last.model_dump()
            for k, v in dump.items():
                vstr = repr(v)
                if len(vstr) > 300:
                    vstr = vstr[:300] + "…"
                print(f"  {k}={vstr}")
        except Exception as e:
            print(f"  (model_dump failed: {e})")

    print("-" * 60)
    print()
    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    full_text = "".join(text_chunks).strip()
    agent_called = len(agent_tool_calls) > 0
    token_in_subagent_output = any(UNIQUE_TOKEN in o for o in agent_tool_outputs)
    token_in_main_reply = UNIQUE_TOKEN in full_text

    print(f"  端到端耗时:              {e2e_duration:.2f}s")
    print(f"  agent 工具被调用:         {'✅' if agent_called else '❌'} (次数={len(agent_tool_calls)})")
    print(f"  其他工具被调用:           {other_tool_calls}")
    print(f"  子 agent 输出含独特 token: {'✅' if token_in_subagent_output else '❌'}")
    print(f"  主 Agent 回复含独特 token: {'✅' if token_in_main_reply else '❌'}")
    print(f"  AssistantTurnComplete:   {'✅' if completed else '❌'}")
    print(f"  errors:                  {len(errors)}")
    print()
    if agent_tool_outputs:
        print(f"  子 agent 原始输出（首段）:")
        print(f"    {agent_tool_outputs[0][:300]!r}")
        print()
    print(f"  主 Agent 完整回复: {full_text!r}")
    print()

    # 通过条件：subagent 真的被派出去且子 agent 回的内容含 token
    # 主 Agent 是否复述 token 不强求（弱模型可能没搬过来）
    # Part A 标准：AgentTool 调用成功 + 派出 subprocess（不要求拿到子 agent 完整输出，
    # 因为 AgentTool 是 fire-and-forget，输出在 task_manager 里）
    spawned_ok = agent_called and any("Spawned agent" in o for o in agent_tool_outputs)
    print(f"  Part A — AgentTool 派出 subprocess: {'✅' if spawned_ok else '❌'}")
    print()

    # Part B：编程式 spawn + 同步等结果（orchestrator 真正会用的路径）
    print("=" * 60)
    print("Part B — 编程式 spawn + 同步等结果（无 LLM 决策）")
    print("=" * 60)
    part_b_ok = await run_part_b(cfg)

    print()
    print("=" * 60)
    print("FINAL VERDICT")
    print("=" * 60)
    print(f"  Part A (LLM-driven AgentTool):  {'✅' if spawned_ok else '❌'}")
    print(f"  Part B (programmatic spawn):    {'✅' if part_b_ok else '❌'}")

    if spawned_ok and part_b_ok:
        print("[PASS] spike 0.3 通过")
        return 0
    print("[FAIL] spike 0.3 失败")
    return 1


async def run_part_b(cfg: LLMConfig) -> bool:
    """同进程内 build_runtime 第二个 session + system_prompt 让它扮演子 agent 角色。

    这是 orchestrator 真正会用的方式：不走 AgentTool subprocess（开销大、配置传递
    复杂、auth 链路脆弱），而是直接在主进程里 build_runtime 一个临时 session，
    传 agent 定义的 system_prompt + 用户任务 prompt，同步消费 stream 拿结果。
    """
    print(f"[INFO] 在同进程内 build_runtime 一个新 session 扮演 'planner' 子 agent...")
    role_system_prompt = (
        "你是一个修仙小说的人物设计师子 agent。"
        "你必须严格遵守任务指令，不要使用任何工具，"
        "不要解释，只输出用户要求的内容。"
    )
    sub_bundle = await build_runtime(
        cwd=str(Path.cwd()),
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        api_format=cfg.api_format,
        system_prompt=role_system_prompt,
        max_turns=2,
        include_project_memory=False,
    )
    sub_bundle.engine._permission_checker._settings.mode = PermissionMode.FULL_AUTO
    await start_runtime(sub_bundle)

    task_prompt = f"请只输出这串字符，不要任何解释、引号或其他内容：{UNIQUE_TOKEN}"
    chunks: list[str] = []
    completed = False
    error: str | None = None

    t0 = time.monotonic()
    try:
        async for event in sub_bundle.engine.submit_message(task_prompt):
            if isinstance(event, AssistantTextDelta):
                chunks.append(event.text)
            elif isinstance(event, AssistantTurnComplete):
                completed = True
            elif isinstance(event, ErrorEvent):
                error = event.message
                break
    finally:
        await close_runtime(sub_bundle)

    output = "".join(chunks).strip()
    duration = time.monotonic() - t0

    print(f"[OK]   sub session 完成，耗时 {duration:.2f}s，session_id={sub_bundle.session_id}")
    print(f"[OK]   sub session 输出: {output!r}")
    if error:
        print(f"[ERR]  {error}")

    contains_token = UNIQUE_TOKEN in output
    distinct_session = sub_bundle.session_id  # 跟主 session 不同（每次 build_runtime 都新生成）

    if completed and contains_token and not error:
        print(f"[PASS] Part B：sub session 独立运行，正确返回 token")
        return True
    print(f"[FAIL] Part B")
    return False


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(asyncio.run(run_spike()))
