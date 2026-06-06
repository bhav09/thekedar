"""Operational commands — DLQ replay, etc."""

from __future__ import annotations

import asyncio
from typing import Annotated

import redis.asyncio as aioredis
import typer
from thekedar_shared.bus import RedisMessageBus, create_message_bus
from thekedar_shared.db import init_db
from thekedar_shared.dlq import DlqStore
from thekedar_shared.settings import get_settings

app = typer.Typer(name="ops", help="Thekedar operator tasks")


@app.command("replay-dlq")
def replay_dlq(
    dry_run: Annotated[bool, typer.Option(help="Inspect without republishing")] = False,
    max_messages: Annotated[int, typer.Option(help="Max messages to replay")] = 100,
) -> None:
    """Replay dead-letter queue messages back to the inbound bus."""
    settings = get_settings()
    session_factory = init_db(settings.database_url)

    async def _run() -> int:
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        bus = create_message_bus(settings, redis)
        dlq = DlqStore(redis, session_factory)

        async def publish_fn(envelope: dict) -> None:
            payload = envelope.get("payload", envelope)
            await bus.publish_inbound(payload)

        count = await dlq.replay_all(publish_fn, dry_run=dry_run, max_messages=max_messages)
        depth = await dlq.depth()
        typer.echo(f"Replayed {count} message(s); DLQ depth={depth}")
        return count

    count = asyncio.run(_run())
    if count == 0 and not dry_run:
        raise typer.Exit(code=0)
