# Thekedar — Enhanced Task Brief (ETB): Cloud Workstation & IDE Harness Integration

**Status:** Awaiting Approval  
**Operating mode:** `[Production]`  
**Deployment:** GCP cloud-first (staging → prod). Local docker-compose is dev emulation only.

---

## 1. Problem Statement

Today, the "laptop-closed" coding workflow is partially scaffolded but runs on the wrong machine or filesystem (the orchestrator pod rather than the cloud workstation). Specifically:
- **Cloud execution plane is simulated:** The staging/prod pipeline only updates database flags and returns static/simulated pass strings instead of running real tests and code edits on GCP Cloud Workstations.
- **IDE CLI execution runs locally on Orchestrator:** IDE adapters (`cursor.py`, `claude.py`, `antigravity.py`) execute local subprocesses on the orchestrator's local filesystem (`cwd()`), rendering them non-functional on cloud deployments.
- **Critical bugs in existing adapters:**
  - Claude and Antigravity adapters pass `cwd` as a CLI positional argument to the command rather than as a subprocess keyword argument (`cwd=`), running them in the wrong directory.
  - VS Code adapter returns a hardcoded fake success with zero commits, breaking the downstream pipeline when no commits are produced.
- **VS Code Extension is a stub:** Only a `README.md` exists for the extension; there is no real implementation for JWT auth, active run status, or task queue execution.
- **Context Harness Gaps:** The SHA freshness contract is a warning rather than an enforced gate in production, prompting potential staleness; prompt isolation is incomplete; and eval suites are thin.

---

## 2. Solution: The Complete Cloud Workstation & IDE-Agnostic Harness

We will implement a phased, secure, and fully verified integration of the cloud dev environment, supporting full "laptop-closed" execution on GCP Cloud Workstations alongside an IDE-agnostic headless/interactive remote coding workflow.

---

## 3. Invariants (Testable)

- **Tenant Isolation:** All remote directories and workspaces are strictly isolated by `tenant_id` (e.g., `{remote_root}/{tenant_id}/{repo_name}`).
- **Fail-Closed in Staging/Prod:** Staging/prod environments fail loudly if the remote executor fails to boot/sync, or if the mock adapter is requested.
- **No Mock IDE in Prod:** Staging/prod execution is blocked from using `MockIDEAdapter` (throws `ConfigurationError`).
- **Real Tests on Execution Plane:** All baseline and post-coding tests (e.g., pytest, npm test) run on the workstation VM via remote execution, not as mocked or hardcoded pass strings.
- **Structured Context in Prompts:** Context is delivered inside `<ground_truth_context>` XML-like tags to protect against prompt injection, utilizing indexed symbols, docs, and security profiles.

---

## 4. Rollback Plan

We implement strict feature flags in the environment:
- `THEKEDAR_REMOTE_EXECUTOR`: `local` (run on dev/orchestrator via local subprocess) or `gcp` (run on GCP workstation via SSH/IAP) or `fake` (unit tests).
- `THEKEDAR_VSCODE_TASK_MODE`: `extension` (poll/WS task queue) or `disabled` (fail-closed / direct CLI).

If any stage fails, setting these keys safely reverts back to local dev or disabled states without redeploying.

---

## 5. Phases of Work & Acceptance Criteria

### Phase A: Remote Execution Abstraction (testable without GCP)
- **Scope:** Define `RemoteExecutor` protocol; implement `LocalRemoteExecutor` (dev/local subproc), `InProcessFakeRemoteExecutor` (pytest recorder), and wire them into `cloud.py` and `workstation.py`. Extend DB schema for `WorkstationHealth` (host, instance_id, repo_path, boot_started_at, last_error).
- **Acceptance Criteria:** Unit tests in `test_remote_executor.py`, `test_execution_router.py`, and `test_cloud_executor.py` are fully green.

### Phase B: IDE Adapter Harness & Bug Fixes
- **Scope:** Correct Claude/Antigravity `cwd` bug; use shared `build_ide_prompt` with `<ground_truth_context>` tags; fail-closed staging/prod from using mock adapter; enforce `max_coding_iterations` and token/cost ceiling checks in worker and router; implement `post_run_metrics` (commits, files changed).
- **Acceptance Criteria:** `test_ide_adapters.py` and `test_phase_d.py` pass with zero failures.

### Phase C: GCP Workstation Client & Remote Executor
- **Scope:** Real GCP workstations start/stop/status via `google-cloud-workstations` client with polling and retry backoff. SSH/IAP-based remote command execution for repo cloning, pull, test, and adapter run on the remote VM.
- **Acceptance Criteria:** Provisioning client tests green, reachability checks in `thekedar doctor` verify connection, and manual E2E run on staging succeeds with laptop off.

### Phase D: Bidirectional VS Code Task Queue & Extension
- **Scope:** Full API for `ide_tasks` (create, pending, claim, complete, fail). WebSocket push notification on task creation. Build bidirectional task runner and sidebar panel extension in `extensions/vscode-thekedar`.
- **Acceptance Criteria:** DB task table updates correctly; VS Code extension successfully claims a task, runs the local agent, and completes it back to the backend.

### Phase E: Context Harness Completion (M9 Gaps)
- **Scope:** Block stale context coding in production unless overridden; workstation SHA retrieval over remote executor; post-sync indexing on remote VM path; `ContextQuery.chunk_types` filtering; evidence linkage on `ExecutionPlan`; GitHub push reindexing.
- **Acceptance Criteria:** Full context/retrieval evaluation suite passes with zero failures.

### Phase F: End-to-End Pipeline Wiring
- **Scope:** Tie `CoderPipeline._node_execute_coding` to remote workspace setup, remote index, and remote coding adapter execution. Pass `workspace.cloud_workstation_config_id` to cloud executor.
- **Acceptance Criteria:** E2E integration test suite completes successfully.

### Phase G: Documentation & GA Checklist
- **Scope:** Update `docs/IDE_SETUP.md`, `docs/CODING_PIPELINE.md`, `docs/CONTEXT_HARNESS.md`, `docs/GA_CHECKLIST.md`, and `README.md`.
- **Acceptance Criteria:** All docs match implemented production code; M5/M7/M9 items in GA checklist marked as completed.

### Phase H: Run-Until-Green Testing Loop
- **Scope:** Maintain continuous pytest verification after every phase, fixing bugs on occurrence, ensuring no regression.
- **Acceptance Criteria:** `uv run pytest tests/` completes with 100% green tests.

---

## 6. Reference

- Plan File: `.cursor/plans/cloud_ide_completion_71baacec.plan.md`
- Original blueprint: `.cursor/plans/thekedar_full_blueprint_92d125ae.plan.md`
