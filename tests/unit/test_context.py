"""Context indexer and retriever tests."""

from __future__ import annotations

from pathlib import Path

from thekedar_context.indexer import RepoIndexer
from thekedar_context.retriever import ContextRetriever
from thekedar_context.schemas import ContextQuery


def test_index_repo(session_factory, test_settings) -> None:
    session = session_factory()
    repo_path = Path(__file__).resolve().parents[2]
    snapshot = RepoIndexer().index(session, "default", "thekedar/thekedar", repo_path)
    assert snapshot.sha
    assert snapshot.id

    retriever = ContextRetriever(test_settings)
    ctx = retriever.load_global_context(session, "default", "thekedar/thekedar")
    assert ctx is not None
    assert ctx.manifest
    assert len(ctx.symbol_index) > 0
    session.close()


def test_context_query(session_factory, test_settings) -> None:
    session = session_factory()
    repo_path = Path(__file__).resolve().parents[2]
    RepoIndexer().index(session, "default", "thekedar/thekedar", repo_path)
    retriever = ContextRetriever(test_settings)
    hits = retriever.query(
        session,
        ContextQuery(tenant_id="default", repo="thekedar/thekedar", keywords=["orchestrator"]),
    )
    assert any("orchestrator" in str(h).lower() for h in hits)
    session.close()
