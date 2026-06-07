"""Context retrieval for agent runs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session
from thekedar_shared.db import ContextChunk, ContextSnapshot
from thekedar_shared.settings import Settings

from thekedar_context.schemas import ContextQuery, GlobalContext


class ContextRetriever:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def latest_snapshot(self, session: Session, tenant_id: str, repo: str) -> ContextSnapshot | None:
        return (
            session.query(ContextSnapshot)
            .filter_by(tenant_id=tenant_id, repo=repo)
            .order_by(ContextSnapshot.indexed_at.desc())
            .first()
        )

    def needs_refresh(self, snapshot: ContextSnapshot | None) -> bool:
        if snapshot is None:
            return True
        age = datetime.now(UTC) - snapshot.indexed_at.replace(tzinfo=UTC)
        return age > timedelta(hours=self._settings.context_reindex_hours)

    def load_global_context(
        self, session: Session, tenant_id: str, repo: str, snapshot_id: str | None = None
    ) -> GlobalContext | None:
        if snapshot_id:
            snapshot = session.get(ContextSnapshot, snapshot_id)
        else:
            snapshot = self.latest_snapshot(session, tenant_id, repo)
        if snapshot is None:
            return None

        chunks = session.query(ContextChunk).filter_by(snapshot_id=snapshot.id).all()
        data: dict[str, dict | list] = {}
        for chunk in chunks:
            try:
                data[chunk.chunk_type] = json.loads(chunk.payload)
            except json.JSONDecodeError:
                data[chunk.chunk_type] = {}

        manifest = data.get("repo_manifest", {})
        doc_data = data.get("doc_chunks", {})
        symbol_data = data.get("symbol_index", {})
        return GlobalContext(
            snapshot_id=snapshot.id,
            tenant_id=tenant_id,
            repo=repo,
            sha=snapshot.sha,
            branch=snapshot.branch,
            manifest=manifest if isinstance(manifest, dict) else {},
            doc_chunks=doc_data.get("items", []) if isinstance(doc_data, dict) else [],
            symbol_index=symbol_data.get("symbols", []) if isinstance(symbol_data, dict) else [],
            dependency_graph=data.get("dependency_graph", {}) if isinstance(
                data.get("dependency_graph"), dict
            ) else {},
            test_map=data.get("test_map", {}) if isinstance(data.get("test_map"), dict) else {},
            security_profile=data.get("security_profile", {})
            if isinstance(data.get("security_profile"), dict)
            else {},
        )

    def query(self, session: Session, query: ContextQuery) -> list[dict]:
        ctx = self.load_global_context(session, query.tenant_id, query.repo)
        if ctx is None:
            return []

        hits: list[dict] = []
        keywords = [k.lower() for k in query.keywords]

        # Filter by chunk_types if provided
        check_doc = not query.chunk_types or "doc" in query.chunk_types
        check_symbol = not query.chunk_types or "symbol" in query.chunk_types
        check_security = not query.chunk_types or "security" in query.chunk_types

        if check_doc:
            for doc in ctx.doc_chunks:
                text = f"{doc.get('path', '')} {doc.get('excerpt', '')}".lower()
                if not keywords or any(k in text for k in keywords):
                    hits.append({"type": "doc", **doc})

        if check_symbol:
            for sym in ctx.symbol_index:
                if not keywords or any(k in sym.lower() for k in keywords):
                    hits.append({"type": "symbol", "ref": sym})

        if check_security:
            auth_modules = ctx.security_profile.get("auth_modules", [])
            if isinstance(auth_modules, list):
                for mod in auth_modules:
                    if not keywords or any(k in mod.lower() for k in keywords):
                        hits.append({"type": "security", "ref": mod})

        return hits[:50]
