"""Impact analyzer tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from thekedar_context.indexer import RepoIndexer
from thekedar_context.retriever import ContextRetriever
from thekedar_context.schemas import GlobalContext, ImpactReport
from thekedar_orchestrator.impact import ImpactAnalyzer


@pytest.fixture
def global_context(session_factory, test_settings) -> GlobalContext:
    session = session_factory()
    repo_path = Path(__file__).resolve().parents[2]
    RepoIndexer().index(session, "default", "thekedar/thekedar", repo_path)
    retriever = ContextRetriever(test_settings)
    ctx = retriever.load_global_context(session, "default", "thekedar/thekedar")
    assert ctx is not None
    session.close()
    return ctx


def test_impact_auth_keywords(test_settings, global_context: GlobalContext) -> None:
    analyzer = ImpactAnalyzer(test_settings, ContextRetriever(test_settings))
    report = analyzer.assess("@Coder fix THE-42 login auth bug", global_context, "THE-42")
    assert isinstance(report, ImpactReport)
    assert report.security_risks
    assert report.confidence in ("high", "medium", "low")
    assert report.evidence


def test_impact_chat_summary(test_settings, global_context: GlobalContext) -> None:
    analyzer = ImpactAnalyzer(test_settings, ContextRetriever(test_settings))
    report = analyzer.assess("Update README", global_context)
    text = report.to_chat_summary("http://localhost:8081", "run-1")
    assert "Impact assessment" in text
    assert "run-1" in text
