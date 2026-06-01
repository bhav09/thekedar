"""Coder pipeline integration tests (mock IDE)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from thekedar_context.indexer import RepoIndexer
from thekedar_shared.db import AgentRun, PendingApproval
from thekedar_shared.schemas import Channel, MessageEvent


@pytest.fixture
def indexed_context(session_factory) -> None:
    session = session_factory()
    repo_path = Path(__file__).resolve().parents[2]
    RepoIndexer().index(session, "default", "thekedar/thekedar", repo_path)
    session.close()


@pytest.fixture
def coder_message() -> MessageEvent:
    return MessageEvent(
        channel=Channel.SLACK,
        message_id="m-coder",
        thread_id="C123",
        user_id="U123",
        tenant_id="T001",
        text="@Coder fix THE-42 login auth bug",
        mentioned_agents=["Coder"],
        idempotency_key="slack:coder-1",
    )


@pytest.mark.asyncio
async def test_coder_pipeline_pauses_at_impact(
    orchestrator_services, session_factory, indexed_context, coder_message
) -> None:
    run_id = str(uuid.uuid4())
    session = session_factory()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id="T001",
            channel="slack",
            user_id="U123",
            workflow="coder",
            status="running",
            trigger_text=coder_message.text,
        )
    )
    session.commit()
    session.close()

    result = await orchestrator_services.run_coder_pipeline(coder_message, run_id, None)
    assert result["status"] == "awaiting_approval"
    assert "Impact assessment" in result["reply"]

    session = session_factory()
    approval = (
        session.query(PendingApproval)
        .filter_by(run_id=run_id, approval_type="impact_review")
        .first()
    )
    assert approval is not None
    assert approval.stage == "impact"
    session.close()


@pytest.mark.asyncio
async def test_coder_pipeline_resume_after_impact(
    orchestrator_services, session_factory, indexed_context, coder_message
) -> None:
    run_id = str(uuid.uuid4())
    session = session_factory()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id="T001",
            channel="slack",
            user_id="U123",
            workflow="coder",
            status="running",
            trigger_text=coder_message.text,
            issue_key="THE-42",
        )
    )
    session.commit()
    session.close()

    await orchestrator_services.run_coder_pipeline(coder_message, run_id, None)
    session = session_factory()
    approval = (
        session.query(PendingApproval)
        .filter_by(run_id=run_id, approval_type="impact_review")
        .first()
    )
    assert approval is not None
    approval.status = "approved"
    session.commit()
    approval_id = approval.id
    session.close()

    result = await orchestrator_services.resume_coder_run(run_id, approval_id, "approved")
    assert result["status"] == "awaiting_approval"
    assert "Execution plan" in result["reply"]


@pytest.mark.asyncio
async def test_full_pipeline_to_publish_gate(
    orchestrator_services, session_factory, indexed_context, coder_message, tmp_path
) -> None:
    import os

    os.environ["THEKEDAR_LOCAL_REPO_PATH"] = str(tmp_path)
    from thekedar_shared.settings import get_settings

    get_settings.cache_clear()

    # Init temp git repo
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    session = session_factory()
    RepoIndexer().index(session, "default", "thekedar/thekedar", tmp_path)
    session.close()

    run_id = str(uuid.uuid4())
    session = session_factory()
    session.add(
        AgentRun(
            id=run_id,
            tenant_id="T001",
            channel="slack",
            user_id="U123",
            workflow="coder",
            status="running",
            trigger_text=coder_message.text,
            issue_key="THE-42",
        )
    )
    session.commit()
    session.close()

    async def approve_stage(approval_type: str) -> str:
        session = session_factory()
        row = (
            session.query(PendingApproval)
            .filter_by(run_id=run_id, approval_type=approval_type, status="pending")
            .first()
        )
        assert row is not None
        row.status = "approved"
        session.commit()
        aid = row.id
        session.close()
        return aid

    r1 = await orchestrator_services.run_coder_pipeline(coder_message, run_id, None)
    assert r1["status"] == "awaiting_approval"

    r2 = await orchestrator_services.resume_coder_run(
        run_id, await approve_stage("impact_review"), "approved"
    )
    assert "Execution plan" in r2["reply"]

    r3 = await orchestrator_services.resume_coder_run(
        run_id, await approve_stage("plan_review"), "approved"
    )
    assert r3["status"] in ("awaiting_approval", "failed", "completed")
    if r3["status"] == "awaiting_approval":
        assert "Completion report" in r3["reply"] or "Publish" in r3["reply"]

    get_settings.cache_clear()
