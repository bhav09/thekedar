FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml ./
COPY packages/shared/pyproject.toml packages/shared/
COPY packages/message-adapter/pyproject.toml packages/message-adapter/
COPY packages/webhook-ingress/pyproject.toml packages/webhook-ingress/
COPY packages/shared/src packages/shared/src
COPY packages/message-adapter/src packages/message-adapter/src
COPY packages/webhook-ingress/src packages/webhook-ingress/src

RUN pip install --no-cache-dir ./packages/shared ./packages/message-adapter ./packages/webhook-ingress

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER appuser

ENV THEKEDAR_ENVIRONMENT=prod
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"

CMD ["uvicorn", "thekedar_webhook_ingress.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
