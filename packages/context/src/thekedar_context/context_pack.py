"""Context pack builder for LLMs and IDE adapters."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from thekedar_context.schemas import GlobalContext


class ContextPackBuilder:
    """Builds bounded context packs for inclusion in prompts."""

    @staticmethod
    def build_context_pack(context: GlobalContext, keywords: list[str]) -> dict[str, Any]:
        manifest_excerpt = list(context.manifest.items())[:10] if context.manifest else []
        top_symbols = [
            sym for sym in context.symbol_index 
            if any(k in sym.lower() for k in keywords)
        ][:15]
        security_profile = context.security_profile
        test_map = [
            chunk for chunk in context.doc_chunks 
            if "test" in chunk.get("path", "").lower()
        ][:5]

        return {
            "manifest_excerpt": manifest_excerpt,
            "top_symbols": top_symbols,
            "security_profile": security_profile,
            "test_map": test_map,
        }
