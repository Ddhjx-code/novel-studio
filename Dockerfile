# Stage 1: Build frontend
FROM node:20-alpine AS frontend
ARG NPM_REGISTRY=https://registry.npmjs.org
WORKDIR /app/frontend
COPY frontend/package*.json frontend/.npmrc ./
RUN npm ci --silent --registry ${NPM_REGISTRY}
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + static assets
FROM python:3.11-slim
ARG PIP_INDEX=https://pypi.org/simple/
WORKDIR /app

COPY pyproject.toml ./
COPY backend/ backend/
RUN pip install --no-cache-dir -i ${PIP_INDEX} .

COPY --from=frontend /app/frontend/dist frontend/dist
COPY .env.example .env.example

EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
