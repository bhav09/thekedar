"""Approval command parser tests."""

from thekedar_orchestrator.approval_commands import parse_approval_command


def test_parse_approve() -> None:
    cmd = parse_approval_command("approve")
    assert cmd is not None
    assert cmd.decision == "approved"


def test_parse_reject_with_id() -> None:
    aid = "b04dc6c9-c995-4109-86b9-4b2cea3ea7a6"
    cmd = parse_approval_command(f"reject {aid}")
    assert cmd is not None
    assert cmd.decision == "rejected"
    assert cmd.approval_id == aid


def test_parse_create_pr_intent() -> None:
    cmd = parse_approval_command("create pr")
    assert cmd is not None
    assert cmd.decision == "approved"
    assert cmd.user_message == "create pr"


def test_skip_coder_messages() -> None:
    assert parse_approval_command("@Coder fix THE-42") is None
