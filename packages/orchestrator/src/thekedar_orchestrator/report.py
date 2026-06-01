"""Completion report generator."""

from __future__ import annotations

from thekedar_context.schemas import CompletionReport, ExecutionPlan, ImpactReport
from thekedar_ide_adapters import CodingResult


class ReportGenerator:
    def generate(
        self,
        plan: ExecutionPlan,
        impact: ImpactReport,
        coding: CodingResult,
        test_status: str,
        test_summary: str,
        *,
        cost_usd: float = 0.0,
        compare_url: str | None = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
    ) -> CompletionReport:
        modules = list({f.split("/")[0] for f in coding.files_changed if f})[:8]
        security = list(impact.security_risks)
        if test_status != "passed":
            security.append("Tests did not pass — do not merge without review")

        residual = list(impact.blindspots)
        if coding.error:
            residual.append(coding.error[:200])

        summary = (
            f"Completed: {plan.summary}. "
            f"Coding: {'OK' if coding.success else 'FAILED'}. "
            f"Tests: {test_status}."
        )

        return CompletionReport(
            summary=summary,
            modules_changed=modules or impact.affected_modules[:6],
            tests_added=coding.tests_added,
            tests_updated=coding.tests_updated,
            tests_passed=tests_passed if tests_passed else (1 if test_status == "passed" else 0),
            tests_failed=tests_failed if tests_failed else (0 if test_status == "passed" else 1),
            security_notes=security,
            residual_risks=residual,
            cost_usd=cost_usd,
            compare_url=compare_url,
            commits_ahead=coding.commits_ahead,
        )
