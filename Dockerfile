# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.8.15-python3.12-bookworm-slim AS uv
FROM python:3.12-slim-bookworm

COPY --from=uv /usr/local/bin/uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 appuser
USER appuser

ENV HOST=0.0.0.0 \
    PORT=8080 \
    MCP_RESOURCE_URL=http://127.0.0.1:8080/mcp

EXPOSE 8080

CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn trpg_mcp.main:app --host \"${HOST}\" --port \"${PORT}\""]
