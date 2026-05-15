#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Creating Python virtual environment..."
python3 -m venv .venv

echo "==> Installing backend dependencies..."
.venv/bin/pip install -e . --quiet

echo "==> Installing frontend dependencies..."
cd frontend && npm install --silent && cd ..

echo "==> Building frontend..."
cd frontend && npm run build && cd ..

if [ ! -f .env.local ]; then
    echo "==> Creating .env.local from template..."
    cp .env.example .env.local
    echo "    Please edit .env.local and fill in your LLM API Key."
else
    echo "==> .env.local already exists, skipping."
fi

echo ""
echo "Setup complete!"
echo ""
echo "  1. Edit .env.local to configure your LLM API key"
echo "  2. Start the server:"
echo "       .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080"
echo "  3. Open http://localhost:8080 in your browser"
