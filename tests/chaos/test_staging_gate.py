"""Staging CI gate — chaos suite marker for weekly runs."""

import pytest
from thekedar_resilience.circuit_breaker import CircuitBreaker

pytestmark = pytest.mark.chaos


def test_chaos_suite_registered() -> None:
    """Non-blocking chaos marker until staging infra wired."""
    assert True


def test_circuit_breaker_chaos_simulation() -> None:
    """Simulate a dependency failure and assert circuit breaker opens."""
    breaker = CircuitBreaker(name="test-chaos-breaker", failure_threshold=2, open_seconds=5)
    
    # Record failures to open the circuit
    breaker.record_failure()
    breaker.record_failure()
    
    with pytest.raises(Exception) as exc:
        breaker.check()
    assert "circuit open" in str(exc.value).lower()

