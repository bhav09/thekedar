"""Staging CI gate — chaos suite marker for weekly runs."""

import pytest

pytestmark = pytest.mark.chaos


def test_chaos_suite_registered() -> None:
    """Non-blocking chaos marker until staging infra wired."""
    assert True
