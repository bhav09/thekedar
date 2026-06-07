"""Run checkpoint store — Redis cache with SQL ledger fallback."""

from __future__ import annotations

import json
import hmac
import hashlib
from typing import Any

from redis.asyncio import Redis

from thekedar_shared.run_ledger import RunLedger
from thekedar_shared.settings import Settings, get_settings

RESUME_QUEUE_KEY = "thekedar:queue:resume"
CHECKPOINT_PREFIX = "thekedar:run:checkpoint"


def _sign_payload(payload: dict[str, Any], secret: str) -> str:
    # Canonicalize payload by sorting keys
    serialized = json.dumps(payload, sort_keys=True)
    return hmac.new(secret.encode(), serialized.encode(), hashlib.sha256).hexdigest()


class RunCheckpointStore:
    def __init__(
        self,
        redis: Redis,
        *,
        ttl_seconds: int = 259_200,
        session_factory=None,
        settings: Settings | None = None,
    ) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._ledger = RunLedger(session_factory) if session_factory else None
        self._settings = settings

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
        settings = self._settings or get_settings()
        secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else "default-secret"
        signature = _sign_payload(payload, secret)
        signed_payload = {
            "payload": payload,
            "signature": signature,
        }
        await self._redis.lpush(RESUME_QUEUE_KEY, json.dumps(signed_payload))

    async def consume_resume(self, timeout: int = 5) -> dict[str, Any] | None:
        result = await self._redis.brpop(RESUME_QUEUE_KEY, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "payload" in data and "signature" in data:
                settings = self._settings or get_settings()
                secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else "default-secret"
                expected_sig = _sign_payload(data["payload"], secret)
                if hmac.compare_digest(data["signature"], expected_sig):
                    return data["payload"]
                else:
                    import logging
                    logging.getLogger(__name__).warning("Rejected resume event: invalid signature")
                    return None
            import logging
            logging.getLogger(__name__).warning("Rejected resume event: missing signature or invalid format")
            return None
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Failed to parse or verify resume event: {exc}")
            return None
