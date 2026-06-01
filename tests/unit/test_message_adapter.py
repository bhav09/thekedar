"""Message adapter unit tests."""

import hashlib
import hmac
import time

from thekedar_message_adapter.slack import parse_slack_event, verify_slack_signature
from thekedar_message_adapter.whatsapp import parse_whatsapp_payload, verify_whatsapp_signature


def test_slack_signature_valid() -> None:
    secret = "test-secret"
    body = b'{"type":"event_callback","event":{"type":"message","text":"hi"}}'
    ts = str(int(time.time()))
    base = f"v0:{ts}:{body.decode()}"
    digest = hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest()
    assert verify_slack_signature(secret, body, ts, f"v0={digest}")


def test_slack_signature_invalid() -> None:
    assert not verify_slack_signature("secret", b"{}", "1", "v0=bad")


def test_parse_slack_message_event() -> None:
    payload = {
        "team_id": "T001",
        "event": {
            "type": "message",
            "user": "U1",
            "text": "Hello @Coder fix bug",
            "channel": "C1",
            "ts": "123.456",
        },
    }
    events = parse_slack_event(payload)
    assert len(events) == 1
    assert events[0].tenant_id == "T001"
    assert events[0].mentioned_agents == ["Coder"]
    assert events[0].idempotency_key == "slack:T001:123.456"


def test_whatsapp_signature_valid() -> None:
    secret = "app-secret"
    body = b'{"object":"whatsapp_business_account"}'
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_whatsapp_signature(secret, body, f"sha256={digest}")


def test_parse_whatsapp_text_message() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PN123"},
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "15551234567",
                                    "type": "text",
                                    "text": {"body": "@Status show runs"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    events = parse_whatsapp_payload(payload)
    assert len(events) == 1
    assert events[0].tenant_id == "PN123"
    assert events[0].mentioned_agents == ["Status"]
