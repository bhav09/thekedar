"""SQL-first run step ledger — source of truth for pipeline recovery."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from thekedar_shared.db import RunStep


class RunLedger:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def begin_step(
        self,
        run_id: str,
        tenant_id: str,
        step: str,
        *,
        approval_id: str | None = None,
        attempt: int = 1,
    ) -> str:
        session = self._session_factory()
        try:
            existing = (
                session.query(RunStep)
                .filter_by(run_id=run_id, step=step, approval_id=approval_id)
                .order_by(RunStep.attempt.desc())
                .first()
            )
            if existing and existing.status == "completed":
                return existing.id

            row = RunStep(
                run_id=run_id,
                tenant_id=tenant_id,
                step=step,
                status="running",
                attempt=attempt if existing is None else existing.attempt + 1,
                approval_id=approval_id,
            )
            session.add(row)
            session.commit()
            return row.id
        finally:
            session.close()

    def complete_step(
        self,
        step_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        session = self._session_factory()
        try:
            row = session.get(RunStep, step_id)
            if row is None:
                return
            row.status = "completed"
            if payload is not None:
                row.payload_json = json.dumps(payload, default=str)
            session.commit()
        finally:
            session.close()

    def fail_step(
        self,
        step_id: str,
        *,
        error_class: str,
        error_message: str,
        pending_retry: bool = False,
    ) -> None:
        session = self._session_factory()
        try:
            row = session.get(RunStep, step_id)
            if row is None:
                return
            row.status = "pending_retry" if pending_retry else "failed"
            row.error_class = error_class
            row.error_message = error_message[:4000]
            session.commit()
        finally:
            session.close()

    def latest_completed_payload(self, run_id: str, step: str) -> dict[str, Any] | None:
        session = self._session_factory()
        try:
            row = (
                session.query(RunStep)
                .filter_by(run_id=run_id, step=step, status="completed")
                .order_by(RunStep.updated_at.desc())
                .first()
            )
            if row is None or not row.payload_json:
                return None
            return json.loads(row.payload_json)
        finally:
            session.close()

    def rebuild_checkpoint_state(self, run_id: str) -> dict[str, Any]:
        session = self._session_factory()
        try:
            rows = (
                session.query(RunStep)
                .filter_by(run_id=run_id, status="completed")
                .order_by(RunStep.updated_at.asc())
                .all()
            )
            state: dict[str, Any] = {"run_id": run_id}
            for row in rows:
                if row.payload_json:
                    chunk = json.loads(row.payload_json)
                    if isinstance(chunk, dict):
                        state.update(chunk)
                state["last_completed_step"] = row.step
            return state
        finally:
            session.close()
