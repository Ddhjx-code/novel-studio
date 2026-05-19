<p align="center">
  <h1 align="center">Novel Studio</h1>
  <p align="center">
    AI 小说创作辅助工具 — 浏览器即用，多 Agent 工作流 + RAG 一致性校验
  </p>
  <p align="center">
    简体中文 | <a href="./README.md">English</a>
  </p>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-%3E%3D3.10-blue?logo=python&logoColor=white" alt="Python"></a>
  <a href="https://nodejs.org/"><img src="https://img.shields.io/badge/node-%3E%3D20-green?logo=node.js&logoColor=white" alt="Node.js"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white" alt="FastAPI"></a>
  <a href="https://react.dev/"><img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white" alt="React"></a>
  <a href="https://github.com/Ddhjx-code/novel-studio/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow" alt="License"></a>
</p>

---

> 定位：辅助人类作者完成小说创作的工作台，**不是**全自动写作机器。
> 核心理念是「分阶段生成 + 随时讨论」，人类全程主导节奏与创意。

## 功能特性

- **大纲生成** — 输入故事梗概，自动生成结构化章节大纲
- **分阶段章节生成** — 拆分为规划阶段（A+B）和写作阶段（C+D+E+F），中间可暂停讨论
- **Agent 讨论** — 随时与规划师/审查员/写手对话，打磨方案和稿件
- **审查 & 润色** — 自动十维度评审并给出修改建议，或进行文风润色
- **章节编辑器** — Monaco 编辑器 + 右侧规划/审查面板；规划中章节以"规划中"标签展示
- **设定集管理** — 角色档案、世界观设定、剧情笔记，支持 RAG 向量检索保证前后一致
- **提示词工作室** — 在浏览器中直接编辑 Agent 系统提示词和 Skill 文件
- **任务历史** — 持久化任务追踪，支持失败重试
- **LLM 配置** — 在界面中配置 LLM 服务商和模型
- **WebSocket 实时推送** — 流水线进度通过 WebSocket 事件实时反馈

## 快速开始

### 方式 A：Docker（推荐）

```bash
cp .env.example .env.local
# 编辑 .env.local，填入你的 LLM API Key

docker compose up --build
# 浏览器打开 http://localhost:8080
```

国内服务器使用镜像加速：

```bash
docker build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  --build-arg PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/ \
  -t novel-studio:1.0 .
```

### 方式 B：一键脚本

```bash
./setup.sh
# 编辑 .env.local，填入你的 LLM API Key

.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
# 浏览器打开 http://localhost:8080
```

### 方式 C：手动安装

```bash
# 后端
python3 -m venv .venv
.venv/bin/pip install -e .

# 前端
cd frontend && npm install && npm run build && cd ..

# 配置
cp .env.example .env.local
# 编辑 .env.local

# 启动（单端口，生产模式）
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### 开发模式（双终端）

```bash
# 终端 A — 后端（自动重载）
.venv/bin/uvicorn backend.main:app --reload --port 8080

# 终端 B — 前端（Vite 开发服务器，支持 HMR）
cd frontend && npm run dev
# 浏览器打开 http://localhost:5173
```

## 工作流程

```
梗概 → 大纲 → [讨论] → 章节规划 → [讨论] → 写作 → 审查 → 润色 → 定稿
                 ↑                     ↑                  ↑
            讨论面板               讨论面板            讨论面板
```

每个步骤可独立触发。作者可随时暂停、与 Agent 讨论、手动编辑文件，再继续下一步。

## LLM 配置

编辑 `.env.local`，或在界面的**设置**页面中配置：

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_API_FORMAT` | `openai_compat` 或 `ollama` | `openai_compat` |
| `LLM_BASE_URL` | API 地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名称 | `gpt-4o` |
| `LLM_API_KEY` | API 密钥 | `sk-...` |

Embedding 配置为可选项，留空则自动复用 LLM 配置。

## 项目结构

```
novel-studio/
├── backend/
│   ├── main.py              # FastAPI 入口（API 子应用 + 静态文件托管）
│   ├── config.py            # 配置管理（读取 .env.local）
│   ├── api/                 # REST + WebSocket 接口
│   ├── agents/              # Agent 定义文件（.md）
│   ├── skills/              # Skill 定义文件
│   ├── orchestrator/        # 流水线逻辑（章节、大纲、审查）
│   ├── projects/            # 项目工作空间 + 持久化层
│   ├── runtime/             # Session + Agent 管理
│   ├── tools/               # 自定义流水线工具
│   └── vectorstore/         # Embedding + FAISS 向量检索
├── frontend/
│   ├── src/
│   │   ├── pages/           # 项目列表、工作台、章节、设定集、提示词工作室、设置
│   │   ├── components/      # ChatPanel、ReviewPanel、ChapterList、MarkdownViewer 等
│   │   ├── hooks/           # useChat、usePipeline、useWebSocket
│   │   └── api.ts           # 后端 API 客户端
│   └── vite.config.ts       # 开发代理配置
├── pyproject.toml           # Python 依赖声明
├── setup.sh                 # 一键安装脚本
├── Dockerfile               # 多阶段构建（支持 build-arg 镜像加速）
├── docker-compose.yml       # Docker Compose 配置
├── .dockerignore            # 排除 node_modules/dist 进入构建上下文
└── .env.example             # LLM 配置模板
```

## Nginx 部署

生产环境 nginx 反向代理参考配置：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ws {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 600s;
    }
}
```

## 运行测试

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest backend/tests/ -q
```

## 开源协议

[MIT](LICENSE)
