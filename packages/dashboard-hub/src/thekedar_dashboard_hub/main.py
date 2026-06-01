"""CLI entrypoint."""

import uvicorn


def run() -> None:
    uvicorn.run(
        "thekedar_dashboard_hub.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8081,
        log_level="info",
    )


if __name__ == "__main__":
    run()
