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

## 十二、LLM 写作质量问题与应对策略

### 12.1 五大核心问题

LLM 生成小说文本有五个系统性缺陷：

| # | 问题 | 表现 | 根因 |
|---|------|------|------|
| 1 | 比喻过多 | 无功能比喻堆砌，不传递新信息 | LLM 训练数据中文学文本过度使用修辞 |
| 2 | 排比过多 | 对称/并列结构冗余，多项说同一件事 | "三段式法则"被过度学习 |
| 3 | 解释性旁白 | 叙述者越权解释角色心理、总结场景意义 | LLM 倾向于"说清楚"而非"留白" |
| 4 | 信息量少/逻辑出错 | 每段文字不承载新信息，或因填充导致逻辑链断裂 | 为凑长度而灌水 |
| 5 | 片段反复(模板化) | 同一套反应模式/情绪处理在不同场景中重复出现 | LLM 对某些模式有强烈偏好 |

### 12.2 项目中的应对机制

**层级一：deai-rules skill（规则层面）**

`deai-rules` 是一个详尽的"去 AI 味"规则集，覆盖：

- **内容模式**：过度强调意义、宣传式语言、模糊归因、肤浅分析尾缀、公式化"挑战与展望"
- **语言模式**：高频 AI 词汇清单、系动词回避、否定式排比、三段式过度使用、同义词循环
- **风格模式**：破折号过度使用、粗体滥用、内联标题列表
- **填充模式**：填充短语、过度限定、通用积极结论
- **小说特有模式**：情感标签替代感受、角色声音同质化、叙述节奏均匀、隐喻堆砌、过度对称句式

每条规则都附带 AI 味 vs 人味的对比示例，以及具体的替换策略。

该 skill 被 writer 和 polisher 两个 Agent 共享使用。writer 在扩写阶段加载它来预防问题产生；polisher 在润色阶段加载它来修复已有问题。

**层级二：polisher Agent（执行层面）**

polisher 的职责明确限定在"怎么写"而非"写什么"：
- 去 AI 味（应用 deai-rules）
- 对话语言指纹修正
- 描写精炼
- 节奏微调
- 措辞优化

polisher 有明确的**边界声明**：如果发现问题超出润色范围（需要改情节、补场景、调逻辑），不自行处理，而是记录在报告中建议交回 writer。

**层级三：reviewer Agent（检测层面）**

reviewer 的十维度审查中包含对上述问题的检测：
- 维度审查中检查"叙述节奏是否均匀"
- 检查"角色声音是否同质化"
- 检查"信息量是否足够"

reviewer 是只读的（`disallowed_tools: [Write, Edit, Bash]`），只输出报告不修改文件，确保审查的独立性。

**层级四：项目积累（经验层面）**

`deai-rules` 的末尾有一个"项目积累"段落，记录了特定项目中从人类反馈中总结的规则：
- 禁止心理分析句式
- 避免哲理金句
- 情感不可量化
- 结尾避免说教性总结

这个段落是**可增长的**——每次人类给出新的反馈，都可以追加到这里，形成项目特定的写作风格约束。

### 12.3 效果与局限

**有效的地方**：
- deai-rules 提供了详尽的检查清单，LLM 在被明确告知"不要做 X"时遵从度较高
- writer + polisher 两轮处理形成了"预防 + 修复"的双保险
- 项目积累机制让规则随时间精准化

**依然存在的局限**：
- **遵从度衰减**：LLM 的 context window 越长，对早期 system prompt 中规则的遵从度越低。deai-rules 本身有 4000+ 字，如果被压在 prompt 后部，效果会下降
- **创造力 vs 规则的矛盾**：规则太多会让 LLM 变得保守，产出"安全但无趣"的文字
- **无法检测"不存在的东西"**：规则能发现"不该有的模式"，但无法检测"应该有但没有"的东西（比如缺少环境描写、缺少节奏变化）
- **模型间差异**：不同 LLM 的 AI 味模式不同。deai-rules 主要针对 GPT/DeepSeek 系列训练，换模型可能需要更新

---

## 十三、Agent 边界设计与稳定性

### 13.1 Agent 边界控制

| Agent | 可写范围 | 禁止操作 | 职责边界 |
|-------|----------|----------|----------|
| coordinator | 无（只协调） | 不写长文本 | 分派任务，不执行创作 |
| planner | `bible/`、`plans/` | - | 唯一维护设定集的 Agent |
| writer | `chapters/`、`plans/` | - | 只负责正文生成 |
| reviewer | 无（只读） | Write、Edit、Bash | 只输出报告，不修改任何文件 |
| polisher | `chapters/` | - | 只改"怎么写"，不改"写什么" |

边界通过三种机制强制：
1. **disallowed_tools**（硬约束）：reviewer 被技术层面禁止写入
2. **system prompt 声明**（软约束）：每个 Agent 的 prompt 明确说"你不应该做 X"
3. **语义边界**（polisher 特有）：声明了什么情况超出范围、应交回其他 Agent

### 13.2 稳定性问题

**问题一：Agent 不遵从指令**

LLM 可能无视 system prompt 中的约束。应对方式：
- `disallowed_tools` 提供硬边界（技术层面阻止）
- `max_turns` 限制最大轮次（防止无限循环）
- Pipeline 超时（600s）防止 Agent 卡死

**问题二：Agent 输出不完整**

Agent 可能只输出部分内容就停了。当前处理：
- Pipeline 的 `_read_step_output` 回读文件（如果 Agent 用 Write 写了文件，即使 stdout 不完整也能获取完整内容）
- 如果文件和 stdout 都没有足够内容，Pipeline 仍然会继续（这是一个 gap，没有质量校验）

**问题三：Agent 写错文件路径**

Agent 可能把章节写到错误位置。当前缓解：
- system prompt 明确声明了文件路径约定（`chapters/chNN.md`、`plans/chNN-plan.md`）
- Pipeline 回读时只检查约定路径

**问题四：Agent 之间的隐式依赖**

- planner 维护 `foreshadow-tracker.md` → writer 读取它来决定如何埋/收伏笔
- reviewer 的报告 → polisher 参考它来决定重点润色什么

如果上游 Agent 没有正确维护文件，下游 Agent 就会基于过时信息工作。这个链条的可靠性完全依赖 LLM 的遵从度。

### 13.3 Skill 系统的设计考量

**当前设计：按需加载 vs 预注入**

经过讨论，我们认识到 skill 在两种模式下有不同的最优策略：

| 模式 | 当前做法 | 更优做法 |
|------|----------|----------|
| Pipeline（确定性任务） | Agent 通过 `skill` 工具调用加载 | 核心 skill 直接注入 prompt（Pipeline prompt builder 已部分在做）；次要 skill 保持按需 |
| Chat（开放式讨论） | Agent 按 system prompt 指示加载 | 保持按需，Agent 自主判断 |

**当前的矛盾点**：Pipeline prompt builder 已经从 skill 目录中提取了模板内容注入 prompt（如 `load_template("writer-skill", "chapter-template.md")`），但 Agent 启动后又可能通过 `skill writer-skill` 再加载完整 skill 内容——存在职责重叠和 token 浪费。

**未来优化方向**：Pipeline 模式下，将核心 skill 内容整合进 prompt builder 的注入逻辑，Agent 不再需要自己加载；Chat 模式下保持当前的按需加载机制。

---

## 十四、RAG 与知识持久化的互补设计

### 14.1 三层知识体系

```
                    ┌─────────────────────────────────┐
                    │  Agent 行为约束 (system prompt)   │ ← 确保读取和更新
                    └──────────────┬──────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                           │
┌───────▼────────┐   ┌────────────▼──────────┐   ┌───────────▼──────────┐
│  Bible 直读     │   │  向量检索 (RAG/FAISS)  │   │  结构化追踪文件       │
│                │   │                        │   │                      │
│ · global_summary│   │ · 章节原文 ~500字切片   │   │ · foreshadow-tracker │
│ · character_state│  │ · Embedding 语义搜索   │   │ · suspense-tracker   │
│ · characters/   │   │ · top-8 相似片段       │   │ · progress-tracker   │
│ · worldbuilding/│   │ · 排除当前章节         │   │ · decision-log       │
│ · plot/outline  │   │                        │   │                      │
└────────────────┘   └────────────────────────┘   └──────────────────────┘
      │                        │                           │
      ▼                        ▼                           ▼
  确保"规则"不违反       补充"相关情节细节"         确保"伏笔/悬念"不遗漏
  (确定性，全量注入)     (模糊匹配，尽力而为)       (结构化清单，显式追踪)
```

### 14.2 各层的失效模式

| 层 | 正常工作时 | 失效场景 |
|----|-----------|----------|
| Bible 直读 | 角色设定、世界规则被遵守 | `global_summary` 是 LLM 压缩的，可能丢失细节 |
| RAG 向量检索 | 相关前文被找到，避免矛盾 | query 和目标 chunk 语义距离远时检索不到 |
| 结构化追踪 | 伏笔按时回收，悬念不超期 | planner 没有按规范更新 tracker 文件 |

### 14.3 伏笔/悬念问题的完整解决路径

之前讨论中提到"RAG 搜不到伏笔"的 gap。实际上项目设计中通过 **结构化追踪文件** 已经覆盖了这个问题：

```
伏笔生命周期：
  planner 规划时 → 在 plan-template 中声明"埋设伏笔：XXX"
                 → 更新 bible/plot/foreshadow-tracker.md（记录：内容、埋设章节、预期回收章节）
  后续章节规划时 → planner 读取 tracker，检查"超期未回收"的伏笔
                 → 在新章规划中安排回收
  reviewer 审查时 → 读取 tracker，验证"所有伏笔是否已揭示"
```

这个机制不依赖 RAG 的语义搜索——它是**显式的、结构化的追踪**，类似于项目管理中的 todo list。只要 planner 遵从指令维护 tracker 文件，伏笔就不会被遗忘。

**真正的风险点**：如果 LLM 的遵从度不够，planner 可能跳过更新 tracker 的步骤。这时候伏笔确实会丢失——但这是 Agent 遵从度问题，不是知识存储架构的问题。

### 14.4 RAG 的实际定位

经过分析，RAG 在本项目中的真正价值不是"防止伏笔丢失"（那是 tracker 的工作），而是：

1. **避免描写矛盾**：上一次写酒馆老板是秃头，下次不能写他甩头发
2. **保持氛围连贯**：找到之前描写某个场景的文字风格，保持一致
3. **细节呼应**：之前提到的小物件、环境特征，在相关场景中自然出现

这些都是**局部性的、描写层面的一致性**，和伏笔这种**全局性的、结构层面的一致性**是不同层次的问题。

---

## 十五、LLM 遵从度问题

Agent 系统的一切设计最终都依赖一个前提：LLM 会遵从 system prompt 中的指令。实际情况：

**遵从度较高的场景**：
- 明确的"禁止"指令（如 reviewer 的"只读不写"）——尤其当 `disallowed_tools` 提供了硬约束时
- 格式要求（按模板输出）——LLM 对结构化输出遵从度较好
- 短指令（"不要使用破折号"）

**遵从度较低的场景**：
- context window 后半段的指令（规则多到 Agent "记不住"）
- 负面指令的长期维持（"不要使用比喻"写着写着就忘了）
- 多步骤流程中的文件维护（"每次规划后更新 tracker"容易被跳过）
- 创造力与约束的平衡（规则太多时 LLM 倾向于忽略部分规则以保持输出流畅）

**项目中的缓解策略**：
1. 关键约束用技术手段强制（`disallowed_tools`、`max_turns`、timeout）
2. 非关键约束分层加载（不把所有规则一次塞进 prompt）
3. 多 Agent 互相校验（writer 可能违反规则 → reviewer 检测到 → polisher 修复）
4. Pipeline 多步骤本身就是一种"重试"——一个 Agent 没做好的事由下一个 Agent 补

**本质问题**：LLM 不是确定性系统。同样的 prompt，不同次调用可能有不同的遵从度。这意味着 Pipeline 的输出质量有方差——有时很好，有时需要人工介入。这也是为什么项目定位是"辅助工具"而非"全自动系统"。

---

## 十六、关键技术指标

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
