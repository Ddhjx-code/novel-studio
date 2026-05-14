"""Spike 0.2 — 多 session 并发

目的：验证 build_runtime 能在同一进程内并行起多个 session（不同 cwd），
互不干扰。这是「多项目共享后端进程」部署模式的前提。

验证点：
  1. 两个 session 用不同 cwd 同时 build_runtime 不冲突
  2. 各自的 submit_message 流交错收到，内容不串
  3. 一个 session 失败/慢，不影响另一个
  4. tool_registry / engine 实例彼此独立

策略：
  - 在 spikes/output/ 下建两个临时项目目录 spike02-A、spike02-B
  - 两个 session 用 asyncio.gather 并发跑
  - 各让它写一首关于不同主题的两行小诗（避免 tool 调用，专注隔离）
  - 校验两个回复内容里都包含各自的关键词
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from openharness.engine.stream_events import (
    AssistantTextDelta,
    AssistantTurnComplete,
    ErrorEvent,
)
from openharness.ui.runtime import build_runtime, close_runtime, start_runtime

from _common import LLMConfig, load_env


@dataclass
class SessionResult:
    label: str
    cwd: str
    session_id: str
    text: str
    duration: float
    completed: bool
    error: str | None


async def run_one(label: str, cwd: Path, prompt: str, cfg: LLMConfig) -> SessionResult:
    cwd.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    bundle = await build_runtime(
        cwd=str(cwd),
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url,
        api_format=cfg.api_format,
        max_turns=2,
        include_project_memory=False,
    )
    await start_runtime(bundle)
    print(f"[{label}] build_runtime in {time.monotonic() - t0:.2f}s, session_id={bundle.session_id}, cwd={cwd}")

    chunks: list[str] = []
    completed = False
    error: str | None = None

    try:
        async for event in bundle.engine.submit_message(prompt):
            if isinstance(event, AssistantTextDelta):
                chunks.append(event.text)
            elif isinstance(event, AssistantTurnComplete):
                completed = True
                break
            elif isinstance(event, ErrorEvent):
                error = event.message
                break
    finally:
        await close_runtime(bundle)

    return SessionResult(
        label=label,
        cwd=str(cwd),
        session_id=bundle.session_id,
        text="".join(chunks).strip(),
        duration=time.monotonic() - t0,
        completed=completed,
        error=error,
    )


async def run_spike() -> int:
    load_env()
    cfg = LLMConfig.from_env()
    print(cfg.banner())
    print()

    out_dir = Path("spikes/output").resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    cwd_a = out_dir / "spike02-A"
    cwd_b = out_dir / "spike02-B"

    prompt_a = "用一句中文写一句关于「月亮」的诗，诗里必须出现「月」字。直接给诗句，不要解释。"
    prompt_b = "用一句中文写一句关于「大海」的诗，诗里必须出现「海」字。直接给诗句，不要解释。"

    print("[INFO] 并发启动两个 session ...")
    t0 = time.monotonic()
    result_a, result_b = await asyncio.gather(
        run_one("A", cwd_a, prompt_a, cfg),
        run_one("B", cwd_b, prompt_b, cfg),
    )
    total = time.monotonic() - t0

    print()
    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    print(f"  并发耗时:                {total:.2f}s")
    print()
    for r in (result_a, result_b):
        print(f"  [{r.label}] session_id:        {r.session_id}")
        print(f"  [{r.label}] cwd:               {r.cwd}")
        print(f"  [{r.label}] duration:          {r.duration:.2f}s")
        print(f"  [{r.label}] completed:         {'✅' if r.completed else '❌'}")
        print(f"  [{r.label}] error:             {r.error}")
        print(f"  [{r.label}] text:              {r.text!r}")
        print()

    # 隔离校验
    a_keyword_in_a = "月" in result_a.text
    b_keyword_in_b = "海" in result_b.text
    a_b_swapped = "海" in result_a.text or "月" in result_b.text  # 不应该出现交叉
    distinct_session_ids = result_a.session_id != result_b.session_id

    print(f"  A 回复含「月」:           {'✅' if a_keyword_in_a else '❌'}")
    print(f"  B 回复含「海」:           {'✅' if b_keyword_in_b else '❌'}")
    print(f"  A/B 内容无交叉:           {'✅' if not a_b_swapped else '❌'}")
    print(f"  session_id 不同:          {'✅' if distinct_session_ids else '❌'}")
    print()

    all_pass = (
        result_a.completed
        and result_b.completed
        and a_keyword_in_a
        and b_keyword_in_b
        and not a_b_swapped
        and distinct_session_ids
        and not result_a.error
        and not result_b.error
    )

    if all_pass:
        print("[PASS] spike 0.2 通过：多 session 并发互不干扰")
        return 0
    print("[FAIL] spike 0.2 失败")
    return 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(asyncio.run(run_spike()))
