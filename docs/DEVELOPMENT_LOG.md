# Novel Studio 开发日志

> 记录项目从零到可部署版本的完整开发历程，重点分析 AI Agent 技术的设计决策、用户反馈驱动的迭代、以及开发过程中暴露的设计缺陷。

---

## 一、项目定位与核心理念

Novel Studio 定位为**辅助人类作者**的小说创作工作台，不是全自动写作机器。核心理念：

- 人类控制节奏和创意方向
- AI 负责繁重的初稿生成、一致性校验、文风润色
- 每一步都可以暂停、讨论、手动修改后再继续

这个定位直接决定了后续所有技术选型和架构决策。

---

## 二、技术选型：为什么用 Multi-Agent + Pipeline

### 2.1 为什么不是单一 Agent

小说创作包含多种截然不同的能力需求：

| 能力 | 特征 | 对应 Agent |
|------|------|-----------|
| 结构规划 | 需要全局视野、节奏把控 | planner |
| 正文写作 | 需要文学表达力、场景描写 | writer |
| 质量审查 | 需要批判性思维、严格标准 | reviewer |
| 文风润色 | 需要语言美感、去 AI 味 | polisher |
| 总协调 | 需要任务分派、状态管理 | coordinator |

单一 Agent 很难同时扮演「创作者」和「批评者」——这两个角色需要对立的思维模式。拆分后每个 Agent 有专注的 system prompt、专属的 tools 权限和 skill 知识。

### 2.2 为什么不用 CrewAI / AutoGen 等框架

选择 OpenHarness 作为 Agent 运行时，原因：

1. **轻量**：核心就是 Agent 定义（YAML frontmatter + Markdown）+ 流式事件
2. **可控**：每个 Session 独立，可随时销毁，没有框架级的 Agent 通信协议拖累
3. **透明**：事件流直接暴露给前端，用户能实时看到 Agent 在做什么

### 2.3 Pipeline 而非 Agent 自治

最初考虑过让 coordinator Agent 自行决定下一步该做什么（类似 AutoGPT）。放弃这个方案的原因：

- **不可预测**：用户需要明确知道流程到了哪一步
- **难以中断**：自治 Agent 一旦启动，打断重来的成本高
- **浪费 token**：coordinator 决策本身就消耗大量 token，而流程是固定的

最终选择了**确定性 Pipeline + 用户控制触发**：步骤顺序固定（A→B→C→D→E→F），但用户可以选择只执行部分步骤。

---

## 三、开发阶段与关键决策

### Phase 0：风险验证（Spikes）

在写任何正式代码之前，先做了 4 个 spike 实验：

1. **OpenHarness 集成 spike** — 验证 Agent 定义加载、Session 创建、流式事件接收
2. **FAISS 向量检索 spike** — 验证中文文本切分、Embedding 调用、相似度搜索
3. **WebSocket 流式传输 spike** — 验证前后端实时通信
4. **多步 Pipeline spike** — 验证多个 Agent 串联执行

这些 spike 代码在验证完成后从仓库移除（`chore: remove spikes directory`），但它们确认了技术路线的可行性。

### Phase 1：项目骨架

FastAPI + Vite + React + Ant Design 的标准前后端分离结构。

关键决策：**单端口部署**。生产模式下 uvicorn 同时 serve API 和前端静态文件，避免 CORS 和端口映射的复杂性。开发模式下前端走 Vite dev server + 代理。

### Phase 2：Session + 流式事件

这是整个系统的基础设施层。设计要点：

**NovelSession 的事件广播模型**：
- 一个 Session 可以有多个 subscriber（`asyncio.Queue`）
- Pipeline 订阅来收集 Agent 输出
- WebSocket 订阅来推送给前端
- Queue 满时丢弃事件而不是阻塞（防止慢消费者拖垮系统）

**StreamEvent 序列化**：
- OpenHarness 的内部事件类型被映射为简单的 `{type, data, ts}` JSON
- 这个映射层隔离了前端对 OpenHarness 内部实现的依赖

### Phase 3：Agent 迁移

从之前的 writeAgent 项目迁移了 5 个 Agent 定义和配套的 skill 文件。

**Agent 边界设计**：
- planner 是唯一可以写 `bible/` 目录的 Agent
- reviewer 被显式禁止 Write/Edit 工具（`disallowed_tools`）
- writer 只写 `chapters/` 和 `plans/` 目录

**Skill 系统**：
- Skill 是 Agent 可在运行时通过 `skill` 工具调用加载的知识模块
- 包含模板文件（如 review-report-template.md、plan-template.md）
- 比直接写进 system prompt 更灵活——Agent 按需加载，节省 context window

### Phase 4-5：Pipeline + RAG

**Pipeline 的文件回读机制**：
- 对于 "自治" 步骤（PLAN、WRITE），Agent 可能直接用 Write 工具写文件
- Pipeline 完成后先尝试从磁盘读文件（`_read_step_output`）
- 如果文件存在就用文件内容，否则用 Agent 的 stdout 输出
- 这样 Agent 是否用工具写文件都不影响 Pipeline 的正确性

**RAG 的失败容忍设计**：
- `search_relevant_chunks` 内部 catch 所有异常，返回空字符串
- 原因：RAG 是增强手段，失败不应阻断整个 Pipeline
- Embedding 服务不可用时，Pipeline 依然可以跑——只是少了前文参考

### Phase 6：前端 MVP

6 个页面：Projects（项目列表）、Workbench（工作台）、Chapters（章节编辑器）、Bible（设定集）、PromptStudio（提示词编辑）、Settings（LLM 配置）。

### Phase 7：任务持久化

**TaskCard 设计**：
- 独立于 Pipeline 的持久化层
- `registry.json` 文件存储全部任务
- 原子写入（tempfile + os.replace）防止写入中断导致数据损坏
- 启动时 `recover_interrupted_tasks()` 把残留的 "running" 状态标记为 "failed"

### Phase 8：Docker 打包

多阶段构建：Node Alpine 编译前端，Python slim 运行后端。

---

## 四、用户反馈驱动的迭代

以下是开发对话中用户给出的关键反馈，以及对应的设计修正：

### 4.1 "没有和模型讨论的环节"

**用户原话**：*"好像没有人工意见窗口，比如我对 review 有什么其他意见，对大纲有什么其他意见，虽然可以直接修改，但好像没有和模型讨论的环节"*

**暴露的问题**：原始设计是纯自动化流水线，缺少「人机协作」的核心环节。用户指出：辅助创作 ≠ 一键生成，需要有讨论、碰撞、修改方案的过程。

**解决方案**：实现了 ChatPanel（Drawer 面板），基于已有 Session/WebSocket 基础设施，让用户随时和任意 Agent 对话。讨论结果由 Agent 直接修改文件（因为 Agent 有 Write/Edit 工具权限）。

### 4.2 "生成章节好像直接跑完了"

**用户原话**：*"大纲生成的时候没有讨论吗...生成章节的时候好像也没有讨论，好像直接生成了，可能场景规划或者骨架稿之后，需要讨论一下？"*

**暴露的问题**：Pipeline 一旦触发就跑完全部步骤，没有暂停点。用户无法在规划完成后审阅、讨论、确认再进入写作阶段。

**解决方案**：将"生成章节"拆为两个独立触发：
- "生成规划"：只跑 A+B 步骤（加载上下文 + 规划）
- "开始写作"：跑 C+D+E+F 步骤（写作 + 审查 + 润色 + 定稿）

中间用户可以自由讨论、修改规划文件，满意后再触发写作。

### 4.3 "规划生成之后看不到"

**用户原话**：*"规划生成之后前端页面看不到，chapters 还没生成，所以看不到吗"*

**暴露的问题**：`list_chapters()` 只扫描 `chapters/` 目录。跑完 A+B（只生成规划）后，`plans/ch01-plan.md` 存在但章节列表为空——用户找不到入口查看规划。

**解决方案**：新增 `list_planned_chapters()` 扫描 `plans/` 目录，返回「有规划但无正文」的章节号。前端 ChapterList 合并显示，规划中章节带蓝色标签和不同图标。

### 4.4 "右侧面板无法滚动"

**暴露的问题**：ReviewPanel 使用 antd Tabs，但内容区高度没有正确约束（`height: 100%` 在 Tabs 内不生效）。规划内容超出面板高度时无法滚动。

**解决方案**：改用 `calc(100vh - 偏移)` 显式计算内容高度，配合 CSS class 约束 Tabs 的内容容器。

### 4.5 "讨论完后要怎么触发任务" / "它会把讨论内容带进去吗"

**用户原话**：*"讨论完后要怎么触发任务"*、*"它会把讨论内容带进去吗"*

**暴露的问题**：讨论和生成之间的衔接不清晰——用户困惑于讨论结论如何影响后续生成。

**设计选择**（Approach A）：讨论中 Agent 直接修改文件（plan、bible 等）。后续 Pipeline 触发时从磁盘读取最新文件。这样讨论结论通过文件落地传递，不需要特殊的"记忆传递"机制。简单、透明、可追溯。

### 4.6 超时设置

**用户原话**：*"写作这些改成 10 分钟吧"*

背景：默认 300s（5 分钟）超时在 DeepSeek 等较慢模型上不够用，写长章节时容易超时失败。改为 600s。

---

## 五、原始设计的缺陷分析

### 5.1 缺乏人机交互节点（已修复）

最初的 Pipeline 是完全自动化的"一键到底"模式。这违背了项目"人类主导"的核心理念。Agent 技术的价值不仅在于自动执行，更在于**提供可讨论的中间产物**。

教训：AI 辅助工具的设计应该围绕「人机对话」而非「人机委托」。

### 5.2 Agent 输出的双通道问题

Agent 有两种方式产出结果：
1. 通过 Write 工具直接写文件（自治模式）
2. 通过 stdout 输出文本（被动模式）

Pipeline 需要处理这两种情况（`_read_step_output` + 文本回退）。这增加了复杂度，也导致了一些边界情况：

- Agent 写了文件但 stdout 也输出了内容 → 以文件为准
- Agent 没写文件（比如工具调用失败）→ 用 stdout
- Agent 写了文件但内容不完整 → 目前没有检测机制

如果重新设计，可能会统一为一种模式。

### 5.3 没有 Agent 输出质量校验

Pipeline 接收 Agent 输出后直接存储，没有验证：
- 字数是否合理（可能 Agent 只输出了一段话就停了）
- 格式是否符合模板要求
- 内容是否和输入 prompt 相关

这是一个已知的 gap，未来可以加 guardrail 层。

### 5.4 Session 生命周期管理

每个 Pipeline 步骤创建一个新 Session，执行完立刻销毁。这意味着：
- Agent 没有跨步骤的记忆（context 通过 prompt 传递，不是对话历史）
- 如果 Pipeline 中途失败，之前步骤的 Session 已经不存在了

好处：资源干净、不会泄漏。
坏处：Agent 无法参考自己在前一步骤的"思考过程"。

### 5.5 前端代理端口不一致

Vite 代理最初硬编码指向 8080（项目约定端口），但开发时我用 `--port 8000` 启动后端，导致前端无法连接。这个低级问题暴露了配置管理的缺失——应该在一个地方定义端口，而不是多处硬编码。

---

## 六、AI Agent 的技术实现细节

### 6.1 Agent 定义格式

```yaml
---
name: writer
description: 小说正文写手
tools: [Read, Write, Edit, Grep, Glob]
disallowed_tools: []
skills: [writer-skill, deai-rules, hook-techniques]
max_turns: 16
permission_mode: bypassPermissions
---

# System Prompt（Markdown 格式）
你是一个专业的小说写手...
```

**设计考量**：
- `max_turns` 限制 Agent 的最大交互轮次，防止无限循环
- `permission_mode: bypassPermissions` 让 Agent 不需要人工确认就能执行工具
- `disallowed_tools` 提供负面约束（reviewer 禁止修改文件）
- `skills` 列表声明可用的知识模块

### 6.2 Agent 加载与缓存

```python
@lru_cache(maxsize=1)
def _load_all():
    return load_agents_dir(agents_dir)
```

使用 `lru_cache` 避免每次请求都从磁盘读取。但提供了 `reload_agents()` 手动刷新——用户在 PromptStudio 修改 Agent 后可以重新加载。

### 6.3 Session 与 Agent 的关系

```
SessionManager
  └── create_for_agent(agent_name, project_cwd)
        ├── 从 AgentDefinition 读取 system_prompt、max_turns、tools
        ├── 从 Settings 读取 model、api_key、base_url
        ├── 构建 SessionConfig
        └── 创建 NovelSession → 启动 RuntimeBundle
```

一个 Agent 定义可以同时有多个 Session 实例（比如用户聊天 + Pipeline 都在用 planner）。

### 6.4 Prompt 工程：上下文注入

Pipeline 为每个步骤构建完整的 prompt，注入所有相关上下文：

```
[任务指令] 请为第 N 章创建详细的场景规划。

[全局摘要] 前文摘要：...（bible/global_summary.md）
[角色状态] 角色状态：...（bible/character_state.md）
[前章结尾] 上一章结尾：...（chapters/ch{n-1}.md 末尾 2000 字）
[Bible 设定] 角色设定/世界观/剧情规划：...
[RAG 结果] 相关前文片段：...（FAISS 检索 top-8）
[已有规划] 已有规划（参考）：...（plans/chNN-plan.md）
[输出模板] 请按以下模板格式输出：...（skill 模板文件）
```

**设计决策**：宁可 prompt 长一点（提供充分上下文），也不要让 Agent 因为缺乏信息而产出不一致的内容。

### 6.5 RAG 的定位：增强而非依赖

RAG 在本项目中的角色是**辅助一致性**，不是核心生成引擎：
- 搜索前文相关片段，帮助 Agent 避免前后矛盾
- 排除当前章节自身的内容（防止自引用）
- 失败时返回空字符串，不阻断流程

向量存储使用 FAISS（本地文件，无需额外服务），在 Finalize 步骤将新章节切分后入库。

---

## 七、测试策略

### 7.1 测试金字塔

```
Unit Tests (核心)
  ├── 工具函数：text_splitter、blueprint_parser、prompt_format
  ├── 数据层：workspace 文件操作、task repository
  ├── 序列化：stream event → JSON
  └── 向量引擎：FAISS 增删查、dimension 校验

Integration Tests (中间层)
  ├── API 端点：FastAPI TestClient 测试完整请求/响应
  ├── Pipeline 步骤：mock Agent 输出，验证步骤串联逻辑
  └── Session 生命周期：创建 → 订阅 → 广播 → 销毁

E2E Tests (缺失)
  └── 未实现：完整 Pipeline 跑真实 LLM 的端到端测试
```

### 7.2 Mock 策略

Agent 的 LLM 调用通过 mock `build_runtime` 来模拟：

```python
@pytest.fixture
def mock_build_runtime():
    async def _build(*args, **kwargs):
        # 返回预制的 StreamEvent 序列
        for event in fake_events:
            yield event
    with patch("backend.runtime.session.build_runtime", side_effect=_build):
        yield
```

Pipeline 测试 mock 的是 `SessionManager.create_for_agent`，返回一个 mock session，其 queue 预填了事件。这样可以验证 Pipeline 的流程逻辑而不依赖 LLM。

### 7.3 测试覆盖的决策

优先覆盖：
- **数据完整性**：workspace 的路径遍历防护、task registry 的原子写入
- **Pipeline 控制流**：步骤顺序、取消、错误传播、事件回调
- **序列化边界**：所有 StreamEvent 类型都有对应的序列化测试

不覆盖：
- LLM 输出质量（无法确定性验证）
- 前端 UI（依赖手动测试 + 截图确认）

---

## 八、持久化设计

### 8.1 项目数据（文件系统）

选择文件系统而非数据库，原因：
- 小说内容天然是文本文件（Markdown）
- 用户可以用任何编辑器直接修改
- Git 友好，可以版本控制整个项目
- 部署简单，不需要数据库服务

目录结构：
```
projects/my-novel/
├── bible/
│   ├── characters/        # 角色档案（多文件）
│   ├── worldbuilding/     # 世界观设定
│   ├── plot/              # 剧情规划 + 大纲
│   ├── global_summary.md  # 自动维护的前文摘要
│   └── character_state.md # 自动维护的角色状态
├── plans/                 # 章节规划
├── chapters/              # 章节正文
├── reviews/               # 审查报告
├── vectorstore/           # FAISS 索引 + 元数据
└── journal.jsonl          # 操作日志
```

### 8.2 任务数据（JSON 文件）

`TaskCard` 存储在 `registry.json`：

- 原子写入（write to temp → rename）防止损坏
- 启动时恢复中断的任务
- 简单查询（全量加载、内存过滤）

不用数据库的原因：任务量小（一个项目几十到几百个任务），文件够用。

### 8.3 向量数据（FAISS 文件）

- `index.faiss`：向量索引
- `metadata.jsonl`：每个向量对应的文本和元数据
- `dimension.txt`：向量维度（用于一致性校验）

更新策略：章节 finalize 时，先删除该章节旧数据（`delete_by_chapter`），再重新入库。

---

## 九、日志与可观测性

### 9.1 结构化事件日志

每个项目有 `journal.jsonl`，记录关键操作：

```json
{"type": "chapter_finalized", "chapter_num": 1, "chunk_count": 12, "ts": "2026-05-15T..."}
```

### 9.2 Pipeline 事件流

Pipeline 执行过程中通过 `event_callback` 发出结构化事件：
- `pipeline.step_start` — 步骤开始
- `pipeline.step_progress` — 中间进度（Agent 的每个事件）
- `pipeline.step_complete` — 步骤完成
- `pipeline.step_failed` — 步骤失败
- `pipeline.done` — Pipeline 完成

这些事件通过 WebSocket 实时推送给前端。

### 9.3 Python logging

使用标准 `logging` 模块，Pipeline 失败时 `log.exception()` 记录完整堆栈。

---

## 十、部署经验

### 10.1 Docker 构建的坑

开发过程中遇到的 Docker 问题（按时间顺序）：

1. **缺少 README.md**：`pyproject.toml` 声明了 `readme = "README.md"`，但 Dockerfile 没 COPY 进去，hatchling 构建失败
2. **平台绑定**：`package-lock.json` 在 macOS 生成，不包含 `@rollup/rollup-linux-x64-musl`，Docker 用 Alpine Linux 时找不到原生绑定
3. **node_modules 覆盖**：`COPY frontend/ ./` 把本地 macOS 的 node_modules 覆盖了容器里正确安装的

解决方案：
- `.dockerignore` 排除 `frontend/node_modules`、`frontend/dist`、`frontend/package-lock.json`
- Dockerfile 只 COPY `package.json`（不含 lock），让 `npm install` 为目标平台重新解析
- COPY `README.md` 给 hatchling

### 10.2 镜像加速

中国服务器构建时，npm 和 pip 走国际源很慢。通过 `ARG` 支持构建时注入镜像：

```dockerfile
ARG NPM_REGISTRY=https://registry.npmjs.org
ARG PIP_INDEX=https://pypi.org/simple/
```

国内构建：
```bash
docker build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  --build-arg PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/ \
  -t novel-studio:1.0 .
```

### 10.3 Nginx 反向代理

关键点：WebSocket 需要单独配置 `Upgrade` 和 `Connection` header，且 `proxy_read_timeout` 要覆盖 Pipeline 的最大超时（600s）。

---

## 十一、反思与未来方向

### 做对了的事

1. **Phase 0 的 spike 验证** — 避免了在错误技术方向上投入大量时间
2. **Pipeline 步骤可选** — 后端从一开始就支持 `steps` 参数，后来拆分阶段时几乎不需要改后端
3. **事件流架构** — WebSocket + Queue 模型一次设计，Chat 和 Pipeline 都能用
4. **文件系统持久化** — 简单、透明、Git 友好，用户可以直接看和改文件

### 做错了的事

1. **初始设计忽略人机交互** — 花了大量时间补 ChatPanel 和分阶段触发
2. **端口管理不一致** — vite.config.ts 和启动命令各自硬编码，导致多次调试
3. **Docker 构建未早期验证** — 积累了 5 个连续 fix commit 才把 Docker 跑通
4. **前端 antd 版本适配** — 使用 antd 6 但按 antd 5 的 API 写代码，导致 deprecation warning 和样式问题

### 未来可以改进的方向

1. **讨论结论自动摘要** — Agent 讨论后自动把结论写入文件，而不是依赖用户手动确认
2. **输出质量 guardrail** — 检测 Agent 输出的字数、格式、相关性
3. **跨步骤 Agent 记忆** — 在 Pipeline 内复用同一个 Session，让 Agent 有连续对话上下文
4. **增量 RAG 更新** — 目前每次 finalize 都重建该章节的索引，大型小说可能需要更高效的策略
5. **前端 E2E 测试** — 目前前端完全依赖手动验证
6. **多用户 / 多项目并发** — 当前设计是单用户的，没有认证和资源隔离

---

## 十二、关键技术指标

| 指标 | 数值 |
|------|------|
| 总 commit 数 | 31 |
| 后端测试数 | 212 |
| Agent 数量 | 5 |
| Skill 数量 | 6 |
| Pipeline 步骤 | 6 (A→F) |
| 单步超时 | 600s (10 min) |
| RAG top-k | 8 |
| 文本切分粒度 | ~500 字/chunk |
| WebSocket 队列容量 | 500 events/subscriber |
| 前端页面数 | 6 |

---

## 十三、对话中的关键设计讨论摘要

| 讨论话题 | 用户立场 | 最终决策 |
|----------|----------|----------|
| 讨论面板形式 | "右侧可展开的面板" | Drawer 组件 |
| 讨论后如何触发 | 用户选择方案 A | 讨论修改文件 → 手动触发下一步 |
| 讨论内容是否带入 Pipeline | 关注传递机制 | 通过文件落地传递 |
| 超时时间 | "改成 10 分钟" | 300s → 600s |
| 规划章节不可见 | "生成后看不到" | 扫描 plans/ 目录，合并显示 |
| UI 方案选择 | "UI 会不会太挤" | 选择方案 1（合并列表） |
| npm 源 | "换掉内网的" | 项目级 .npmrc + lock 文件重生成 |
| Docker 构建镜像 | "国内会不会慢" | build-arg 支持注入镜像 |

---

*最后更新：2026-05-19*
