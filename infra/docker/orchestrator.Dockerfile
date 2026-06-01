FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml ./
COPY packages/shared/pyproject.toml packages/shared/
COPY packages/message-adapter/pyproject.toml packages/message-adapter/
COPY packages/mcp-policy/pyproject.toml packages/mcp-policy/
COPY packages/context/pyproject.toml packages/context/
COPY packages/execution/pyproject.toml packages/execution/
COPY packages/ide-adapters/pyproject.toml packages/ide-adapters/
COPY packages/resilience/pyproject.toml packages/resilience/
COPY packages/orchestrator/pyproject.toml packages/orchestrator/

COPY packages/shared/src packages/shared/src
COPY packages/message-adapter/src packages/message-adapter/src
COPY packages/mcp-policy/src packages/mcp-policy/src
COPY packages/context/src packages/context/src
COPY packages/execution/src packages/execution/src
COPY packages/ide-adapters/src packages/ide-adapters/src
COPY packages/resilience/src packages/resilience/src
COPY packages/orchestrator/src packages/orchestrator/src

RUN pip install --no-cache-dir \
    ./packages/shared \
    ./packages/message-adapter \
    ./packages/mcp-policy \
    ./packages/context \
    ./packages/execution \
    ./packages/ide-adapters \
    ./packages/resilience \
    ./packages/orchestrator

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER appuser

ENV THEKEDAR_ENVIRONMENT=prod

CMD ["thekedar-orchestrator"]
