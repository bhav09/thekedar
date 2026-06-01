"""Shared integration and configuration errors."""


class IntegrationError(Exception):
    """Required external integration unavailable or misconfigured."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"{provider}: {message}")


class ConfigurationError(Exception):
    """Invalid or unsafe configuration for the current environment."""
