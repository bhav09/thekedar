"""IDE adapter protocol and factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_shared.settings import Settings
from thekedar_shared.exceptions import ConfigurationError


@dataclass
class CodingResult:
    success: bool
    summary: str
    files_changed: list[str] = field(default_factory=list)
    tests_added: int = 0
    tests_updated: int = 0
    commits_ahead: int = 0
    error: str | None = None


class IDEAdapter(Protocol):
    async def healthcheck(self) -> bool: ...

    async def run_task(
        self, plan: ExecutionPlan, context: GlobalContext, branch: str
    ) -> CodingResult: ...


def select_adapter(settings: Settings) -> IDEAdapter:
    from thekedar_ide_adapters.antigravity import AntigravityAdapter
    from thekedar_ide_adapters.claude import ClaudeCodeAdapter
    from thekedar_ide_adapters.cursor import CursorAdapter
    from thekedar_ide_adapters.mock import MockIDEAdapter
    from thekedar_ide_adapters.vscode import VSCodeAdapter
    from thekedar_ide_adapters.base import command_available

    name = settings.ide_adapter.lower()

    if name == "mock" or settings.llm_provider == "mock":
        if settings.environment in ("staging", "prod") and not settings.demo_mode:
            raise ConfigurationError("MockIDEAdapter is not allowed in staging/prod environments")
        return MockIDEAdapter(settings)

    mapping: dict[str, type] = {
        "cursor": CursorAdapter,
        "vscode": VSCodeAdapter,
        "claude": ClaudeCodeAdapter,
        "antigravity": AntigravityAdapter,
        "mock": MockIDEAdapter,
    }

    if name == "auto":
        if command_available("claude"):
            return ClaudeCodeAdapter(settings)
        elif command_available("cursor") or command_available("cursor-agent"):
            return CursorAdapter(settings)
        elif command_available("agy") or command_available("antigravity"):
            return AntigravityAdapter(settings)
        else:
            if settings.environment in ("staging", "prod") and not settings.demo_mode:
                raise ConfigurationError("No available IDE CLI found in 'auto' mode in staging/prod")
            logger_warning = True
            try:
                import logging
                logging.getLogger(__name__).warning("No active IDE adapter CLI found for 'auto', falling back to Mock")
            except Exception:
                pass
            return MockIDEAdapter(settings)

    cls = mapping.get(name, MockIDEAdapter)
    if cls == MockIDEAdapter and settings.environment in ("staging", "prod") and not settings.demo_mode:
        raise ConfigurationError(f"MockIDEAdapter/Unknown adapter '{name}' is not allowed in staging/prod environments")

    return cls(settings)
