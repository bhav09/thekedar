"""Context service schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ContextChunkData(BaseModel):
    chunk_type: str
    content_hash: str
    payload: dict[str, Any] = Field(default_factory=dict)


class GlobalContext(BaseModel):
    snapshot_id: str
    tenant_id: str
    repo: str
    sha: str
    branch: str
    manifest: dict[str, Any] = Field(default_factory=dict)
    doc_chunks: list[dict[str, Any]] = Field(default_factory=list)
    symbol_index: list[str] = Field(default_factory=list)
    dependency_graph: dict[str, Any] = Field(default_factory=dict)
    test_map: dict[str, Any] = Field(default_factory=dict)
    security_profile: dict[str, Any] = Field(default_factory=dict)


class ContextQuery(BaseModel):
    tenant_id: str
    repo: str
    keywords: list[str] = Field(default_factory=list)
    chunk_types: list[str] = Field(default_factory=list)


Confidence = Literal["high", "medium", "low"]


class ImpactReport(BaseModel):
    request_summary: str
    affected_modules: list[str] = Field(default_factory=list)
    breaking_changes: list[str] = Field(default_factory=list)
    security_risks: list[str] = Field(default_factory=list)
    blindspots: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    existing_behavior_changes: list[str] = Field(default_factory=list)
    recommended_scope: str = "in-scope"
    confidence: Confidence = "medium"
    evidence: list[str] = Field(default_factory=list)

    def to_chat_summary(self, dashboard_url: str, run_id: str) -> str:
        lines = [
            f"*Impact assessment*\n{self.request_summary}",
            "",
            "*Affected modules*",
            "\n".join(f"• {m}" for m in self.affected_modules[:8]) or "• (none identified)",
        ]
        if self.breaking_changes:
            lines += ["", "*Possible breaking changes*"] + [
                f"• {x}" for x in self.breaking_changes[:5]
            ]
        if self.security_risks:
            lines += ["", "*Security notes*"] + [f"• {x}" for x in self.security_risks[:5]
            ]
        if self.tradeoffs:
            lines += ["", "*Tradeoffs*"] + [f"• {x}" for x in self.tradeoffs[:3]]
        lines += [
            "",
            f"Confidence: {self.confidence}",
            f"Full report: {dashboard_url}/#/runs/{run_id}/impact",
            "",
            "Reply Approve to proceed to planning, or Reject to cancel.",
        ]
        return "\n".join(lines)


class FileEvidence(BaseModel):
    filepath: str
    chunk_ids: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    summary: str
    files_to_touch: list[str] = Field(default_factory=list)
    test_strategy: str = ""
    branch_name: str = ""
    rollback_strategy: str = "Revert branch and close PR"
    estimated_minutes: int = 15
    estimated_cost_usd: float = 0.25
    evidence: list[FileEvidence] = Field(default_factory=list)

    def to_chat_summary(self, dashboard_url: str, run_id: str) -> str:
        files = "\n".join(f"• `{f}`" for f in self.files_to_touch[:10]) or "• TBD"
        return (
            f"*Execution plan*\n{self.summary}\n\n"
            f"*Files (estimate)*\n{files}\n\n"
            f"*Tests:* {self.test_strategy}\n"
            f"*Branch:* `{self.branch_name}`\n"
            f"*Est. time:* {self.estimated_minutes} min\n\n"
            f"Details: {dashboard_url}/#/runs/{run_id}/plan\n\n"
            "Approve to start coding, or Reject to cancel."
        )


class CompletionReport(BaseModel):
    summary: str
    modules_changed: list[str] = Field(default_factory=list)
    tests_added: int = 0
    tests_updated: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    security_notes: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    compare_url: str | None = None
    commits_ahead: int = 0

    def to_chat_summary(self, dashboard_url: str, run_id: str) -> str:
        return (
            f"*Completion report*\n{self.summary}\n\n"
            f"Modules: {', '.join(self.modules_changed[:6]) or 'n/a'}\n"
            f"Tests: +{self.tests_added} new, {self.tests_passed} passed, "
            f"{self.tests_failed} failed\n"
            f"Commits ahead: {self.commits_ahead}\n"
            + (f"Compare: {self.compare_url}\n" if self.compare_url else "")
            + f"\nFull report: {dashboard_url}/#/runs/{run_id}/report\n\n"
            "Reply with: `approve publish`, `create pr`, or `push branch`."
        )
