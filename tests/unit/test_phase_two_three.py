"""Unit tests for Phase II and Phase III features (McpRegistry, SdkAdapter, ContextPackBuilder, Context MCP)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from thekedar_context.context_pack import ContextPackBuilder
from thekedar_context.indexer import RepoIndexer
from thekedar_context.retriever import ContextRetriever
from thekedar_context.schemas import GlobalContext, ContextQuery, ExecutionPlan
from thekedar_ide_adapters.antigravity_sdk import AntigravitySdkAdapter
from thekedar_shared.db import ContextSnapshot, ContextChunk
from thekedar_shared.mcp_registry import McpRegistry
from thekedar_shared.settings import Settings


def test_context_pack_budget() -> None:
    # 1. Ensure small budget truncates top_symbols and test_map iteratively
    ctx = GlobalContext(
        snapshot_id="snap-123",
        tenant_id="default",
        repo="my/repo",
        sha="abcdef",
        branch="main",
        manifest={"key": "val"},
        doc_chunks=[
            {"path": "tests/test_a.py", "excerpt": "aaa"},
            {"path": "tests/test_b.py", "excerpt": "bbb"},
            {"path": "tests/test_c.py", "excerpt": "ccc"},
        ],
        symbol_index=["src/a.py:def foo()", "src/b.py:class Bar()", "src/c.py:def baz()"],
    )

    # With high token budget, everything fits
    pack_large = ContextPackBuilder.build_context_pack(ctx, ["foo", "test"], max_tokens=1000)
    assert len(pack_large["top_symbols"]) > 0
    assert len(pack_large["test_map"]) > 0

    # With tiny token budget, iterative truncation kicks in
    pack_small = ContextPackBuilder.build_context_pack(ctx, ["foo", "test"], max_tokens=20)
    assert len(pack_small["top_symbols"]) == 0 or len(pack_small["test_map"]) == 0


def test_indexer_improvements(session_factory, test_settings: Settings) -> None:
    session = session_factory()
    repo_path = Path(__file__).resolve().parents[2]
    
    # Run the indexer with JS/TS and service_graph support
    indexer = RepoIndexer()
    snapshot = indexer.index(session, "tenant-test", "thekedar/thekedar", repo_path)
    assert snapshot.id is not None

    # Retrieve and check chunks
    retriever = ContextRetriever(test_settings)
    ctx = retriever.load_global_context(session, "tenant-test", "thekedar/thekedar")
    assert ctx is not None
    assert "service_graph" in ctx.model_fields_set or ctx.service_graph is not None
    assert isinstance(ctx.service_graph.get("services"), list)

    # Verify query works on service_graph
    query = ContextQuery(tenant_id="tenant-test", repo="thekedar/thekedar", keywords=["thekedar"], chunk_types=["service_graph"])
    hits = retriever.query(session, query)
    # The list may or may not be empty depending on services list, but it should query successfully
    assert isinstance(hits, list)
    session.close()


def test_mcp_registry_tenant_token(test_settings: Settings) -> None:
    registry = McpRegistry(test_settings)

    # Test environment variable fallback
    with patch.dict("os.environ", {"GITHUB_TOKEN_MY_TENANT": "env-token-123"}):
        token = registry.get_tenant_github_token("my-tenant")
        assert token == "env-token-123"

    # Test GCP Secret Manager fallback under staging/prod
    test_settings.environment = "staging"
    test_settings.gcp_project_id = "gcp-proj"
    
    import sys
    mock_secret_client = MagicMock()
    mock_payload = MagicMock()
    mock_payload.data = b"gcp-token-456"
    mock_secret_client.access_secret_version.return_value = MagicMock(payload=mock_payload)

    # Inject mock module into sys.modules so that imports in McpRegistry pass cleanly
    mock_sm = MagicMock()
    mock_sm.SecretManagerServiceClient.return_value = mock_secret_client
    sys.modules["google.cloud.secretmanager"] = mock_sm
    try:
        token = registry.get_tenant_github_token("my-tenant")
        assert token == "gcp-token-456"
    finally:
        sys.modules.pop("google.cloud.secretmanager", None)


@pytest.mark.asyncio
async def test_antigravity_sdk_adapter_fallback(test_settings: Settings) -> None:
    # Test fallback to mock when SDK is not available
    adapter = AntigravitySdkAdapter(test_settings)
    
    # We enforce SDK_AVAILABLE = False via patch/mock if we want to test mock fallback path
    with patch("thekedar_ide_adapters.antigravity_sdk.SDK_AVAILABLE", False):
        plan = ExecutionPlan(summary="Fix code", files_to_touch=["main.py"])
        ctx = GlobalContext(snapshot_id="s1", tenant_id="t1", repo="r1", sha="sha", branch="main")
        res = await adapter.run_task(plan, ctx, "feat-x")
        assert res.success is True
        assert "Mock coding completed" in res.summary


def test_context_mcp_stdio_server(session_factory, test_settings: Settings) -> None:
    # Setup test index first
    session = session_factory()
    repo_path = Path(__file__).resolve().parents[2]
    RepoIndexer().index(session, "default", "thekedar/thekedar", repo_path)
    session.close()

    # Import MCP handlers
    from thekedar_context.context_mcp import handle_initialize, handle_tools_list, handle_tools_call

    # 1. Initialize
    init_res = handle_initialize(1)
    assert init_res["id"] == 1
    assert init_res["result"]["serverInfo"]["name"] == "thekedar-context-mcp"

    # 2. List tools
    tools_res = handle_tools_list(2)
    assert tools_res["id"] == 2
    assert any(t["name"] == "search_context" for t in tools_res["result"]["tools"])

    # 3. Call tool
    with patch("thekedar_context.context_mcp.get_settings", return_value=test_settings), \
         patch("thekedar_context.context_mcp.init_db", return_value=session_factory):
        call_res = handle_tools_call(3, {
            "name": "search_context",
            "arguments": {
                "tenant_id": "default",
                "repo": "thekedar/thekedar",
                "keywords": ["orchestrator"]
            }
        })
        assert call_res["id"] == 3
        assert "content" in call_res["result"]
        content_text = call_res["result"]["content"][0]["text"]
        hits = json.loads(content_text)
        assert isinstance(hits, list)
