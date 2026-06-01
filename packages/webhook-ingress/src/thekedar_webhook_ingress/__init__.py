"""Public webhook ingress — signature verify, enqueue, fast ACK (M2)."""

__all__ = ["create_app"]

from thekedar_webhook_ingress.app import create_app
