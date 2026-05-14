"""Spike 0.4 — LLM provider 适配诊断

目的：验证 OpenHarness 在 zenmux 自定义 base_url 下能否正确识别 provider，
两个协议端点都跑通，并打印 detect_provider 的判断结果作为文档。

验证点：
  1. zenmux 的 OpenAI 兼容端点 (/api/v1) + deepseek/deepseek-v4-pro → 能跑
  2. zenmux 的 Anthropic 端点 (/api/anthropic) + deepseek/deepseek-v4-pro → 能跑
  3. 打印两种配置下 detect_provider_from_registry 的判断
  4. 测量两种协议的延迟差异（非严格 benchmark）
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from openharness.api.registry import detect_provider_from_registry
from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
)
from openharness.permissions.modes import PermissionMode
from openharness.ui.runtime import build_runtime, close_runtime, start_runtime

from _common import LLMConfig, load_env


PROBE_PROMPT = "用一个英文单词回答：你好吗？"


@dataclass
class ProbeResult:
    label: str
    api_format: str
    base_url: str
    provider_detected: str | None
    backend_type: str | None
    text: str
    duration: float
    completed: bool
    error: str | None


async def probe(label: str, api_format: str, base_url: str, cfg: LLMConfig) -> ProbeResult:
    spec = detect_provider_from_registry(model=cfg.model, api_key=cfg.api_key, base_url=base_url)
    detected_name = spec.name if spec else None
    backend_type = spec.backend_type if spec else None
    print(f"[{label}] detect_provider → name={detected_name!r}, backend_type={backend_type!r}")

    t0 = time.monotonic()
    bundle = await build_runtime(
        cwd=str(Path.cwd()),
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=base_url,
        api_format=api_format,
        max_turns=2,
        include_project_memory=False,
    )
    bundle.engine._permission_checker._settings.mode = PermissionMode.FULL_AUTO
    await start_runtime(bundle)

    chunks: list[str] = []
    completed = False
    error: str | None = None
    try:
        async for event in bundle.engine.submit_message(PROBE_PROMPT):
            if isinstance(event, AssistantTextDelta):
                chunks.append(event.text)
            elif isinstance(event, AssistantTurnComplete):
                completed = True
                # 单 turn prompt 不会有 tool_use，turn complete 后可以 break
                break
            elif isinstance(event, ErrorEvent):
                error = event.message
                break
    finally:
        await close_runtime(bundle)

    return ProbeResult(
        label=label,
        api_format=api_format,
        base_url=base_url,
        provider_detected=detected_name,
        backend_type=backend_type,
        text="".join(chunks).strip(),
        duration=time.monotonic() - t0,
        completed=completed,
        error=error,
    )


async def run_spike() -> int:
    load_env()
    cfg = LLMConfig.from_env()
    print(f"[INFO] model={cfg.model}, key={cfg.api_key[:8]}…{cfg.api_key[-4:]}")
    print()

    print("=" * 60)
    print("Probe 1: OpenAI 兼容协议 (/api/v1)")
    print("=" * 60)
    r1 = await probe(
        label="OpenAI",
        api_format="openai_compat",
        base_url="https://zenmux.ai/api/v1",
        cfg=cfg,
    )
    print(f"  duration={r1.duration:.2f}s  completed={r1.completed}  error={r1.error}")
    print(f"  text={r1.text!r}")
    print()

    print("=" * 60)
    print("Probe 2: Anthropic 协议 (/api/anthropic)")
    print("=" * 60)
    r2 = await probe(
        label="Anthropic",
        api_format="anthropic",
        base_url="https://zenmux.ai/api/anthropic",
        cfg=cfg,
    )
    print(f"  duration={r2.duration:.2f}s  completed={r2.completed}  error={r2.error}")
    print(f"  text={r2.text!r}")
    print()

    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    print(f"  {'协议':<14} {'detected':<14} {'backend':<14} {'通':<4} {'耗时':<8} 文本")
    for r in (r1, r2):
        ok = "✅" if r.completed and not r.error and r.text else "❌"
        print(
            f"  {r.api_format:<14} {str(r.provider_detected):<14} "
            f"{str(r.backend_type):<14} {ok:<4} {r.duration:>6.2f}s  {r.text[:30]!r}"
        )
    print()

    findings = []
    findings.append(
        f"detect_provider 对 zenmux base_url 的识别：OpenAI={r1.provider_detected}, "
        f"Anthropic={r2.provider_detected} —— 注意：deepseek 模型名命中 deepseek provider，"
        f"backend_type 与传入 api_format 可能不一致，但运行时以 api_format 为准。"
    )
    print("[FINDING]", findings[0])
    print()

    if r1.completed and r2.completed and r1.text and r2.text:
        print("[PASS] spike 0.4 通过：两种协议都能正常调用")
        return 0
    print("[FAIL] spike 0.4 失败")
    return 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(asyncio.run(run_spike()))
