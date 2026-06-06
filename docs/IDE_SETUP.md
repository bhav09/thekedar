# IDE Setup (M7)

Thekedar routes coding work through pluggable IDE adapters on Cloud Workstation or your local machine.

## Adapters

| IDE | Env value | CLI checked by `thekedar doctor` |
|-----|-----------|----------------------------------|
| Mock (demo/tests) | `mock` | always available in demo mode |
| Claude Code | `claude` | `claude` |
| Cursor | `cursor` | `cursor` or `cursor-agent` |
| VS Code | `vscode` | `code` or `code-server` |
| Antigravity | `antigravity` | `agy` or `antigravity` |
| Auto | `auto` | prefers Claude, falls back to mock |

Set in `.env`:

```bash
THEKEDAR_LOCAL_IDE=1
THEKEDAR_LOCAL_REPO_PATH=/path/to/your/repo
THEKEDAR_IDE_ADAPTER=auto
THEKEDAR_LLM_PROVIDER=mock   # use mock for local OSS; configure provider in prod
```

## Cloud Workstation (staging/prod)

1. Configure `GCP_PROJECT_ID` and `cloud_workstation_config_id` on the workspace
2. Orchestrator boots workstation via `WorkstationManager`
3. Shell/filesystem MCP runs on the workstation (not on orchestrator pod)
4. Attach Cursor or VS Code via Remote-SSH to the workstation hostname

## Local fallback (OSS)

1. Clone target repo and set `THEKEDAR_LOCAL_REPO_PATH`
2. Enable `THEKEDAR_LOCAL_IDE=1`
3. Run `thekedar context index --path $THEKEDAR_LOCAL_REPO_PATH`
4. Send `@Coder fix THE-42 ...` from Slack/WhatsApp demo scripts

If the IDE CLI is missing, adapters fall back to `MockIDEAdapter` (creates marker commit + stub test).

## VS Code extension

See [extensions/vscode-thekedar/README.md](../extensions/vscode-thekedar/README.md) for the dashboard webview stub (run status + approvals).
