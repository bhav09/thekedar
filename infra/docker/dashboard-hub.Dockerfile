FROM python:3.12-slim AS builder

WORKDIR /app

COPY pyproject.toml ./
COPY packages/shared/pyproject.toml packages/shared/
COPY packages/dashboard-hub/pyproject.toml packages/dashboard-hub/
COPY packages/shared/src packages/shared/src
COPY packages/dashboard-hub/src packages/dashboard-hub/src

RUN pip install --no-cache-dir ./packages/shared ./packages/dashboard-hub

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER appuser

ENV THEKEDAR_ENVIRONMENT=prod
ENV PORT=8081

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8081/api/v1/widgets/workstation-health')"

CMD ["uvicorn", "thekedar_dashboard_hub.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8081"]
