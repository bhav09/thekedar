"""In-memory circuit breaker (per process); registry syncs state to Redis."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


class CircuitOpenError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Circuit open: {name}")


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    open_seconds: float = 60.0
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if time.monotonic() - self._opened_at >= self.open_seconds:
            self._opened_at = None
            self._failures = 0
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()

    def check(self) -> None:
        if not self.allow():
            raise CircuitOpenError(self.name)

    @property
    def is_open(self) -> bool:
        return not self.allow()
