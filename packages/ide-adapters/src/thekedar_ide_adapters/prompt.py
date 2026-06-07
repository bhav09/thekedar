"""Shared IDE prompt building and adapter utilities."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from thekedar_context.schemas import ExecutionPlan, GlobalContext
from thekedar_context.context_pack import ContextPackBuilder
from thekedar_ide_adapters.base import commits_ahead, run_git
from thekedar_ide_adapters import CodingResult


def sanitize_plan_field(text: str) -> str:
    """Sanitize and quote command fields to prevent shell metacharacter injection."""
    return shlex.quote(text)


def _keywords_from_text(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z_]{3,}", text.lower())
    stop = {"the", "and", "for", "fix", "coder", "with", "from", "this", "that"}
    return [t for t in tokens if t not in stop][:12]


def build_ide_prompt(plan: ExecutionPlan, context: GlobalContext, branch: str) -> str:
    """Build a structured IDE context-aware prompt using shared ContextPackBuilder."""
    keywords = _keywords_from_text(plan.summary)
    context_pack = ContextPackBuilder.build_context_pack(context, keywords)

    sanitized_summary = sanitize_plan_field(plan.summary)
    sanitized_strategy = sanitize_plan_field(plan.test_strategy)
    sanitized_files = [sanitize_plan_field(f) for f in plan.files_to_touch[:10]]

    prompt = (
        f"Implement: {sanitized_summary}.\n"
        f"Touch files: {', '.join(sanitized_files)}.\n"
        f"Tests: {sanitized_strategy}.\n\n"
        f"<ground_truth_context>\n"
        f"{json.dumps(context_pack, indent=2)}\n"
        f"</ground_truth_context>"
    )
    return prompt


def post_run_metrics(repo: Path, branch: str, success: bool = True, summary: str = "") -> CodingResult:
    """Compute files changed and commits ahead relative to origin/main or main."""
    res = run_git(repo, "diff", "--name-only", "origin/main...HEAD")
    if res.returncode != 0:
        res = run_git(repo, "diff", "--name-only", "main...HEAD")

    files_changed = []
    if res.returncode == 0:
        files_changed = [line.strip() for line in res.stdout.splitlines() if line.strip()]

    ahead = commits_ahead(repo, branch)
    return CodingResult(
        success=success,
        summary=summary,
        files_changed=files_changed,
        commits_ahead=ahead,
    )
