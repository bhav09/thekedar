"""Ticket/branch naming utilities."""

from __future__ import annotations

import re

ISSUE_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def extract_issue_key(text: str) -> str | None:
    match = ISSUE_KEY_RE.search(text)
    return match.group(1) if match else None


def branch_name(issue_key: str, slug: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9-]", "-", slug.lower()).strip("-")[:40]
    return f"thekedar/{issue_key}-{safe or 'work'}"


def slug_from_text(text: str) -> str:
    words = re.sub(r"@[A-Za-z]+", "", text).split()
    return "-".join(words[:4]) if words else "task"
