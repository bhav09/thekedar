"""CLI entrypoint for webhook-ingress service."""

import uvicorn


def run() -> None:
    uvicorn.run(
        "thekedar_webhook_ingress.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )


if __name__ == "__main__":
    run()
