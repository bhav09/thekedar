"""IDE adapter protocol and factory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_shared.settings import Settings


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

    name = settings.ide_adapter.lower()
    if settings.demo_mode or settings.llm_provider == "mock":
        return MockIDEAdapter(settings)
    mapping: dict[str, type] = {
        "cursor": CursorAdapter,
        "vscode": VSCodeAdapter,
        "claude": ClaudeCodeAdapter,
        "antigravity": AntigravityAdapter,
        "mock": MockIDEAdapter,
    }
    if name == "auto":
        return ClaudeCodeAdapter(settings)
    cls = mapping.get(name, MockIDEAdapter)
    return cls(settings)
