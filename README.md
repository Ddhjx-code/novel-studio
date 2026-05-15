<p align="center">
  <h1 align="center">Novel Studio</h1>
  <p align="center">
    AI-powered novel writing assistant — browser-based, multi-agent workflow + RAG consistency.
  </p>
  <p align="center">
    <a href="./README.zh-CN.md">简体中文</a> | English
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

> An author's workbench that **assists** with novel creation, **not** an auto-writer.
> The author controls pace and creativity throughout.

## Features

- **Outline Generation** — provide a synopsis, get a structured chapter outline
- **Chapter Generation** — 4-step pipeline (blueprint, draft, continuity check, finalize) powered by specialized agents
- **Review & Polish** — automated review with actionable feedback, or stylistic polish pass
- **Bible (Settings Collection)** — character profiles, worldbuilding, plot notes with RAG-powered consistency checking
- **Prompt Studio** — edit agent system prompts and skill files directly in the browser
- **Task History** — persistent task tracking with retry support
- **LLM Settings** — configure LLM provider and model from the UI

## Quick Start

### Option A: Docker (recommended)

```bash
cp .env.example .env.local
# Edit .env.local — fill in your LLM API key

docker compose up --build
# Open http://localhost:8080
```

### Option B: Setup Script

```bash
./setup.sh
# Edit .env.local — fill in your LLM API key

.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
# Open http://localhost:8080
```

### Option C: Manual

```bash
# Backend
python3 -m venv .venv
.venv/bin/pip install -e .

# Frontend
cd frontend && npm install && npm run build && cd ..

# Config
cp .env.example .env.local
# Edit .env.local

# Run (single port, production mode)
.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

### Development Mode

```bash
# Terminal A — backend (auto-reload)
.venv/bin/uvicorn backend.main:app --reload --port 8080

# Terminal B — frontend (Vite dev server with HMR)
cd frontend && npm run dev
# Open http://localhost:5173
```

## LLM Configuration

Edit `.env.local` or use the **Settings** page in the UI:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_FORMAT` | `openai_compat` or `ollama` | `openai_compat` |
| `LLM_BASE_URL` | API endpoint | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model name | `gpt-4o` |
| `LLM_API_KEY` | API key | `sk-...` |

Embedding config is optional — falls back to the LLM config if left empty.

## Project Structure

```
novel-studio/
├── backend/
│   ├── main.py              # FastAPI entry (API sub-app + static files)
│   ├── config.py             # Settings from .env.local
│   ├── api/                  # REST + WebSocket endpoints
│   ├── agents/               # Agent definition files (.md)
│   ├── skills/               # Skill definition files
│   ├── orchestrator/         # Pipeline logic (chapter, outline, review)
│   ├── projects/             # Workspace + persistence layer
│   ├── runtime/              # Session + agent management
│   ├── tools/                # Custom pipeline tools
│   └── vectorstore/          # Embedding + FAISS integration
├── frontend/
│   ├── src/
│   │   ├── pages/            # Workbench, Bible, PromptStudio, Settings
│   │   ├── components/       # Shared UI components
│   │   ├── hooks/            # WebSocket, custom hooks
│   │   └── api.ts            # Backend API client
│   └── vite.config.ts        # Dev proxy config
├── pyproject.toml            # Python dependencies
├── setup.sh                  # One-click setup script
├── Dockerfile                # Multi-stage build
├── docker-compose.yml        # Docker Compose config
└── .env.example              # LLM config template
```

## Running Tests

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest backend/tests/ -q
```

## License

[MIT](LICENSE)
