# Novel Studio

AI 小说创作辅助工具 — 浏览器即用，4-Agent 工作流 + RAG 一致性。

> **定位**：辅助人类作者完成小说创作的工作台，**不是**全自动写作机器。
> 核心能力是「一键生成大纲」「一键生成单章」「一键审查/润色」，每个能力可独立调用，人类全程主导节奏与创意。

详细规划见 [`plan.md`](./plan.md)。Phase 0 风险验证发现见 [`docs/spike-findings.md`](./docs/spike-findings.md)。

---

## 当前阶段

- ✅ Phase 0 — 风险 spike 全过
- ✅ Phase 1 — 前后端骨架（健康检查打通）
- ⬜ Phase 2 — Runtime + WebSocket
- ⬜ Phase 3+ — 后续

---

## 快速开始

### 0. 前置依赖

- Python ≥ 3.10
- Node.js ≥ 20
- 已 clone 三个参考项目到本仓库根目录：`OpenHarness/`、`writeAgent/`、`AI_NovelGenerator/`（这些目录被 `.gitignore` 排除，不入版本库）

### 1. 配置 LLM 凭据

复制 `.env.example` 为 `.env.local`，填入你的 API key：

```bash
cp .env.example .env.local
# 用编辑器修改 .env.local
```

`.env.local` 已被 `.gitignore` 排除，**永远不会进入 git**。

默认配置走 [zenmux](https://zenmux.ai/) 的 OpenAI 兼容协议（`https://zenmux.ai/api/v1`）+ `deepseek/deepseek-v4-pro` 模型。要换别的 provider，参考 `.env.example` 注释。

### 2. 装后端

```bash
python3 -m venv .venv
.venv/bin/pip install -e ./OpenHarness
.venv/bin/pip install -e .
```

### 3. 装前端

```bash
cd frontend && npm install && cd ..
```

### 4. 启动

两个终端：

**终端 A — 后端**：
```bash
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8080
```

**终端 B — 前端**：
```bash
cd frontend && npm run dev
```

浏览器访问 [http://localhost:5173](http://localhost:5173)，应该能看到「后端健康检查」卡片，状态绿色 `ok`，且 LLM 已配置。

---

## 项目结构

```
novel-studio/
├── plan.md                # 完整实现计划（Phase 0-8）
├── pyproject.toml         # 后端依赖声明
├── .env.example           # LLM 配置模板（复制为 .env.local）
├── docs/
│   └── spike-findings.md  # Phase 0 风险验证报告
├── spikes/                # Phase 0 验证脚本（保留作回归测试用）
│   ├── _common.py
│   ├── 01_runtime.py
│   ├── 02_concurrency.py
│   ├── 03_subagent.py
│   └── 04_providers.py
├── backend/
│   ├── __init__.py
│   ├── main.py            # FastAPI 入口
│   └── config.py          # Settings（从 .env.local 读）
├── frontend/
│   ├── src/
│   │   ├── App.tsx        # 当前：健康检查 demo
│   │   ├── api.ts         # axios 包装
│   │   └── main.tsx
│   ├── vite.config.ts     # /api 代理到 :8080，/ws 代理 WebSocket
│   └── package.json
├── projects/              # 用户运行时数据（已 gitignored）
├── OpenHarness/           # 参考项目（已 gitignored）
├── writeAgent/            # 参考项目（已 gitignored）
└── AI_NovelGenerator/     # 参考项目（已 gitignored）
```

---

## 跑 Phase 0 spike（回归测试）

```bash
.venv/bin/python spikes/01_runtime.py    # 嵌入式 runtime
.venv/bin/python spikes/02_concurrency.py # 多 session 并发
.venv/bin/python spikes/03_subagent.py    # subagent 派遣
.venv/bin/python spikes/04_providers.py   # provider 适配
```

切到 Anthropic 协议跑：

```bash
LLM_API_FORMAT=anthropic LLM_BASE_URL=https://zenmux.ai/api/anthropic \
  .venv/bin/python spikes/01_runtime.py
```

---

## License

MIT
