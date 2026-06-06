"""Plan generator tests."""

from __future__ import annotations

from thekedar_context.schemas import ExecutionPlan, GlobalContext, ImpactReport
from thekedar_orchestrator.plan import PlanGenerator


def test_generate_plan() -> None:
    ctx = GlobalContext(
        snapshot_id="s1",
        tenant_id="default",
        repo="thekedar/thekedar",
        sha="abc",
        branch="main",
        symbol_index=["packages/orchestrator/src/foo.py:def bar"],
        test_map={"count": 48, "test_files": ["tests/unit/test_foo.py"]},
    )
    impact = ImpactReport(
        request_summary="THE-42: fix login",
        affected_modules=["packages/orchestrator"],
        confidence="medium",
    )
    plan = PlanGenerator().generate("@Coder fix THE-42 login", ctx, impact, "THE-42")
    assert isinstance(plan, ExecutionPlan)
    assert plan.branch_name.startswith("thekedar/THE-42")
    assert plan.files_to_touch


def test_plan_amendment() -> None:
    plan = ExecutionPlan(
        summary="Fix bug",
        files_to_touch=["a.py"],
        branch_name="the-42-fix",
        test_strategy="pytest",
    )
    gen = PlanGenerator()
    assert gen.is_amendment("also update docs/README.md")
    updated = gen.apply_amendment(plan, "also update docs/README.md")
    assert "docs/README.md" in updated.files_to_touch
