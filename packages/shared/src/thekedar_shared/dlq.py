"""Dead letter queue helpers for Redis and SQL mirror."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from thekedar_shared.db import DlqMessage

logger = logging.getLogger(__name__)

DLQ_KEY = "thekedar:queue:dlq"


class DlqStore:
    def __init__(self, redis, session_factory) -> None:
        self._redis = redis
        self._session_factory = session_factory

    async def push(self, payload: dict, *, source: str = "inbound", error: str = "") -> None:
        raw = json.dumps(payload, default=str)
        await self._redis.lpush(DLQ_KEY, raw)
        session = self._session_factory()
        try:
            session.add(
                DlqMessage(
                    source=source,
                    payload_json=raw,
                    status="pending",
                    last_error=error[:2000] if error else None,
                )
            )
            session.commit()
        finally:
            session.close()

    async def depth(self) -> int:
        return int(await self._redis.llen(DLQ_KEY))

    async def replay_one(self, *, dry_run: bool = False) -> dict | None:
        result = await self._redis.brpop(DLQ_KEY, timeout=1)
        if result is None:
            return None
        _, raw = result
        envelope = json.loads(raw)
        payload = envelope.get("payload", envelope)
        if dry_run:
            await self._redis.lpush(DLQ_KEY, raw)
            return payload

        session = self._session_factory()
        try:
            row = (
                session.query(DlqMessage)
                .filter_by(payload_json=raw, status="pending")
                .order_by(DlqMessage.created_at.desc())
                .first()
            )
            if row is None:
                session.add(
                    DlqMessage(
                        source="inbound",
                        payload_json=raw,
                        status="replayed",
                        replayed_at=datetime.now(UTC),
                    )
                )
            elif row:
                row.status = "replayed"
                row.replayed_at = datetime.now(UTC)
            session.commit()
        finally:
            session.close()
        return payload

    async def replay_all(
        self,
        publish_fn,
        *,
        dry_run: bool = False,
        max_messages: int = 100,
    ) -> int:
        count = 0
        for _ in range(max_messages):
            payload = await self.replay_one(dry_run=dry_run)
            if payload is None:
                break
            count += 1
            if not dry_run:
                await publish_fn(payload)
        return count
