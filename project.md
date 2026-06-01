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

---

# Enhanced Task Brief: Dashboard Beautification & Slack Threading

### User Goal
Beautify the dashboard using 21st.dev style components to support scalable, multi-team access and configure workspace GitHub project URL contexts, while enabling E2E Slack thread replies and Jira ticket creation.

### Mode
`[Production]` (Staff SDE).  
*Reason:* Thekedar is an enterprise headless orchestrator communicating with live Slack and Jira APIs, managing GCP workspaces, and requiring robust, resilient handling of webhooks, concurrency, secure token rotations, and multitenant isolation.

### Code Grounding
We have read and verified the following files:
- [packages/shared/src/thekedar_shared/db.py](file:///c:/Users/bhavi/Projects/thekedar/packages/shared/src/thekedar_shared/db.py)
- [packages/shared/src/thekedar_shared/workspace_config.py](file:///c:/Users/bhavi/Projects/thekedar/packages/shared/src/thekedar_shared/workspace_config.py)
- [config/workspace.yaml](file:///c:/Users/bhavi/Projects/thekedar/config/workspace.yaml)
- [packages/dashboard-hub/src/thekedar_dashboard_hub/routes/widgets.py](file:///c:/Users/bhavi/Projects/thekedar/packages/dashboard-hub/src/thekedar_dashboard_hub/routes/widgets.py)
- [packages/dashboard-hub/src/thekedar_dashboard_hub/static/index.html](file:///c:/Users/bhavi/Projects/thekedar/packages/dashboard-hub/src/thekedar_dashboard_hub/static/index.html)
- [packages/orchestrator/src/thekedar_orchestrator/replies.py](file:///c:/Users/bhavi/Projects/thekedar/packages/orchestrator/src/thekedar_orchestrator/replies.py)
- [packages/orchestrator/src/thekedar_orchestrator/outbox.py](file:///c:/Users/bhavi/Projects/thekedar/packages/orchestrator/src/thekedar_orchestrator/outbox.py)
- [packages/orchestrator/src/thekedar_orchestrator/services.py](file:///c:/Users/bhavi/Projects/thekedar/packages/orchestrator/src/thekedar_orchestrator/services.py)

### Dependency Check
- No new libraries needed. The UI is built using vanilla CSS with modern layout features (CSS grid/flexbox, custom SVGs for charts/visualizations) to keep bundle size small and load speeds ultra-fast. Database integrations use existing SQLAlchemy structures.

### The "Safety Audit"
- **Race Conditions:** Ensure database updates to workspace settings (like updating the GitHub Project URL) are wrapped in atomic transactions and committed safely. When handling Slack webhook callbacks, the `idempotency_key` mechanism (claiming keys in Redis) must be atomic to prevent processing the same Slack message twice if delivered concurrently.
- **PII Leaks:** Mask credentials in logs. Ensure the new GitHub URL settings do not write credentials to any standard console logs.
- **N+1 Query Problems:** Limit relationship queries to tenant contexts and optimize workspace retrievals.

### Step-by-Step Plan
1. **Schema/Types:**
   - Add `github_project_url` to `Workspace` database model.
   - Update config loaders/seeds to map URL settings to `github_org` and `github_repos`.
2. **Failing Test:**
   - Add an E2E test verifying that a Slack message triggers a Jira ticket creation and returns a threaded reply using the correct `thread_ts`.
3. **Logic:**
   - Modify Slack delivery services to support and propagate `thread_ts` through direct sends and the database-backed outbox mechanism.
   - Expand orchestrator's `@Architect` ticket parsing triggers.
   - Implement API routes in the dashboard-hub to list workspaces and update workspace settings.
4. **Telemetry/Logs:**
   - Log GitHub URL parsers and outbound Slack API threading parameters.
5. **Dashboard UI Refactoring:**
   - Completely rewrite the frontend layout to feature a premium dark glassmorphism design system.
   - Support dynamic workspace switching and filtering by actor.
   - Include a Settings card showing the **GitHub Project URL** configuration input.

## Work Log
- **2026-06-01**:
  - Isolated test environments by dynamic `.env` ignoring and environment cleanup.
  - Added `github_project_url` schema and dynamic parsing mapping.
  - Implemented workspace settings endpoints and list queries in widgets API.
  - Built a premium glassmorphic dashboard in `index.html` featuring workspace selectors, settings update panel, and SVG charts.
  - Propagated Slack thread IDs for direct and outbox messages.
  - Verified Slack-to-Jira ticket E2E creation successfully.
  - Successfully updated ngrok client to version 3.39.5, authenticated it using the user-provided auth token, and started a public HTTP tunnel at `https://cut-utensil-handlebar.ngrok-free.dev` forwarding to `localhost:8080`.


# Enhanced Task Brief: Repository Publishing and Env Documentation

### User Goal
Document environment variable sources in `.env.example`, ensure `.gitignore` is fully updated, verify no credentials or secrets are leaked, and create a public GitHub repository named `thekedar` to publish the workspace code.

### Mode
`[Production]` (Staff SDE).  
*Reason:* The codebase contains sensitive local configurations, database credentials, Slack app configurations, and Jira tokens that must never be public.

### Code Grounding
We have read and verified:
- [.env.example](file:///c:/Users/bhavi/Projects/thekedar/.env.example)
- [.gitignore](file:///c:/Users/bhavi/Projects/thekedar/.gitignore)

### Dependency Check
- No new libraries needed.

### The "Safety Audit"
- **PII / Secret Leaks:** Verify that `.env` files, `.cursor/plans/`, cached files, and personal credentials are fully ignored and not committed. Check untracked files for any temporary or sensitive scripts.

### Step-by-Step Plan
1. **Setup:** Update `.env.example` with documentation hyperlinks for setting up GitHub PAT, Slack Tokens, Jira tokens, GCP Projects, and Meta/WhatsApp tokens.
2. **Gitignore Audit:** Audit and edit `.gitignore` to ensure no sensitive telemetry or local keys leak.
3. **Audit Run:** Run a local git check of staged/untracked files.
4. **Publish Repo:** Create the remote GitHub repository `thekedar` under user `bhav09` using the `gh` CLI, keep it public, and push the code.


