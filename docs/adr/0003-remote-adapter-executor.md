# ADR-0003: Remote Adapter Executor Pattern for True Cloud Sandboxing

## Status

Accepted

## Context

The current `CloudWorkstationExecutor` implementation contains a major architectural flaw: it triggers a remote repository sync on the Cloud Workstation, but then attempts to run the selected IDE adapter locally on the orchestrator's filesystem. 

```python
# From packages/execution/src/thekedar_execution/cloud.py
sync_res = await self._remote.sync_repo(context.tenant_id, context.repo, branch)
adapter = select_adapter(self._settings)
return await adapter.run_task(plan, context, branch)  # Executed locally!
```

This causes two severe problems:
1. The orchestrator attempts to reference `/home/user/repos/{tenant_id}/{repo_slug}` as its current working directory (`cwd`), which does not exist on the orchestrator's local filesystem.
2. The IDE binaries/agents (Claude Code, Cursor Agent, Antigravity) are executed locally on the orchestrator pod rather than within the secure, sandboxed cloud workstation, completely defeating the "laptop-closed cloud contractor" promise.

## Decision

We decide to introduce the `RemoteAdapterExecutor` pattern to route all IDE adapter invocations to the remote execution plane when operating in cloud mode (`THEKEDAR_REMOTE_EXECUTOR=gcp`).

1. **Remote Execution Wrapper:** We will create a `RemoteAdapterExecutor` abstraction in `packages/execution`. This will act as the single boundary for executing IDE agents.
2. **In-VM Agent execution:** In GCP mode, instead of calling the adapter subprocess on the orchestrator, the `RemoteAdapterExecutor` will launch the agent command on the remote VM using the existing SSH-over-IAP tunnel (`gcloud workstations ssh`).
3. **VM Worker Option:** We can provision a thin python worker (`thekedar-ws-agent`) inside the Cloud Workstation home directory during bootstrap that acts as a local proxy, importing the adapters and running the SDK/CLI directly inside the workstation environment, communicating back via standard I/O or a lightweight secure port.
4. **Adapter Decoupling:** Headless adapters (Claude Code, Cursor Agent, Antigravity) will no longer assume they have direct access to a local file path. They will execute command composition locally but compile the execution arguments into remote command strings.

## Consequences

- **Secure Sandbox Enforcement:** All agent code writes, test runs, and shell executions occur strictly on the remote VM, completely isolating the orchestrator pod from potential malicious actions or resource exhaustion.
- **Path Synchronization:** Resolves the P0 path-mismatch bugs: the target working directory exists natively on the workstation filesystem during remote execution.
- **Slight Latency Overhead:** Executing commands over SSH-over-IAP introduces minor transport latency compared to local dev subprocesses. This is an acceptable trade-off for true production isolation.
- **Portability:** If we switch cloud providers (e.g., from GCP to AWS Cloud9 or GitHub Codespaces), we only need to rewrite the `RemoteExecutor` and `RemoteAdapterExecutor` SSH wrapper without changing any of the core IDE adapters.
