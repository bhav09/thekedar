# ADR-0006: Secure Tenant GitHub PAT Management via GCP Secret Manager

## Status

Accepted

## Context

To enable the three-layer repository understanding model, the Antigravity SDK agent and the GitHub MCP server must read private repositories, create pull requests, and manage issues. This requires high-privilege GitHub Personal Access Tokens (PATs) or Installation Access Tokens. 

If these tokens are hardcoded, written to configuration files in the workspace, or exposed in prompts/logs, they represent a critical security vulnerability and regulatory non-compliance (PCI-DSS, SOC2).

We need a secure, multi-tenant credential storage and injection mechanism.

## Decision

We decide to store all tenant GitHub PATs securely within GCP Secret Manager and inject them dynamically into execution environments at runtime, ensuring they are never exposed in prompts, logs, or codebase files.

1. **GCP Secret Manager Storage:** Each tenant’s GitHub credentials will be stored as a unique secret under the naming convention `github_token_{tenant_id}`.
2. **Dynamic Injected Environment:** When the `RemoteAdapterExecutor` prepares the execution environment on the workstation VM, it fetches the PAT from Secret Manager and sets it as an environment variable (e.g., `GITHUB_TOKEN` or `BIFROST_GITHUB_PAT`).
3. **No Prompt Leakage:** Prompt builders are strictly forbidden from reading or referencing the PAT. The agent never sees its own credential; it only interacts with the MCP server which uses the environment variable implicitly.
4. **Log Redaction:** All logger configurations inside `thekedar_shared/observability.py` are updated to automatically scan for and redact any bearer tokens or strings matching the GitHub PAT pattern (`ghp_[a-zA-Z0-9]{36}`) before writing to stdout or cloud logs.

## Consequences

- **SOC2 & PCI Compliance:** Eliminates the risk of credential leakage in repositories, audit logs, or shared database instances.
- **Robust Tenant Isolation:** Tenant A's agent cannot access Tenant B's repository because the workstation environment only receives the PAT scoped to Tenant A's Secret Manager entry.
- **Credential Rotation:** Workspaces can rotate their GitHub PATs seamlessly by updating the GCP Secret Manager secret without needing to redeploy or modify any running orchestrator code.
- **Read-Only Verification:** The `thekedar doctor` command is extended to perform a non-destructive verification check, ensuring that the active PAT is valid and restricted to repository-scoped permissions.
