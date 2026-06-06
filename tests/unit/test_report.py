"""Report generator tests."""

from __future__ import annotations

from thekedar_context.schemas import ExecutionPlan, ImpactReport
from thekedar_ide_adapters import CodingResult
from thekedar_orchestrator.report import ReportGenerator


def test_completion_report() -> None:
    plan = ExecutionPlan(summary="Fix login", branch_name="the-42-login", test_strategy="pytest")
    impact = ImpactReport(request_summary="THE-42 login", security_risks=["auth change"])
    coding = CodingResult(
        success=True,
        summary="done",
        files_changed=["packages/auth.py"],
        tests_added=2,
        commits_ahead=2,
    )
    report = ReportGenerator().generate(plan, impact, coding, "passed", "48 passed", cost_usd=0.3)
    assert report.commits_ahead == 2
    assert report.tests_added == 2
    text = report.to_chat_summary("http://localhost:8081", "run-9")
    assert "Completion report" in text
