# ADR-0002: Google Antigravity SDK as the Primary GCP-Native Agent Runtime

## Status

Accepted

## Context

Previously, the Antigravity adapter in Thekedar operated by starting a background terminal subprocess of the Antigravity CLI tool (`agy run --prompt ...`) and waiting for the execution to complete. While this was simple, it created a "black box" where the orchestrator had zero insight into the active steps, token counts, or tool calls of the agent. This led to:
- Poor observability on the dashboard and chat channels.
- Lack of mid-run safety policies (an agent could run a destructive terminal command without any way for the orchestrator to intercept or deny it).
- Subprocess overhead and parsing issues when tool outputs were malformed.

The release of the `google-antigravity` Python SDK provides programmatic control over the core agentic engine, including in-process tool registration, safety policies, and multi-turn conversation tracking.

## Decision

We decide to leverage the `google-antigravity` Python SDK as the primary, GCP-native agent runtime on Cloud Workstations, while keeping the Antigravity CLI as a fallback option.

1. **In-Process SDK Client:** We will implement an `AntigravitySdkAdapter` that imports `google.antigravity` and uses `Agent(LocalAgentConfig)` under an async context manager. This replaces the background subprocess execution.
2. **Graceful Auto-Fallback:** If `google-antigravity` cannot be imported (due to OS or platform-specific wheel limitations during local dev), the adapter will fall back to CLI-based subprocess execution or mock adapters depending on the environment configuration.
3. **Inspect Hook Integration:** We will write Inspect hooks to stream agent reasoning steps and token usage in real-time to the dashboard and Slack/WhatsApp channels, eliminating the "black-box" run anxiety.
4. **Bootstrapping Workstations:** The `infra/workstation/bootstrap.sh` script will be updated to pre-install `google-antigravity` via PyPI.

## Consequences

- **Deeper Observability:** The orchestrator can track tool calls, costs, and token limits progressively rather than post-mortem.
- **Enhanced Safety:** We can apply declarative policies (e.g., denying wildcards on commands or directories) directly inside the SDK config rather than relying on regex filters on the terminal command itself.
- **Improved Prompt Performance:** Exposing context as a dynamic retrieval tool within the SDK allows the agent to pull codebase data on demand, replacing large static XML context blocks in seed prompts.
- **Binary/Wheel Dependency:** The `google-antigravity` SDK requires platform-specific compiled Go binaries. We must ensure that target Cloud Workstations run compatible Linux architectures, and we must handle import errors gracefully on local developer machines.
