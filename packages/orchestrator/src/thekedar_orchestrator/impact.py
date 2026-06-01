"""Hybrid impact analyzer — static retrieval + LLM synthesis."""

from __future__ import annotations

import re

from thekedar_context.schemas import ContextQuery, GlobalContext, ImpactReport
from thekedar_context.retriever import ContextRetriever
from thekedar_orchestrator.llm.router import LLMRouter
from thekedar_orchestrator.policy_gate import PolicyViolation, enforce_mcp_policy
from thekedar_shared.settings import Settings


def _keywords_from_text(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z_]{3,}", text.lower())
    stop = {"the", "and", "for", "fix", "coder", "with", "from", "this", "that"}
    return [t for t in tokens if t not in stop][:12]


def _static_hits(context: GlobalContext, keywords: list[str]) -> list[str]:
    hits: list[str] = []
    for sym in context.symbol_index:
        if any(k in sym.lower() for k in keywords):
            hits.append(sym)
    for doc in context.doc_chunks:
        path = doc.get("path", "")
        if any(k in path.lower() for k in keywords):
            hits.append(f"doc:{path}")
    auth_modules = context.security_profile.get("auth_modules", [])
    if isinstance(auth_modules, list):
        for mod in auth_modules:
            if any(k in mod.lower() for k in keywords):
                hits.append(f"security:{mod}")
    return hits[:20]


class ImpactAnalyzer:
    def __init__(
        self,
        settings: Settings,
        retriever: ContextRetriever,
        llm: LLMRouter | None = None,
    ) -> None:
        self._settings = settings
        self._retriever = retriever
        self._llm = llm or LLMRouter(settings)

    def assess(
        self,
        request_text: str,
        context: GlobalContext,
        issue_key: str | None = None,
    ) -> ImpactReport:
        return self._assess_static(request_text, context, issue_key)

    async def assess_async(
        self,
        request_text: str,
        context: GlobalContext,
        issue_key: str | None = None,
        *,
        session=None,
        run_id: str | None = None,
    ) -> ImpactReport:
        report = self._assess_static(request_text, context, issue_key)
        llm_result = await self._llm.complete(
            f"Summarize impact for: {request_text}\nContext repo: {context.repo}",
            schema_hint="impact",
            session=session,
            tenant_id=context.tenant_id,
            run_id=run_id,
        )
        if llm_result is None:
            if report.confidence == "low":
                report = report.model_copy(
                    update={
                        "blindspots": [
                            *report.blindspots,
                            "LLM unavailable — static analysis only; approval required",
                        ],
                        "confidence": "low",
                    }
                )
            return report

        if llm_result.structured:
            extra_modules = llm_result.structured.get("affected_modules") or []
            merged_modules = list(dict.fromkeys([*report.affected_modules, *extra_modules]))[:10]
            report = report.model_copy(
                update={
                    "affected_modules": merged_modules or report.affected_modules,
                    "request_summary": llm_result.structured.get("summary", report.request_summary)[
                        :200
                    ],
                }
            )
        return report

    def _assess_static(
        self,
        request_text: str,
        context: GlobalContext,
        issue_key: str | None = None,
    ) -> ImpactReport:
        keywords = _keywords_from_text(request_text)
        if issue_key:
            keywords.append(issue_key.lower())

        evidence = _static_hits(context, keywords)
        affected = list({e.split(":")[0] if ":" in e else e.split("/")[0] for e in evidence})[:10]

        breaking: list[str] = []
        security: list[str] = []
        blindspots: list[str] = []
        tradeoffs: list[str] = []
        behavior: list[str] = []

        lower = request_text.lower()
        if any(w in lower for w in ("auth", "login", "jwt", "token", "password")):
            security.append("Touches authentication — review session handling and secret storage")
            if "auth" not in affected:
                affected.append("auth")

        if any(w in lower for w in ("delete", "remove", "migrate", "schema")):
            breaking.append("May change persisted data or API contracts")
            tradeoffs.append("Data migration vs backward compatibility")

        if any(w in lower for w in ("webhook", "api", "endpoint", "route")):
            behavior.append("Public API surface may change — verify webhook signatures and rate limits")
            security.append("Review input validation and tenant scoping on new endpoints")

        test_count = context.test_map.get("count", 0) if isinstance(context.test_map, dict) else 0
        if test_count == 0:
            blindspots.append("No test files indexed — add tests before merge")
        elif not any("test" in e.lower() for e in evidence):
            blindspots.append("No tests mapped to affected modules — extend coverage")

        try:
            enforce_mcp_policy(self._settings, "github", "create_branch", {"repo": context.repo})
        except PolicyViolation as exc:
            security.append(f"Policy constraint: {exc}")

        confidence = "high" if len(evidence) >= 3 else "medium" if evidence else "low"

        if "deploy" in lower or "prod" in lower:
            tradeoffs.append("Production deploy increases blast radius — use staging first")

        summary = request_text.strip()[:200]
        if issue_key:
            summary = f"{issue_key}: {summary}"

        return ImpactReport(
            request_summary=summary,
            affected_modules=affected or ["core"],
            breaking_changes=breaking,
            security_risks=security,
            blindspots=blindspots,
            tradeoffs=tradeoffs or ["Standard implementation complexity"],
            existing_behavior_changes=behavior,
            recommended_scope="in-scope" if confidence != "low" else "needs-split",
            confidence=confidence,
            evidence=evidence[:15],
        )

    def query_context(self, session, tenant_id: str, repo: str, text: str) -> list[dict]:
        return self._retriever.query(
            session,
            ContextQuery(tenant_id=tenant_id, repo=repo, keywords=_keywords_from_text(text)),
        )
