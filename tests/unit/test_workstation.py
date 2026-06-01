"""Workstation hibernation tests."""

from datetime import UTC, datetime, timedelta

from thekedar_orchestrator.integrations.workstation import WorkstationManager
from thekedar_shared.db import WorkstationHealth
from thekedar_shared.settings import Settings


def test_hibernate_idle(session_factory, test_settings: Settings) -> None:
    session = session_factory()
    session.add(
        WorkstationHealth(
            tenant_id="default",
            name="ws-1",
            state="active",
            last_activity_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    session.commit()
    session.close()

    manager = WorkstationManager(test_settings, session_factory)
    count = manager.hibernate_idle()
    assert count == 1

    session = session_factory()
    ws = session.query(WorkstationHealth).filter_by(tenant_id="default").first()
    assert ws is not None
    assert ws.state == "sleeping"
    session.close()
