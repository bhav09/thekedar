# Workspace configuration

Workspaces map messaging tenants (Slack team ID, WhatsApp phone number ID) to Jira/GitHub/workstation settings.

## YAML config

Copy [config/workspace.example.yaml](../config/workspace.example.yaml) to `config/workspace.yaml`:

```yaml
workspaces:
  - tenant_id: default
    name: Engineering
    jira_project_key: THE
    github_org: myorg
    github_repos:
      - myrepo
    slack_team_id: T01234567
    whatsapp_phone_number_id: null
    cloud_workstation_config_id: thekedar-ws-default
    budget_monthly_usd: 100.0
```

The orchestrator worker seeds workspaces from this file on startup when it exists.

## Resolution order

1. Slack: match `event.team_id` → `slack_team_id`
2. WhatsApp: match phone number ID → `whatsapp_phone_number_id`
3. Fallback: match `tenant_id` directly

Unknown tenants receive: "Unknown workspace. Contact admin…"

## Environment

`THEKEDAR_WORKSPACE_CONFIG_PATH` defaults to `config/workspace.yaml`.

Generate via:

```bash
uv run thekedar init
```
