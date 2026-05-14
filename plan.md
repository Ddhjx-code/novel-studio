# AI 小说创作辅助工具 — 融合实现计划

> **定位**：辅助人类作者完成小说创作的工作台，**不是**全自动写作机器。
> 核心能力是「一键生成大纲」「一键生成单章」「一键审查/润色」，每个能力可独立调用，人类全程主导节奏与创意。

## 源项目

| 项目 | 地址 | 贡献内容 |
|------|------|----------|
| **OpenHarness** | https://github.com/HKUDS/OpenHarness | Agent 运行时底座：subagent 分派、tool 系统、hook、skill/agent 加载器、22 个 LLM provider |
| **writeAgent** | https://github.com/Ddhjx-code/writeAgent | 工作流方法论：4 个 Agent 分工、骨架→扩展两阶段写作、十维度审查、去 AI 味 prompt 库、bible 文件结构约定 |
| **AI_NovelGenerator** | https://github.com/YILING0013/AI_NovelGenerator | RAG 三步 pipeline、定稿三件套（摘要+角色状态+向量）、章节蓝图解析、6-provider embedding 适配器、独家 prompt（雪花法 / 双演化方向摘要） |

## 最终产品

一个 **本地 Web 应用**（浏览器即用），用户视角：

- **辅助产出**：点按钮生成大纲 / 人物档案 / 单章正文 / 审查报告 / 润色稿
- **全程可控**：任何 AI 产物都可即时手工编辑、重新生成、对比版本
- **长文一致性自动维护**：每次章节定稿自动滚动更新「全书摘要 + 角色状态 + 向量索引」
- **不强制全自动**：可以一章一章生成，也可以连写多章；用户决定停在哪
- **零 Claude 依赖知识**：所有 Agent 提示词在 UI 里编辑，模型/API Key 在 UI 里配置

## 技术栈

| 层 | 技术选型 | 说明 |
|----|----------|------|
| 前端 | React + Vite + Antd | SPA，浏览器访问，含 Monaco 编辑器 |
| 后端 | FastAPI (Python) | REST + WebSocket |
| Agent 运行时 | OpenHarness (`openharness-ai` PyPI 包) | **嵌入式调用**：`build_runtime + QueryEngine.submit_message`，async API，不走 subprocess |
| 向量存储 | FAISS (`faiss-cpu`) | 替代 Chroma，依赖体积 ~200MB → ~30MB |
| Embedding | OpenAI 兼容 / Ollama / Gemini / SiliconFlow | 复用 AI_NovelGenerator 的 6-provider 适配器（去 langchain） |
| 事件流 | OpenHarness `AsyncIterator[StreamEvent]` → FastAPI WebSocket | 包装层 ~50 行 |
| 持久化 | 项目目录 + JSONL journal | 借鉴 OpenHarness autopilot 的 registry+journal 模式 |

## 关键架构决策

1. **Python 编排 + Agent 思考双层**：Python 控制流程骨架（单章触发、人机暂停、超时重试、状态持久化、并发隔离），Agent 在每个 Step 内做创意决策。不全靠 prompt 自律，也不全 Python 写死。
2. **单章为最小工作单元**：所有自动化以「一章」为粒度。"连续写多章"是循环调用单章流水线，不是另一套流程。
3. **文件即记忆**（沿用 writeAgent）：所有 bible/plans/chapters/reviews 落盘为 Markdown，Agent 间通过文件交接而非消息。
4. **OpenHarness embedded mode**：直接 `import openharness` 跑在 FastAPI 进程内，不开 subprocess（实测 `build_runtime/QueryEngine.submit_message` 是干净 async API）。
5. **Hook 用 HTTP 回调本进程**：OpenHarness hook 是 settings.json 声明式（`command/prompt/http/agent`），用 `http` hook 在 `PreToolUse / PostToolUse / SubagentStop` 回调 FastAPI，做纪律校验和事件采集。

## 项目目录结构

```
novel-studio/
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── runtime/                   # OpenHarness 包装层
│   │   ├── session.py             # build_runtime 封装，生命周期管理
│   │   ├── stream.py              # StreamEvent → WebSocket 转发
│   │   └── hooks_endpoint.py     # 接收 OpenHarness 的 http hook 回调
│   ├── orchestrator/              # 创作流程编排（Python 层）
│   │   ├── chapter_pipeline.py    # 单章生成流水线（核心）
│   │   ├── outline_pipeline.py    # 大纲/人物/世界观生成
│   │   ├── review_pipeline.py     # 独立审查/润色任务
│   │   └── finalize.py            # 定稿三件套：摘要+状态+向量
│   ├── agents/                    # Agent 定义（OpenHarness 格式）
│   │   ├── coordinator.md
│   │   ├── planner.md
│   │   ├── writer.md
│   │   ├── reviewer.md
│   │   └── polisher.md
│   ├── skills/                    # 复用 writeAgent 的 SKILL 包
│   │   ├── planner-skill/
│   │   ├── writer-skill/
│   │   ├── reviewer-skill/
│   │   ├── polisher-skill/
│   │   └── shared/
│   ├── tools/                     # 自定义工具（继承 BaseTool）
│   │   ├── consistency_check.py
│   │   ├── semantic_search.py     # RAG 三步 pipeline
│   │   └── chapter_blueprint_parser.py
│   ├── vectorstore/
│   │   ├── engine.py              # FAISS 封装
│   │   ├── text_splitter.py       # 中文切分（重写，不用 nltk）
│   │   ├── embedding.py           # 6-provider 适配器
│   │   └── ingest.py              # 章节入库
│   ├── projects/                  # 项目 CRUD + 持久化
│   │   ├── repository.py          # registry.json + journal.jsonl
│   │   └── workspace.py           # 项目目录管理
│   └── api/
│       ├── config.py
│       ├── projects.py
│       ├── chapters.py            # 单章 CRUD + 触发生成
│       ├── outline.py             # 大纲/人物/世界观触发
│       ├── reviews.py             # 审查/润色触发
│       ├── agents_skills.py       # Agent/Skill 提示词编辑
│       └── ws.py                  # WebSocket 端点
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Projects.tsx       # 项目列表
│   │   │   ├── Workbench.tsx      # 单项目工作台（核心页面）
│   │   │   ├── Chapter.tsx        # 单章编辑器（核心页面）
│   │   │   ├── Bible.tsx          # 圣经编辑器
│   │   │   ├── PromptStudio.tsx   # Agent/Skill 提示词编辑器
│   │   │   └── Settings.tsx
│   │   └── components/
│   │       ├── StreamConsole.tsx  # 实时事件流
│   │       └── HumanGate.tsx      # 人机交互节点
│   └── package.json
├── projects/                      # 用户项目数据（运行时生成）
│   └── <project_name>/
│       ├── bible/
│       │   ├── characters/
│       │   ├── worldbuilding/
│       │   ├── plot/
│       │   ├── global_summary.md  # 滚动摘要（每次定稿更新）
│       │   └── character_state.md # 滚动角色状态（每次定稿更新）
│       ├── plans/                 # chNN-plan.md, chNN-skeleton.md
│       ├── chapters/              # chNN.md
│       ├── reviews/               # chNN-review.md
│       ├── vectorstore/           # FAISS 索引文件
│       └── journal.jsonl          # 事件流持久化
├── pyproject.toml
└── README.md
```

---

## Phase 0 — 技术风险 Spike（1-2 天）

**目标**：在写任何业务代码前，验证最大的几个未知。

### 0.1 OpenHarness 嵌入式跑通

写 `spikes/01_runtime.py`（约 50 行）：
- `from openharness.ui.runtime import build_runtime, start_runtime, close_runtime`
- 加载一个测试 agent
- `bundle.engine.submit_message("写一段话")` → 异步消费 `StreamEvent`
- 打印 `AssistantTextDelta` / `ToolExecutionStarted/Completed`

### 0.2 多 session 并发

`spikes/02_concurrency.py`：
- 同时 `build_runtime` 两个不同 cwd 的 session
- 各自发消息，确认互不干扰
- **如果不支持，部署架构需重新设计**（每项目独占进程 vs 共享进程）

### 0.3 Subagent 派遣

`spikes/03_subagent.py`：
- 主 Agent 通过 `AgentTool`（subagent_type 参数）派 `planner` 子 Agent
- 验证子 Agent 是否独立上下文窗口
- 验证派单时能否传"文件路径"让子 Agent 自己读，而不是在 prompt 里塞内容（bible 可能很大）

### 0.4 LLM Provider 适配

`spikes/04_providers.py`：
- 各试通一个 OpenAI / DeepSeek / Ollama 模型
- 确认 OpenHarness 的 `api/registry.py` 自动检测能识别我们的 base_url 配置

**通过标准**：4 个 spike 全部跑通，发现的问题写到 `docs/spike-findings.md`。

---

## Phase 1 — 项目骨架

**目标**：最小可运行的前后端框架。

- 创建 `backend/` 和 `frontend/` 子目录
- 后端：`uvicorn backend.main:app --reload` 能起，`/health` 返回 200
- 前端：`npm run dev` 能起，能打到后端 `/health`
- 初始化 git、`.gitignore`、`pyproject.toml`、`requirements.txt`
- 配置 CORS（前端 dev server → 后端）

---

## Phase 2 — Runtime + WebSocket（合并原 Phase 2 + Phase 7）

**目标**：把 OpenHarness 嵌进 FastAPI，事件能实时推到浏览器。

### 2.1 Runtime 包装层（`backend/runtime/session.py`）

- 封装 `build_runtime` 调用
- 提供 `NovelSession` 类：`start(project_dir, model_config)` / `submit(prompt)` / `stop()`
- 模型配置走构造参数，不读全局环境变量（多项目隔离）

### 2.2 Stream → WebSocket 转发（`backend/runtime/stream.py`）

- `AsyncIterator[StreamEvent]` 转换为标准化 JSON 事件
- 事件类型：`agent.text` / `agent.tool_call` / `agent.tool_result` / `agent.subagent_start` / `agent.subagent_end` / `pipeline.step` / `human.gate` / `error`
- 支持多客户端订阅同一 session

### 2.3 WebSocket 端点（`backend/api/ws.py`）

- `/ws/sessions/{session_id}` 推送会话级事件
- `/ws/projects/{project_name}` 订阅项目级事件流

### 2.4 验证

- 前端连 WebSocket，调一个测试 agent，浏览器实时看到流式文本输出

---

## Phase 3 — 移植 writeAgent 的 Agent + Skill 体系

**目标**：4 个子 Agent + 1 个主 Agent + 5 个 Skill 包注册到 OpenHarness。

### 3.1 Agent 定义文件适配

writeAgent 原始 `.md` 文件**没有 OpenHarness 要求的 frontmatter 字段**，需要补：

```yaml
---
name: planner
description: 规划与归档子 Agent，bible 唯一写入者
tools: [Read, Write, Edit, Grep, Glob]
skills: [planner-skill]
model: claude-sonnet-4-6   # 可被 UI 覆盖
---
```

- `planner` — 上述配置
- `writer` — `tools: [Read, Write, Edit]`, `skills: [writer-skill]`
- `reviewer` — `tools: [Read, Grep, Glob]`, `disallowed_tools: [Write, Edit, Bash]`, `skills: [reviewer-skill]`，强制只读纪律
- `polisher` — `tools: [Read, Write, Edit]`, `skills: [polisher-skill]`

主提示词内容直接复用 writeAgent 对应 `.md` 的 body。

### 3.2 主协调 Agent（简化版）

`backend/agents/coordinator.md`：复用 `writeAgent/.claude/CLAUDE.md` 核心理念，但**简化为辅助模式**——不主动规划"全书走向"，只在用户触发任务时分派对应子 Agent。删除"每 5 章自动里程碑""自动跑全书"等相关段落。

### 3.3 Skill 文件复用

`writeAgent/.claude/skills/` 整目录复制到 `backend/skills/`。SKILL.md 的 frontmatter 是标准 Claude Code 格式，OpenHarness 的 `_frontmatter.py` 接受 `name + description`，多余字段（`user-invocable` 等）按需补。

### 3.4 注册与验证

- 启动时 `load_skill_registry(cwd, extra_skill_dirs=[skills_dir])`
- 把 4 个子 AgentDefinition 加到 `get_all_agent_definitions()`
- API `GET /api/agents` 列出所有 Agent，确认 5 个都在
- 测试主 Agent 能用 `AgentTool` 派 planner 子 Agent

---

## Phase 4 — 单章生成流水线（核心）

**目标**：把"一键生成一章"做扎实。其他所有能力都是这条流水线的子集或简化版。

### 4.1 流水线编排（`backend/orchestrator/chapter_pipeline.py`）

Python 控制以下顺序，每步通过 OpenHarness 派对应子 Agent：

```
[必选] Step A — 读取上下文（Python，无 LLM）
  → 加载本章大纲、人物档案、global_summary、最近 N 章摘要
  → 走 RAG 三步：planner 生成关键词 → 向量召回 → planner 过滤
  → 输出：context_bundle（结构化对象）

[必选] Step B — 场景规划（planner 子 Agent）
  → 输入：context_bundle
  → 输出：plans/chNN-plan.md

[可选] Step B.5 — 规划自检（reviewer 快速模式）
  → 仅查结构/因果链/钩子，约 30 秒
  → 不通过 → 退回 Step B（最多 1 次）

[必选] Step C — 写作（writer 子 Agent）
  → 三阶段：骨架 → 分场景扩展 → 拼合
  → 输出：plans/chNN-skeleton.md, chapters/chNN.md

[可选] Step D — 审查（reviewer 子 Agent）
  → 十维度报告：reviews/chNN-review.md
  → 用户在 UI 决定是否要 Step E

[可选] Step E — 润色（polisher 子 Agent）
  → 覆写 chapters/chNN.md，原版备份到 .draft

[必选] Step F — 定稿三件套（Python + planner）
  → 滚动更新 global_summary.md
  → 滚动更新 character_state.md
  → 章节切分 + 入 FAISS 索引
  → 写 journal.jsonl 一条 chapter.finalized 事件
```

### 4.2 流水线参数化

每次触发由 UI 传入：

- `chapter_number: int`
- `steps: list["A","B","B.5","C","D","E","F"]` — 用户可只跑 Step C 重写正文，或只跑 Step D 重审
- `regenerate: bool` — 覆盖已有产物
- `model_overrides: dict[agent_name, model]` — 个别步骤换模型（如 polish 用便宜模型）

### 4.3 人机交互节点（轻量化）

不再有"每 5 章强制暂停"。改为：

- **可选暂停点**：用户在触发时勾选「规划后等我确认」「审查后等我确认」
- **暂停机制**：流水线 await 一个 future，前端通过 `POST /api/sessions/{id}/resume` 推进
- **始终允许中断**：`POST /api/sessions/{id}/cancel` 立即取消

### 4.4 大纲 / 人物 / 世界观流水线（`backend/orchestrator/outline_pipeline.py`）

简化版：单步派 planner，输入用户简述 + 现有 bible，输出对应文件。同样支持「重新生成」「人工编辑后再保存」。

### 4.5 独立审查 / 润色（`backend/orchestrator/review_pipeline.py`）

用户对一段已存在文本（不必是 AI 生成的）触发审查或润色——把这两个 Agent 解耦出来当独立工具用。这是"辅助"定位的关键：用户写了一段，让 AI 看一眼或润一下。

### 4.6 验证

- API `POST /api/projects/{name}/chapters/{n}/generate` 触发完整 6 步
- WebSocket 实时看到每步状态
- 章节产物正确落盘
- 重跑只 Step E 能换一份润色稿
- 独立调用「审查我手写的这段文字」走通

---

## Phase 5 — RAG 与一致性维护（建议与 Phase 4 并行）

**目标**：长文一致性的技术支柱。Phase 4 的 Step A 和 Step F 依赖本 Phase。

### 5.1 FAISS 引擎（`backend/vectorstore/engine.py`）

- `add_chunks(chunks: list[Chunk])` — Chunk 含 `text + chapter_num + scene_id + role`
- `search(query, top_k=5, filter: dict = None)` — 支持按章号区间过滤
- `delete_by_chapter(n)` — 重写章节时清旧
- 持久化到 `projects/<name>/vectorstore/{index.faiss, metadata.jsonl}`

### 5.2 中文文本切分（`backend/vectorstore/text_splitter.py`）

**不复用 AI_NovelGenerator 原版**（用了英文 nltk.sent_tokenize，中文场景会被当成一整句吞掉）。重写：

- 按 `[。！？\n]` 正则切句
- 累加到 ~500 字符开新段
- 保留 chapter / scene 元数据

### 5.3 Embedding 适配器（`backend/vectorstore/embedding.py`）

复用 `AI_NovelGenerator/embedding_adapters.py` 的工厂模式，但**去掉 langchain 依赖**，6 provider 改写约 100 行：
- OpenAI / Azure / Ollama / LM Studio / Gemini / SiliconFlow
- 统一接口：`embed_documents(texts) -> List[List[float]]`、`embed_query(query) -> List[float]`

### 5.4 RAG 三步 Pipeline（`backend/tools/semantic_search.py`）

借鉴 `AI_NovelGenerator/novel_generator/chapter.py::get_filtered_knowledge_context`：

```
1. LLM 生成检索关键词（用 knowledge_search_prompt：实体/事件/地点三类，按优先级）
2. FAISS top-K 召回
3. LLM 过滤重组（用 knowledge_filter_prompt：冲突检测▲ / 价值评估❗ / 结构重组）
```

注册为 OpenHarness `BaseTool`，writer / planner 在 Step A 调用。

### 5.5 章节蓝图解析（`backend/tools/chapter_blueprint_parser.py`）

复用 `AI_NovelGenerator/chapter_directory_parser.py`，把 planner 输出的「第N章 - 标题 / 本章定位 / 核心作用 / 悬念密度 / 伏笔操作 / 认知颠覆 / 简述」七字段文本解析成 dict。

### 5.6 一致性检查工具（`backend/tools/consistency_check.py`）

复用 `AI_NovelGenerator/consistency_checker.py` 的 prompt + 5 段输入（小说设定、角色状态、全书摘要、未解冲突、本章正文）。注册为 BaseTool 供 reviewer 调用。

### 5.7 定稿三件套（`backend/orchestrator/finalize.py`）

借鉴 `AI_NovelGenerator/novel_generator/finalization.py::finalize_chapter`：

```python
def finalize_chapter(project, chapter_num):
    # 1. 滚动更新 global_summary（用 summarize_recent_chapters_prompt 的「继承70/创新30」+ 双演化方向）
    update_global_summary(...)
    # 2. 滚动更新 character_state（用 update_character_state_prompt 的 ASCII 树结构）
    update_character_state(...)
    # 3. FAISS 入库（章节切分 → embedding → add_chunks）
    ingest_chapter_to_vectorstore(...)
    # 4. journal 写一条 chapter.finalized 事件
```

### 5.8 验证

- 写完 3 章后，调 `/api/projects/{name}/search?q=...` 能正确召回前文段落
- 调一致性检查工具能检出注入的剧情矛盾
- `global_summary.md` 是滚动更新（不是覆盖式）
- `character_state.md` 用 ASCII 树格式，能看出角色状态演化

---

## Phase 6a — 最小可用前端（与 Phase 4 并行）

**目标**：能在浏览器触发流水线、看到事件流、读写章节。

### 6a.1 项目管理（`Projects.tsx`）

- 项目列表 / 新建 / 切换 / 删除

### 6a.2 工作台（`Workbench.tsx`，核心页面）

- 当前项目概览：章节数、bible 摘要
- 触发按钮：「生成大纲」「生成新章节」「审查文本」「润色文本」
- 触发表单可选「步骤组合」「人机暂停点」「模型覆盖」
- 实时事件流面板（`StreamConsole.tsx`）

### 6a.3 章节编辑器（`Chapter.tsx`，核心页面）

- 左：章节列表（状态：✅ 定稿 / 🔄 生成中 / ⬜ 未开始）
- 中：Markdown 编辑器（Monaco）
- 右：版本对比 + 审查报告 tab
- 「重新生成」按钮 → 触发流水线（可选步骤组合）
- 「保存修改」直接写文件

### 6a.4 设置页（`Settings.tsx`）

- API Key / 模型 / Embedding provider 配置
- 配置存到后端 `~/.novel-studio/config.json`

---

## Phase 6b — 高级编辑器（可后做）

### 6b.1 Bible 编辑器（`Bible.tsx`）

- Tab 切换：人物 / 世界观 / 大纲 / 情节追踪 / global_summary / character_state
- 每个 tab 是文件树 + Markdown 编辑器

### 6b.2 Prompt Studio（`PromptStudio.tsx`）

- Agent / Skill 列表，Monaco 编辑 `.md` 文件
- 保存即生效（下次任务用新提示词）
- 可对 prompt 做版本管理（保存历史快照）

---

## Phase 7 — 持久化 + Autopilot 范式

**目标**：项目状态可恢复、任务可重试、借鉴 OpenHarness 现成模式。

### 7.1 Project Repository（`backend/projects/repository.py`）

借鉴 `openharness/autopilot/service.py::RepoAutopilotStore`：

- `registry.json` — 项目元数据（名字、创建时间、当前章节、模型配置）
- `journal.jsonl` — 项目级事件流（章节生成、定稿、审查、用户编辑）
- 重启后从 journal 重建状态

### 7.2 任务重试 / 重做

每次生成是一个 task，task 失败可重试，可在 UI 看历史。

---

## Phase 8 — 打包与分发

### 8.1 一键启动脚本

`setup.sh` / `setup.ps1`：

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

前端 build 后由 FastAPI `StaticFiles` 托管，单端口访问。

### 8.2 Docker 镜像（可选）

`Dockerfile` 多阶段构建。

### 8.3 桌面应用打包（可选）

PyInstaller / Tauri 包成单 exe / dmg。

---

## 关键依赖

```
# Python 后端
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
openharness-ai>=0.1.9
faiss-cpu>=1.7.4
openai>=1.0.0
httpx>=0.27.0
pydantic>=2.0.0
python-multipart>=0.0.9
pyyaml>=6.0
websockets>=12.0
# 注意：不需要 langchain、chromadb、torch、transformers、nltk
# 这些都是 AI_NovelGenerator 抽取后可丢的重依赖（~3GB → <50MB）

# Node.js 前端
react>=18.0
antd>=5.0
@monaco-editor/react
axios
react-router-dom
```

## 执行顺序

```
Phase 0 → 风险 Spike（验证 OH 嵌入、并发、subagent、provider）
   ↓
Phase 1 → 前后端骨架
   ↓
Phase 2 → Runtime + WebSocket
   ↓
Phase 3 → 移植 Agent + Skill
   ↓
┌─ Phase 4 → 单章流水线（核心）
├─ Phase 5 → RAG + 一致性                          ← 三者并行
└─ Phase 6a → 最小前端
   ↓
Phase 6b → 高级编辑器（Bible / Prompt Studio）
   ↓
Phase 7 → 持久化 + Autopilot 范式
   ↓
Phase 8 → 打包分发
```

每 Phase 验证标准：

- Phase 0：4 个 spike 全部跑通，`docs/spike-findings.md` 记录发现
- Phase 1：前后端能起，能联通
- Phase 2：浏览器能实时看到 Agent 流式文本
- Phase 3：API 能列出 5 个 Agent，主 Agent 能派子 Agent
- Phase 4：API 触发单章生成 6 步完整跑完，文件正确落盘；独立调用「审查我手写的文字」走通
- Phase 5：RAG 能召回前文，定稿三件套自动跑，能检出剧情矛盾
- Phase 6a：浏览器能完成「生成大纲 → 生成章节 → 审查 → 润色 → 编辑保存」全流程
- Phase 6b：Bible 和 Prompt 能在 UI 编辑
- Phase 7：重启服务后项目状态完整恢复
- Phase 8：朋友能照着 README 一键跑起来

## 风险清单

- 🔴 **OpenHarness 多 session 并发** — Phase 0 必须验，否则部署模型大变
- 🔴 **主 Agent 上下文爆炸** — 验主 Agent 自身有 auto-compact，否则长项目用不下去
- 🟡 **AgentTool 派子 Agent 时 prompt 大小** — bible 大要让子 Agent 自己读文件，不在 prompt 里塞
- 🟡 **Skill frontmatter 兼容** — writeAgent 的 SKILL.md 字段集与 OpenHarness 不完全一致（OH 多 `user-invocable` / `disable-model-invocation` 等），要按需补
- 🟡 **中文 embedding 选择** — OpenAI embedding 中文一般，可选配 BGE / Qwen
- 🟡 **OpenHarness http hook 同步阻塞** — 量大可能拖慢，必要时换 `agent` hook
