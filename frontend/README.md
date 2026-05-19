# Novel Studio Frontend

React 19 + TypeScript + Vite + Ant Design 6 single-page application.

## Pages

| Page | Route | Description |
|------|-------|-------------|
| Projects | `/` | Project list and creation |
| Workbench | `/workbench/:project` | Staged generation controls and task history |
| Chapters | `/chapters/:project` | Monaco editor with plan/review side panel |
| Bible | `/bible/:project` | Settings collection (characters, worldbuilding, plot) |
| Prompt Studio | `/prompts` | Agent and skill prompt editor |
| Settings | `/settings` | LLM provider configuration |

## Development

```bash
npm install
npm run dev
# http://localhost:5173 (proxies /api to backend at :8080)
```

## Build

```bash
npm run build
# Output: dist/ (served by backend in production)
```

## Key Components

- **ChatPanel** — Drawer-based agent discussion (useChat hook + WebSocket)
- **ReviewPanel** — Tabs for plan/review/actions in chapter editor
- **ChapterList** — Shows both written and plan-only chapters
- **MarkdownViewer** — react-markdown renderer with loading states
- **TaskHistory** — Pipeline task list with status badges

## Hooks

- `useChat` — Session lifecycle, message streaming, cursor-based event processing
- `usePipeline` — Pipeline trigger with loading state tracking
- `useWebSocket` — Reconnecting WebSocket with event buffering
