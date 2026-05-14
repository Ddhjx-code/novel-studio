# Phase 0 Spike 发现报告

四个风险 spike 全部通过。本文档汇总验证结果、踩到的坑、以及对 Phase 1+ 的指导。

| Spike | 状态 | 核心结论 |
|---|---|---|
| 0.1 嵌入式 runtime | ✅ | `build_runtime + QueryEngine.submit_message` 是干净 async API，不必 subprocess |
| 0.2 多 session 并发 | ✅ | 同进程内多 session 完全隔离，asyncio.gather 真并发 |
| 0.3 subagent 派遣 | ✅ | AgentTool subprocess 可用但脆弱；**同进程多 build_runtime 是更优路径** |
| 0.4 LLM provider | ✅ | zenmux 两端点都通；建议默认 OpenAI 兼容协议 |

---

## 0.1 嵌入式 runtime — 通过

**验证项**：`build_runtime` + `QueryEngine.submit_message` 能在普通 Python 进程内完整跑通。

**结果**：
- `build_runtime` 0.10s 启动
- 41 个内建 tool 加载
- AsyncIterator[StreamEvent] 流式消费
- `AssistantTextDelta` 一段段拿到文本，`AssistantTurnComplete` 标志一轮结束

**结论**：完全不需要 `oh` CLI / TUI / subprocess 包装。FastAPI 后端可以直接 `import openharness` 嵌入式跑。

---

## 0.2 多 session 并发 — 通过

**验证项**：同进程内并发起 2 个不同 cwd 的 session，验证隔离性。

**结果**：
- 两个 session 不同 `session_id`、不同 `cwd`、内容无交叉
- asyncio.gather 总耗时 8.34s（vs 串行 ~16s），确认是真并发

**结论**：**部署可走单后端进程承载多用户/多项目**。不必每个项目独占进程。

---

## 0.3 Subagent 派遣 — 通过（架构方向有重要修正）

**Part A — AgentTool 走 LLM 决策派 subprocess subagent**：✅
- 主 Agent 通过 `agent` 工具调用，正确生成 `tool_use` 块
- subprocess executor 启动新 Python 进程跑 `python -m openharness --task-worker`
- 输出 `Spawned agent general-purpose@default (task_id=..., backend=subprocess)`

**但 AgentTool 是 fire-and-forget**：
- 主 Agent 拿到 `task_id` 后，需要主动用 `task_output` / `task_get` / `read_file` 工具 poll 子 agent 状态
- 不是 Claude Code 那种"Task 工具同步等结果返回"的语义
- 测试中主 Agent 在 OpenAI 协议下确实自己写出了完整的 poll 循环

**子进程 LLM auth 链路脆弱**：
- 即便 export 了 `OPENHARNESS_API_FORMAT/BASE_URL/MODEL/OPENAI_API_KEY`，子进程仍报空错误 `'API error: '`
- 根因未深挖（怀疑 settings.profile 的 provider/auth_source 状态在子进程里没正确初始化）
- **不是阻塞性问题**，因为我们的架构本来就不应该走这条路径

**Part B — 同进程多 build_runtime + system_prompt 扮演子 agent**：✅（**这才是 orchestrator 真正应该用的路径**）
- 主进程内 `build_runtime` 第二个 session，传 `system_prompt="你是一个修仙小说人物设计师子 agent..."`
- 同步消费 stream，7s 完成
- 独立 session_id，不影响主 session

**架构决策（写入 plan）**：
> Phase 4 chapter_pipeline 派子 agent 用 **同进程 build_runtime + system_prompt 注入角色**，
> 不走 AgentTool subprocess。优点：① 无 subprocess 启动开销；② 无 LLM 配置传递问题；
> ③ 主进程能直接同步消费 stream，与 FastAPI WebSocket 自然集成；④ permission/auth 状态共享。

---

## 0.4 LLM Provider — 通过

**zenmux 两个端点都通**（model 都是 `deepseek/deepseek-v4-pro`）：

| api_format | base_url | detect | 单轮耗时 | 文本 |
|---|---|---|---|---|
| `openai_compat` | `https://zenmux.ai/api/v1` | deepseek (openai_compat) | 5.62s | "Fine" |
| `anthropic` | `https://zenmux.ai/api/anthropic` | deepseek (openai_compat) | 3.70s | "Fine" |

**注意事项**：
- `detect_provider_from_registry` 通过 model 名 `deepseek/...` 命中 deepseek provider，但运行时以 `api_format` 参数为准（spike 01 anthropic 协议下也跑通了）
- **OpenAI 兼容协议下 zenmux 不返回 usage**（input/output tokens 都是 0）—— 计费/配额监控时要注意
- **Anthropic 协议下复杂 tool use 时 deepseek 报 thinking mode 兼容问题**：
  > `'The content[].thinking in the thinking mode must be passed back to the API.'`
  
  zenmux 把 deepseek 包成 anthropic 协议时启用了 thinking mode，但 OpenHarness 没有把 thinking 块回传

**结论 / 建议**：
> **默认使用 OpenAI 兼容协议**（`/api/v1`）。Anthropic 协议留作后备，避免 deepseek thinking mode 兼容问题。

---

## 贯穿性发现 / 踩坑笔记

### 1. `AssistantTurnComplete` 不是流结束信号

```python
# 错误用法（spike 01 早期）
async for event in engine.submit_message(prompt):
    if isinstance(event, AssistantTurnComplete):
        break  # ❌ 早 break 错过 tool execution + 下一轮
```

`AssistantTurnComplete` 是「单轮完成」信号。如果该轮包含 `tool_use`，后面还会有：
1. `ToolExecutionStarted` / `ToolExecutionCompleted`
2. 下一轮 `AssistantTextDelta` / `AssistantTurnComplete`

**正确用法**：让 async for 自然结束（StopAsyncIteration），或精确判断「有 turn complete 且 turn 内无 tool_use」。

### 2. `permission_mode` build_runtime 参数不生效

```python
# 错误用法
bundle = await build_runtime(..., permission_mode="bypassPermissions")  # ❌ 无效

# 正确用法
from openharness.permissions.modes import PermissionMode
bundle = await build_runtime(...)
bundle.engine._permission_checker._settings.mode = PermissionMode.FULL_AUTO
```

原因：`build_runtime` 把 `permission_mode` 收进 `settings_overrides` 给 `model_copy(update=...)`，但 `Settings` 没有顶级 `permission_mode` 字段（只有 `permission: PermissionSettings`），pydantic v2 默默吞掉。

PermissionMode enum 只有三个合法值：`DEFAULT` / `PLAN` / `FULL_AUTO`（**不是** Claude Code 的 `bypassPermissions/acceptEdits`）。

### 3. Default permission mode 拦截 mutating tool

未设 FULL_AUTO 时，`agent` 这种 mutating tool 会被拦：
```
Mutating tools require user confirmation in default mode.
Approve the prompt when asked, or run /permissions full_auto if you want to allow them for this session.
```

后端 orchestrator 必须在 `build_runtime` 后立即把 mode 设成 FULL_AUTO（或提供 `permission_prompt` 回调走 UI 确认）。

### 4. 配置加载顺序

后端启动时 `.env.local` → `os.environ` → OpenHarness `_apply_env_overrides` 读 `OPENHARNESS_*` / `OPENAI_API_KEY`。我们的 `spikes/_common.py::load_env()` 是范本。

---

## 对 plan.md 的修订建议

1. **Phase 4 chapter_pipeline 实现明确路径**：在每步派子 agent 时使用「同进程 build_runtime + system_prompt」，不走 AgentTool subprocess。文档化原因。
2. **Phase 2 Runtime 包装层 `NovelSession`** 必须封装：① permission_mode 默认 FULL_AUTO 的 monkey patch；② AssistantTurnComplete 的正确处理；③ ErrorEvent 处理。
3. **Phase 0 已完成验证**：可以删去或缩减为「环境验收清单」。
4. **协议默认 OpenAI 兼容**：Settings/UI 默认值用 `openai_compat` + zenmux `/api/v1` 端点。

---

## 用过的运行命令

```bash
# 准备
python3 -m venv .venv
.venv/bin/pip install -e ./OpenHarness

# 跑 spike（默认走 .env.local 的 OpenAI 兼容协议）
.venv/bin/python spikes/01_runtime.py
.venv/bin/python spikes/02_concurrency.py
.venv/bin/python spikes/03_subagent.py
.venv/bin/python spikes/04_providers.py

# 临时切 anthropic 协议
LLM_API_FORMAT=anthropic LLM_BASE_URL=https://zenmux.ai/api/anthropic \
  .venv/bin/python spikes/01_runtime.py
```
