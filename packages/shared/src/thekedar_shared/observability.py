"""OpenTelemetry and structured logging helpers."""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from typing import Any

from thekedar_shared.settings import Settings

_request_context: ContextVar[dict[str, str]] = ContextVar("thekedar_log_context", default={})


def bind_log_context(**fields: str) -> None:
    current = dict(_request_context.get())
    current.update({k: v for k, v in fields.items() if v})
    _request_context.set(current)


def clear_log_context() -> None:
    _request_context.set({})


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            **_request_context.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_observability(settings: Settings, service_name: str) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    if settings.environment in ("staging", "prod"):
        handler = logging.StreamHandler()
        handler.setFormatter(StructuredFormatter())
        root.handlers = [handler]

    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        endpoint = settings.otel_exporter_endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        if endpoint:
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
    except ImportError:
        logging.getLogger(__name__).warning("OpenTelemetry packages not installed")


def get_tracer(name: str):
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return None
