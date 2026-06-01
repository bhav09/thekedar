"""Workspace service tests."""

from thekedar_shared.db import Workspace
from thekedar_shared.schemas import Channel, MessageEvent
from thekedar_shared.workspace import WorkspaceService


def test_resolve_slack_team(session_factory) -> None:
    session = session_factory()
    session.add(
        Workspace(
            tenant_id="default",
            name="Test",
            slack_team_id="T999",
        )
    )
    session.commit()
    session.close()

    service = WorkspaceService(session_factory)
    msg = MessageEvent(
        channel=Channel.SLACK,
        message_id="1",
        thread_id="C1",
        user_id="U1",
        tenant_id="T999",
        text="hi",
        idempotency_key="k1",
    )
    ws = service.resolve(msg)
    assert ws is not None
    assert ws.tenant_id == "default"
