"""Run checkpoint store — Redis cache with SQL ledger fallback."""

from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from thekedar_shared.run_ledger import RunLedger

RESUME_QUEUE_KEY = "thekedar:queue:resume"
CHECKPOINT_PREFIX = "thekedar:run:checkpoint"


class RunCheckpointStore:
    def __init__(
        self,
        redis: Redis,
        *,
        ttl_seconds: int = 259_200,
        session_factory=None,
    ) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._ledger = RunLedger(session_factory) if session_factory else None

    def _key(self, run_id: str) -> str:
        return f"{CHECKPOINT_PREFIX}:{run_id}"

    async def save(self, run_id: str, state: dict[str, Any]) -> None:
        await self._redis.set(
            self._key(run_id),
            json.dumps(state, default=str),
            ex=self._ttl,
        )

    async def load(self, run_id: str) -> dict[str, Any] | None:
        raw = await self._redis.get(self._key(run_id))
        if raw is not None:
            return json.loads(raw)
        if self._ledger is None:
            return None
        rebuilt = self._ledger.rebuild_checkpoint_state(run_id)
        if rebuilt.get("last_completed_step"):
            await self.save(run_id, rebuilt)
            return rebuilt
        return None

    async def delete(self, run_id: str) -> None:
        await self._redis.delete(self._key(run_id))

    async def publish_resume(self, payload: dict[str, Any]) -> None:
        await self._redis.lpush(RESUME_QUEUE_KEY, json.dumps(payload))

    async def consume_resume(self, timeout: int = 5) -> dict[str, Any] | None:
        result = await self._redis.brpop(RESUME_QUEUE_KEY, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        return json.loads(raw)
