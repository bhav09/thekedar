# Thekedar Threat Model (STRIDE)

This document maps the security boundaries, potential threats, and corresponding mitigations for the Thekedar orchestrator.

## 1. Trust Boundaries

```
[Untrusted Zone: Slack, WhatsApp, GitHub Webhooks]
       |
       v (HMAC / Signature Verification, Rate Limiting, Idempotency)
[Semi-Trusted Zone: webhook-ingress, dashboard-hub]
       |
       v (JWT Authentication, Tenant Scoping, Signed Resume Events)
[Trusted Zone: orchestrator-worker, PostgreSQL, Redis]
       |
       v (MCP Policies, Sanitized IDE Arguments)
[Privileged Actions: GitHub Write, Cloud Workstations, Jira Write]
```

## 2. STRIDE Threat Mapping

### Spoofing
* **Threat:** Forged webhook events pretending to be Slack or GitHub.
* **Mitigation:** HMAC signature verification on all incoming webhook routes.

### Tampering
* **Threat:** Forged resume events bypassing human approval gates.
* **Mitigation:** HMAC signing of all resume events using a canonical sorted payload and the `THEKEDAR_JWT_SECRET`.

### Repudiation
* **Threat:** Unauthorized actions executed without audit trail.
* **Mitigation:** Comprehensive audit logging in PostgreSQL run ledger for all critical state changes and approvals.

### Information Disclosure
* **Threat:** Cross-tenant data leakage in webhooks or dashboard.
* **Mitigation:** Strict database and memory filtering by `tenant_id` on all read/write paths.

### Denial of Service
* **Threat:** Webhook replay or thundering herd.
* **Mitigation:** Atomic Redis-backed claim-before-publish idempotency mechanism.

### Elevation of Privilege
* **Threat:** Arbitrary tool execution by agent.
* **Mitigation:** Strict MCP policy engine allowlists and argument sanitization.
