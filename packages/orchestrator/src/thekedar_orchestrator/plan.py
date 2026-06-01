"""Execution plan generator."""

from __future__ import annotations

import re

from thekedar_context.schemas import ExecutionPlan, GlobalContext, ImpactReport
from thekedar_orchestrator.ticket_utils import branch_name, extract_issue_key, slug_from_text
from thekedar_shared.exceptions import IntegrationError


def _guess_files(context: GlobalContext, impact: ImpactReport) -> list[str]:
    files: list[str] = []
    for mod in impact.affected_modules:
        if mod.startswith("doc:"):
            files.append(mod.replace("doc:", ""))
            continue
        for sym in context.symbol_index:
            if mod in sym.split(":")[0]:
                files.append(sym.split(":")[0])
    for ev in impact.evidence:
        if ":" in ev and not ev.startswith("doc:"):
            path = ev.split(":")[0]
            if path.endswith(".py"):
                files.append(path)
    return list(dict.fromkeys(files))[:12]


class PlanGenerator:
    def generate(
        self,
        request_text: str,
        context: GlobalContext,
        impact: ImpactReport,
        issue_key: str | None = None,
        *,
        require_files: bool = False,
    ) -> ExecutionPlan:
        key = issue_key or extract_issue_key(request_text) or "TASK"
        branch = branch_name(key, slug_from_text(request_text))
        files = _guess_files(context, impact)
        if not files:
            if require_files:
                raise IntegrationError(
                    "plan",
                    "No files identified from context — amend request or run context index",
                )
            files = []

        test_strategy = "Run pytest on tests/; add unit tests for changed modules"
        if isinstance(context.test_map, dict) and context.test_map.get("test_files"):
            test_strategy = (
                f"Extend existing suite ({context.test_map.get('count', 0)} files); "
                "add cases for new behavior"
            )

        summary = impact.request_summary
        if impact.security_risks:
            summary += " (includes security-sensitive changes)"

        return ExecutionPlan(
            summary=summary,
            files_to_touch=files,
            test_strategy=test_strategy,
            branch_name=branch,
            rollback_strategy=f"Delete branch `{branch}` and abandon PR",
            estimated_minutes=20 if len(files) > 5 else 10,
            estimated_cost_usd=0.35 if len(files) > 5 else 0.15,
        )

    def is_amendment(self, text: str) -> bool:
        lower = text.lower().strip()
        if lower.startswith("approve") or lower.startswith("reject"):
            return False
        return any(
            phrase in lower
            for phrase in ("also", "additionally", "update", "include", "don't forget", "and ")
        )

    def apply_amendment(self, plan: ExecutionPlan, amendment: str) -> ExecutionPlan:
        extra_files = re.findall(r"[\w./-]+\.(?:py|md|yaml|ts|tsx|js)", amendment)
        merged = list(dict.fromkeys([*plan.files_to_touch, *extra_files]))
        if not merged:
            raise IntegrationError(
                "plan",
                "Amendment did not identify any files — specify paths explicitly",
            )
        return plan.model_copy(
            update={
                "summary": f"{plan.summary} — amended: {amendment[:120]}",
                "files_to_touch": merged,
            }
        )
