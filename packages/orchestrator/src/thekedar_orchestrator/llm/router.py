"""LLM router — primary provider with fallback chain and circuit breaker."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from thekedar_resilience.circuit_breaker import CircuitOpenError
from thekedar_resilience.health_registry import ProviderHealthRegistry
from thekedar_shared.audit import log_cost
from thekedar_shared.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    provider: str
    content: str
    structured: dict[str, Any] | None = None
    tokens_estimated: int = 0


class LLMRouter:
    def __init__(
        self,
        settings: Settings,
        registry: ProviderHealthRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._registry = registry

    def _providers(self) -> list[str]:
        chain = [self._settings.llm_primary]
        if self._settings.llm_fallback:
            chain.extend(p.strip() for p in self._settings.llm_fallback.split(",") if p.strip())
        if self._settings.llm_provider != "mock" and self._settings.llm_provider not in chain:
            chain.insert(0, self._settings.llm_provider)
        return [p for p in chain if p and p != "mock"]

    async def complete(
        self,
        prompt: str,
        *,
        schema_hint: str | None = None,
        session=None,
        tenant_id: str = "default",
        run_id: str | None = None,
    ) -> LLMResponse | None:
        if self._settings.llm_provider == "mock" and self._settings.environment == "local":
            return None

        for provider in self._providers():
            try:
                if self._registry:
                    await self._registry.check(f"llm:{provider}")
                response = await self._call_provider(provider, prompt, schema_hint)
                if self._registry:
                    await self._registry.record_success(f"llm:{provider}")
                if session is not None:
                    log_cost(session, tenant_id, "llm", 0.05, run_id)
                return response
            except CircuitOpenError:
                logger.warning("LLM circuit open for %s", provider)
            except Exception:
                logger.exception("LLM provider %s failed", provider)
                if self._registry:
                    await self._registry.record_failure(f"llm:{provider}")
        return None

    async def _call_provider(
        self,
        provider: str,
        prompt: str,
        schema_hint: str | None,
    ) -> LLMResponse:
        if provider == "gemini":
            return await self._gemini(prompt, schema_hint)
        if provider == "openai":
            return await self._openai(prompt, schema_hint)
        if provider == "anthropic":
            return await self._anthropic(prompt, schema_hint)
        raise ValueError(f"Unknown LLM provider: {provider}")

    async def _gemini(self, prompt: str, schema_hint: str | None) -> LLMResponse:
        api_key = __import__("os").environ.get("GEMINI_API_KEY") or __import__("os").environ.get(
            "GOOGLE_API_KEY"
        )
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )
        body: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
        }
        if schema_hint:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, params={"key": api_key}, json=body)
            response.raise_for_status()
            data = response.json()
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        structured = None
        if schema_hint and text:
            try:
                structured = json.loads(text)
            except json.JSONDecodeError:
                pass
        return LLMResponse(provider="gemini", content=text, structured=structured, tokens_estimated=500)

    async def _openai(self, prompt: str, schema_hint: str | None) -> LLMResponse:
        api_key = __import__("os").environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        messages = [{"role": "user", "content": prompt}]
        body: dict[str, Any] = {"model": "gpt-4o-mini", "messages": messages}
        if schema_hint:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=body,
            )
            response.raise_for_status()
            data = response.json()
        text = data["choices"][0]["message"]["content"]
        structured = json.loads(text) if schema_hint and text else None
        return LLMResponse(provider="openai", content=text, structured=structured, tokens_estimated=500)

    async def _anthropic(self, prompt: str, schema_hint: str | None) -> LLMResponse:
        api_key = __import__("os").environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-3-5-haiku-latest",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
        text = data["content"][0]["text"]
        structured = json.loads(text) if schema_hint and text else None
        return LLMResponse(
            provider="anthropic", content=text, structured=structured, tokens_estimated=500
        )
