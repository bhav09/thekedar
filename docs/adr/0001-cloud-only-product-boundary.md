# ADR-0001: Cloud-Only Product Boundary for Slack and WhatsApp Ingress

## Status

Accepted

## Context

Thekedar was originally conceived as a flexible agent orchestrator. However, this flexibility led to architectural drift and a lack of a clear product boundary. Contributors and users faced confusion regarding whether Thekedar is a local CLI tool, a desktop assistant, or a cloud service. Furthermore, local execution of IDE agents on the orchestrator pod or the developer's laptop breaks the primary user promise of a "laptop-closed" background developer contractor. 

To create a highly focused, maintainable, and high-leverage product, we must define an immutable boundary around what Thekedar is, how users interact with it, and where execution occurs.

## Decision

We decide to restrict the user-facing product boundary of Thekedar to a cloud-powered, headless chat-to-codebase integration. 

1. **Slack and WhatsApp are the Sole Ingress Channels:** The user-facing surface is strictly limited to chat interaction (messaging, stage-gate approvals, and command amendments). There is no standalone desktop app, no CLI command runner for end-users, and no general agent marketplace.
2. **Cloud-First/GCP-Only Remote Execution:** In staging and production environments, all codebase analysis, indexing, coding, and testing must execute within GCP Cloud Workstations. No code execution runs on the developer's laptop, and no code execution is performed on the local filesystem of the orchestrator worker.
3. **The `local` Executor is Dev-Only:** Running local execution or local adapters via `THEKEDAR_REMOTE_EXECUTOR=local` is strictly limited to local development and testing. Any deployment to staging or production is blocked at the build/deploy level if the executor is not configured to `gcp`.
4. **VS Code is a Supporting Adjunct:** The VS Code extension is demoted to an optional, secondary developer convenience adjunct rather than a primary product surface. GA completion does not depend on the VS Code extension.

## Consequences

- **Extreme Simplicity:** The orchestrator simplifies down to webhook parsing, task queue coordination, and state reporting. We do not have to maintain native desktop apps or complex client-side security profiles.
- **Improved Security and Isolation:** Executing entirely within sandboxed Cloud Workstations guarantees strong multi-tenant isolation and prevents malicious or accidental shell commands from damaging orchestrator infrastructure or developer machines.
- **Strict Configuration Enforcement:** We enforce a deployment-level validation gate requiring `THEKEDAR_REMOTE_EXECUTOR` to be set to `gcp` in staging/production, failing the pipeline otherwise.
- **Clearer UX:** The developer experiences the exact same outcome whether they are at their desk or on their phone: they chat with the repository in Slack/WhatsApp, and they get a PR link out.
