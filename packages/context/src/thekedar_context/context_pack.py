"""Context pack builder for LLMs and IDE adapters."""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from thekedar_context.schemas import GlobalContext


class ContextPackBuilder:
    """Builds bounded context packs for inclusion in prompts."""

    @staticmethod
    def build_context_pack(
        context: GlobalContext, keywords: list[str], max_tokens: int = 8000
    ) -> dict[str, Any]:
        manifest_excerpt = list(context.manifest.items())[:10] if context.manifest else []
        top_symbols = [
            sym for sym in context.symbol_index if any(k in sym.lower() for k in keywords)
        ][:15]
        security_profile = context.security_profile
        test_map = [
            chunk
            for chunk in context.doc_chunks
            if "test" in chunk.get("path", "").lower()
        ][:5]

        pack = {
            "manifest_excerpt": manifest_excerpt,
            "top_symbols": top_symbols,
            "security_profile": security_profile,
            "test_map": test_map,
        }

        # Token-budgeted retrieval constraint checking (1 token ~= 4 chars)
        max_chars = max_tokens * 4
        serialized = json.dumps(pack)
        
        if len(serialized) > max_chars:
            # Iteratively shrink arrays to fit budget
            while len(serialized) > max_chars and (top_symbols or test_map):
                if top_symbols:
                    top_symbols.pop()
                elif test_map:
                    test_map.pop()
                pack["top_symbols"] = top_symbols
                pack["test_map"] = test_map
                serialized = json.dumps(pack)

        return pack
