FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY packages/shared/pyproject.toml packages/shared/
COPY packages/message-adapter/pyproject.toml packages/message-adapter/
COPY packages/mcp-policy/pyproject.toml packages/mcp-policy/
COPY packages/orchestrator/pyproject.toml packages/orchestrator/
COPY packages/shared/src packages/shared/src
COPY packages/message-adapter/src packages/message-adapter/src
COPY packages/mcp-policy/src packages/mcp-policy/src
COPY packages/orchestrator/src packages/orchestrator/src

RUN uv pip install --system --no-cache ./packages/shared ./packages/message-adapter ./packages/mcp-policy ./packages/orchestrator

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER appuser

ENV THEKEDAR_ENVIRONMENT=prod

CMD ["thekedar-orchestrator"]
