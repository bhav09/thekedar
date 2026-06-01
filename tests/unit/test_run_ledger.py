"""Run ledger tests."""

from __future__ import annotations

from thekedar_shared.run_ledger import RunLedger


def test_run_ledger_step_lifecycle(session_factory) -> None:
    ledger = RunLedger(session_factory)
    step_id = ledger.begin_step("run-1", "tenant-a", "load_context")
    ledger.complete_step(step_id, {"context_snapshot_id": "snap-1"})

    payload = ledger.latest_completed_payload("run-1", "load_context")
    assert payload is not None
    assert payload["context_snapshot_id"] == "snap-1"


def test_run_ledger_rebuild_checkpoint(session_factory) -> None:
    ledger = RunLedger(session_factory)
    s1 = ledger.begin_step("run-2", "tenant-a", "load_context")
    ledger.complete_step(s1, {"global_context": {"repo": "org/repo"}})
    s2 = ledger.begin_step("run-2", "tenant-a", "assess_impact")
    ledger.complete_step(s2, {"impact_report": {"confidence": "medium"}})

    state = ledger.rebuild_checkpoint_state("run-2")
    assert state["last_completed_step"] == "assess_impact"
    assert state["global_context"]["repo"] == "org/repo"
    assert state["impact_report"]["confidence"] == "medium"


def test_run_ledger_fail_step(session_factory) -> None:
    ledger = RunLedger(session_factory)
    step_id = ledger.begin_step("run-3", "tenant-a", "publish")
    ledger.fail_step(step_id, error_class="transient", error_message="503", pending_retry=True)

    from thekedar_shared.db import RunStep

    session = session_factory()
    row = session.get(RunStep, step_id)
    assert row is not None
    assert row.status == "pending_retry"
    session.close()
