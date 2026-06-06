"""Parse approval commands from chat text (Slack/WhatsApp fallback)."""

from __future__ import annotations

import re
from dataclasses import dataclass

UUID_RE = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)


@dataclass
class ApprovalCommand:
    decision: str  # approved | rejected
    approval_id: str | None = None
    user_message: str | None = None  # publish intent or plan amendment


def parse_approval_command(text: str) -> ApprovalCommand | None:
    lower = text.strip().lower()
    if not lower:
        return None

    # Skip new agent tasks
    if any(tag in lower for tag in ("@coder", "@architect", "@status")):
        return None

    approval_id = None
    uuid_match = UUID_RE.search(text)
    if uuid_match:
        approval_id = uuid_match.group(1)

    if lower.startswith("reject"):
        return ApprovalCommand(decision="rejected", approval_id=approval_id)

    if not lower.startswith("approve"):
        # Publish intents without explicit "approve" prefix
        for phrase in ("create pr", "push branch", "approve publish", "open pr", "open draft pr"):
            if phrase in lower:
                return ApprovalCommand(
                    decision="approved",
                    approval_id=approval_id,
                    user_message=text.strip(),
                )
        return None

    user_message = None
    if any(w in lower for w in ("publish", "create pr", "push branch", "open pr", "push to")):
        user_message = text.strip()
    elif len(text.strip()) > len("approve"):
        remainder = text.strip()[len("approve") :].strip()
        if remainder and not UUID_RE.fullmatch(remainder):
            user_message = remainder

    return ApprovalCommand(
        decision="approved",
        approval_id=approval_id,
        user_message=user_message,
    )
