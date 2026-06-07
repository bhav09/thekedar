"""Unit evaluation of adversarial injection and approval confusion suites."""

from __future__ import annotations

import json
from pathlib import Path

from thekedar_orchestrator.impact import sanitize_user_text
from thekedar_orchestrator.approval_commands import parse_approval_command


def test_impact_injection_adversarial_eval() -> None:
    golden_path = Path(__file__).resolve().parent / "impact_injection_adversarial.jsonl"
    with open(golden_path) as f:
        cases = json.load(f)

    for case in cases:
        query = case["query"]
        sanitized = sanitize_user_text(query)
        # Ensure that no user-query closing tag or ground-truth-context tags remain
        assert "</user_query>" not in sanitized
        assert "<ground_truth_context>" not in sanitized
        assert "</ground_truth_context>" not in sanitized


def test_approval_confusion_eval() -> None:
    golden_path = Path(__file__).resolve().parent / "approval_confusion.jsonl"
    with open(golden_path) as f:
        cases = json.load(f)

    for case in cases:
        text = case["text"]
        cmd = parse_approval_command(text)
        
        is_approval = case["is_approval"]
        is_rejection = case["is_rejection"]

        if not is_approval and not is_rejection:
            assert cmd is None or (cmd.decision not in ("approved", "rejected"))
        else:
            assert cmd is not None
            if is_approval:
                assert cmd.decision == "approved"
            if is_rejection:
                assert cmd.decision == "rejected"
