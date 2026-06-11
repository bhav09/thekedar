# ADR-0004: Mid-Run Tool Approvals via Antigravity SDK Hooks

## Status

Accepted

## Context

Traditionally, agent systems rely on pre-run approval gates (e.g., approving an execution plan) or post-run verification (approving a publish/PR). Once an agent begins coding, it operates autonomously. This creates a severe blind spot: if the agent decides during coding to run a potentially risky terminal command (e.g., starting an external container, modifying a config file outside the repo, or installing global packages), there is no way to intercept it. 

We need a mechanism that allows the user to supervise critical or destructive actions *during* the execution phase, directly from their Slack or WhatsApp threads.

## Decision

We decide to utilize the Antigravity SDK's declarative policy engine and lifecycle hooks to enable interactive, mid-run tool approvals.

1. **Declarative Hook Policies:** We will configure the SDK agent with explicit policies in `LocalAgentConfig`:
   ```python
   policies = [
       deny("*"),
       allow("view_file"),
       allow("edit_file"),
       ask_user("run_command", handler=thekedar_approval_handler),
   ]
   ```
2. **Hook Bridge to the Queue:** The `thekedar_approval_handler` will:
   - Capture the requested command and context.
   - Pause the active agent thread on the workstation.
   - Insert an interactive `Approval` record with type `tool_review`.
   - Send an interactive Slack/WhatsApp approval card with "Approve" and "Deny" buttons.
3. **Resumption Protocol:** The agent session will block asynchronously until the user responds in Slack/WhatsApp. Clicking "Approve" updates the `Approval` status, signaling the orchestrator worker over the Redis/WebSocket queue to resume the agent. Clicking "Deny" aborts or injects an access-denied error into the agent's context to let it attempt an alternative.
4. **Time-Out Protection:** To prevent zombie workstation sessions, mid-run approvals have a strict timeout (e.g., 15 minutes). If the user does not respond, the run is terminated with an `expired` status and the workstation is safely hibernated.

## Consequences

- **Unprecedented Trust & Safety:** Developers can delegate massive tasks (e.g., broad refactoring) but stay comfortable knowing that any destructive terminal execution requires an explicit, single-tap confirmation on their phone.
- **Interactive Steerability:** Developers can use the "Deny" flow to inject feedback (e.g., "Do not run pip install; use uv add instead") mid-run, guiding the agent to compliance.
- **Workstation Utilization:** Workstations will remain running while waiting for user approvals. We mitigate this by establishing a short TTL (15 minutes) and sending immediate notification reminders.
