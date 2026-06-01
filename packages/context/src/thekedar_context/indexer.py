"""Repository indexer — builds global context snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from pathlib import Path

from sqlalchemy.orm import Session
from thekedar_shared.db import ContextChunk, ContextSnapshot

logger = logging.getLogger(__name__)

DOC_GLOBS = ("README.md", "project.md", "docs/**/*.md", "CONTRIBUTING.md", "SECURITY.md")
MANIFEST_FILES = ("pyproject.toml", "package.json", "requirements.txt", "uv.lock")
SECURITY_FILES = (".env.example", "SECURITY.md", "config/mcp-policy.yaml")
TEST_MARKERS = ("tests/", "pytest.ini", ".github/workflows/")


class RepoIndexer:
    def __init__(self, repo_path: Path | None = None) -> None:
        self._repo_path = repo_path

    def _resolve_path(self, repo_path: Path | None) -> Path:
        path = repo_path or self._repo_path
        if path is None:
            raise ValueError("repo_path required")
        return path.resolve()

    def _git_sha(self, repo_path: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "unknown"

    def _git_branch(self, repo_path: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() or "main"
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "main"

    def _list_files(self, repo_path: Path) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            return [line for line in result.stdout.splitlines() if line.strip()]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return [str(p.relative_to(repo_path)) for p in repo_path.rglob("*") if p.is_file()]

    def _read_text(self, repo_path: Path, rel: str, max_bytes: int = 32_000) -> str:
        path = repo_path / rel
        if not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8", errors="replace")[:max_bytes]
        except OSError:
            return ""

    def _hash_content(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def build_chunks(self, repo_path: Path | None = None) -> list[tuple[str, str, dict]]:
        root = self._resolve_path(repo_path)
        files = self._list_files(root)
        chunks: list[tuple[str, str, dict]] = []

        manifest: dict[str, str] = {}
        for name in MANIFEST_FILES:
            if (root / name).is_file():
                text = self._read_text(root, name)
                manifest[name] = text
        chunks.append(("repo_manifest", self._hash_content(json.dumps(manifest)), manifest))

        doc_chunks: list[dict] = []
        for rel in files:
            if rel.endswith(".md") or rel.startswith("docs/"):
                text = self._read_text(root, rel, max_bytes=8_000)
                if text:
                    doc_chunks.append({"path": rel, "excerpt": text[:2000]})
        chunks.append(("doc_chunks", self._hash_content(json.dumps(doc_chunks)), {"items": doc_chunks}))

        symbols: list[str] = []
        for rel in files:
            if rel.endswith(".py") and "test" not in rel:
                for line in self._read_text(root, rel, 4_000).splitlines():
                    stripped = line.strip()
                    if stripped.startswith(("def ", "class ", "async def ")):
                        symbols.append(f"{rel}:{stripped[:80]}")
        chunks.append(
            (
                "symbol_index",
                self._hash_content(json.dumps(symbols[:200])),
                {"symbols": symbols[:200]},
            )
        )

        deps: dict[str, str] = {}
        for name in MANIFEST_FILES:
            if name in manifest:
                deps[name] = manifest[name][:4000]
        chunks.append(("dependency_graph", self._hash_content(json.dumps(deps)), deps))

        test_files = [f for f in files if f.startswith("tests/") or "test_" in f]
        test_map = {
            "test_files": test_files[:100],
            "count": len(test_files),
            "ci_workflows": [f for f in files if f.startswith(".github/workflows/")],
        }
        chunks.append(("test_map", self._hash_content(json.dumps(test_map)), test_map))

        security: dict[str, str] = {}
        for name in SECURITY_FILES:
            if (root / name).is_file():
                security[name] = self._read_text(root, name, 4_000)
        auth_hits = [f for f in files if "auth" in f.lower()]
        security["auth_modules"] = auth_hits[:20]
        chunks.append(
            ("security_profile", self._hash_content(json.dumps(security)), security)
        )

        return chunks

    def index(
        self,
        session: Session,
        tenant_id: str,
        repo: str,
        repo_path: Path | None = None,
    ) -> ContextSnapshot:
        root = self._resolve_path(repo_path)
        sha = self._git_sha(root)
        branch = self._git_branch(root)

        session.query(ContextChunk).filter_by(tenant_id=tenant_id, repo=repo).delete()
        session.query(ContextSnapshot).filter_by(tenant_id=tenant_id, repo=repo).delete()

        snapshot = ContextSnapshot(
            tenant_id=tenant_id,
            repo=repo,
            sha=sha,
            branch=branch,
        )
        session.add(snapshot)
        session.flush()

        for chunk_type, content_hash, payload in self.build_chunks(root):
            session.add(
                ContextChunk(
                    snapshot_id=snapshot.id,
                    tenant_id=tenant_id,
                    repo=repo,
                    chunk_type=chunk_type,
                    content_hash=content_hash,
                    payload=json.dumps(payload),
                )
            )

        session.commit()
        session.refresh(snapshot)
        logger.info("Indexed context for %s@%s (%s)", repo, sha[:8], tenant_id)
        return snapshot
