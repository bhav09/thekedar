"""Context retrieval golden evaluation suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from thekedar_context.indexer import RepoIndexer
from thekedar_context.retriever import ContextRetriever
from thekedar_context.schemas import ContextQuery


def test_context_retrieval_golden_eval(session_factory, test_settings) -> None:
    session = session_factory()
    repo_path = Path(__file__).resolve().parents[2]
    RepoIndexer().index(session, "default", "thekedar/thekedar", repo_path)
    retriever = ContextRetriever(test_settings)

    golden_path = Path(__file__).resolve().parent / "context_retrieval_golden.jsonl"
    with open(golden_path) as f:
        cases = json.load(f)

    for case in cases:
        query_text = case["query"]
        expected_files = case["expected_files"]

        hits = retriever.query(
            session,
            ContextQuery(tenant_id="default", repo="thekedar/thekedar", keywords=[query_text]),
        )

        # Check if at least one of the expected files is represented in the hits
        found = False
        for hit in hits:
            if hit.get("type") == "doc":
                path = hit.get("path", "")
                if any(expected in path for expected in expected_files):
                    found = True
                    break
            elif hit.get("type") == "symbol":
                ref = hit.get("ref", "")
                if any(expected in ref for expected in expected_files):
                    found = True
                    break

        assert found, f"Query '{query_text}' failed to retrieve any of {expected_files}"

    session.close()
