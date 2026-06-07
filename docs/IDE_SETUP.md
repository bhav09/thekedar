# IDE Setup

Thekedar routes coding work through pluggable IDE adapters on GCP Cloud Workstations or your local machine.

## Pluggable IDE Adapters

| IDE | Env value | CLI checked by `thekedar doctor` | Description |
|-----|-----------|----------------------------------|-------------|
| Mock (demo/tests) | `mock` | always available in demo mode | Simulates edits and test passes; disabled in production |
| Claude Code | `claude` | `claude` | Anthropic's headless terminal agent |
| Cursor | `cursor` | `cursor` or `cursor-agent` | Cursor IDE's command-line automation agent |
| VS Code | `vscode` | `code` or `code-server` | Bidirectional task queue or Code-OSS CLI execution |
| Antigravity | `antigravity` | `agy` or `antigravity` | Python-first local/remote AI agent |
| Auto | `auto` | prefers Claude, falls back to mock | Smart selection based on CLI availability |

Set in your `.env` or system environment:

```bash
# General config
THEKEDAR_LOCAL_IDE=1
THEKEDAR_LOCAL_REPO_PATH=/path/to/your/repo
THEKEDAR_IDE_ADAPTER=auto
THEKEDAR_LLM_PROVIDER=mock   # use mock for local OSS; configure provider in prod
```

---

## Remote Executor Modes

Thekedar supports three execution modes for remote commands and IDE adapters, configured via `THEKEDAR_REMOTE_EXECUTOR`:

1. **`local` (Development / Local Emulation):** Commands run directly on the orchestrator's local filesystem in the resolved workspace folder.
2. **`gcp` (Production / Staging):** Commands execute securely inside Google Cloud Workstations via an SSH-over-IAP tunnel using `gcloud workstations ssh`.
3. **`fake` (Unit Testing):** Simulates remote workstation commands in-process for speed and deterministic testing.

---

## Bidirectional VS Code Extension

When using VS Code in a "laptop-off" or interactive cloud workflow, configure the task execution mode via `THEKEDAR_VSCODE_TASK_MODE`:

* **`extension` (Interactive / Queue Mode):** The orchestrator enqueues a coding task in the `ide_tasks` database table. The client-side VS Code extension (polling the API / listening to WebSockets) claims the task, runs the agent locally inside your active editor context, calculates metrics (files changed, commits), and reports success/failure back to the orchestrator.
* **`disabled` (Direct Headless / CLI Mode):** Commands execute directly on the headless workstation CLI via SSH.

### Extension Configuration

Install the `extensions/vscode-thekedar` extension package. In your user settings (`settings.json`), configure:

```json
{
  "thekedar.dashboardUrl": "https://dashboard.thekedar.dev",
  "thekedar.token": "your-jwt-authentication-token",
  "thekedar.taskRunnerEnabled": true
}
```

---

## Cloud Workstation Configuration (staging/prod)

1. Ensure `THEKEDAR_REMOTE_EXECUTOR=gcp` is set in the environment.
2. Set your Google Cloud project credentials and ID in `GCP_PROJECT_ID`.
3. The orchestrator boots, stops, and manages the workstation cluster/config programmatically using the `google-cloud-workstations` client.
4. Developers can discover their running workstation host and connect their VS Code or Cursor IDE using Remote-SSH or through the client-side dashboard hub.
