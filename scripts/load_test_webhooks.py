#!/usr/bin/env python3
"""Load test: concurrent webhook ACK latency (M6 gate — 100 concurrent)."""

from __future__ import annotations

import asyncio
import json
import time

import httpx


async def post_webhook(client: httpx.AsyncClient, url: str, idx: int) -> float:
    payload = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "user": "U_TEST",
            "text": f"load test {idx}",
            "channel": "C_TEST",
            "ts": f"{idx}.000",
            "team": "T001",
        },
    }
    start = time.perf_counter()
    response = await client.post(url, content=json.dumps(payload))
    elapsed = time.perf_counter() - start
    response.raise_for_status()
    return elapsed


async def main(base_url: str = "http://localhost:8080", concurrency: int = 100) -> None:
    url = f"{base_url.rstrip('/')}/webhooks/slack"
    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [post_webhook(client, url, i) for i in range(concurrency)]
        latencies = await asyncio.gather(*tasks)

    latencies.sort()
    p99 = latencies[int(len(latencies) * 0.99) - 1]
    print(f"Requests: {concurrency}")
    print(f"p50: {latencies[len(latencies)//2]*1000:.1f}ms")
    print(f"p99: {p99*1000:.1f}ms")
    print(f"max: {max(latencies)*1000:.1f}ms")


if __name__ == "__main__":
    asyncio.run(main())
