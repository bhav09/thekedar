# Thekedar — Enhanced Task Brief (ETB)

**Status:** Approved — implementation started  
**Operating mode:** `[Production]`  
**Deployment:** GCP cloud-first (staging → prod). Local docker-compose is dev emulation only.

## Problem

Engineers need a headless agent that orchestrates WhatsApp, Slack, Jira, GitHub, and cloud dev environments while the laptop is offline. Today this requires juggling local IDEs, manual ticket updates, and no unified visibility.

## Solution

**Thekedar** — a deployed Headless MCP Orchestrator plus unified Dashboard that:

1. Receives WhatsApp/Slack webhooks on public HTTPS
2. ACKs fast, processes async via Pub/Sub
3. Routes to LangGraph agents via Bifrost MCP gateway
4. Runs code on Cloud Workstations
5. Replies with summaries + PR links (never raw diffs in chat)
6. Aggregates status in a multi-surface dashboard

## Invariants (testable)

- Webhook ACK p99 < 500ms (agent work is async)
- Idempotent webhook processing per `(channel, message_id)`
- `tenant_id` on every data access path
- Irreversible actions require human approval
- Agent runs bounded: max 25 iterations, 30min wall clock, cost ceiling
- Secrets only in GCP Secret Manager (never in repo/logs)
- MCP images pinned by digest

## Objective function (priority)

1. Correctness & safety  
2. Reliability (laptop closed)  
3. Security & audit  
4. Cost control  
5. Latency perception  
6. Feature velocity  

## Milestones

| ID | Scope | Gate |
|---|---|---|
| M0 | Scaffold, ETB, Terraform skeleton, CI, `/health` on Cloud Run staging | `staging-api.../health` → 200 |
| M1 | Bifrost + GitHub MCP on GKE | `mcp ping github` on staging |
| M2 | Webhooks, async pipeline, LangGraph, Dashboard D0 | Slack message → deployed reply |
| M3 | Jira Rovo MCP, multi-tenant workspaces | Jira query via WhatsApp sandbox |
| M4 | Branch/PR workflow, approvals, Dashboard D1 | E2E PR on staging |
| M5 | Cloud Workstations, hibernation, Dashboard D2 | Laptop-closed coding path |
| M6 | Load tests, DR, GA | Production checklist |

## Out of scope (MVP)

- OSS-primary deployment path (documented alternate only)
- Raw diffs in messaging channels
- Offline/local-only agent execution

## Reference

Full blueprint: `.cursor/plans/thekedar_full_blueprint_92d125ae.plan.md`
