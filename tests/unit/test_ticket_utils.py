"""Ticket utilities."""

from thekedar_orchestrator.ticket_utils import branch_name, extract_issue_key, slug_from_text


def test_extract_issue_key() -> None:
    assert extract_issue_key("Fix THE-42 login") == "THE-42"
    assert extract_issue_key("no ticket here") is None


def test_branch_name() -> None:
    assert branch_name("THE-42", "fix-login").startswith("thekedar/THE-42-")


def test_slug_from_text() -> None:
    assert "fix" in slug_from_text("@Coder fix THE-42 bug")
