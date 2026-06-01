# Jira integration

## 1. Create an API token

1. [Atlassian account settings](https://id.atlassian.com/manage-profile/security/api-tokens) → Create API token
2. Note your Jira Cloud site URL (e.g. `https://your-org.atlassian.net`)

## 2. Environment variables

```bash
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=...
```

## 3. Project key

Set `jira_project_key` in `config/workspace.yaml` (e.g. `THE`).

## 4. Verify

```bash
uv run thekedar doctor
```

Send: `@Architect list open issues` or `@Architect create issue: My task`

## Demo mode

Without Jira credentials, `@Architect` returns mock issues when `THEKEDAR_DEMO_MODE=true`.
