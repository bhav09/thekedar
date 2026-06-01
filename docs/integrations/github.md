# GitHub integration

## 1. Personal access token

Create a fine-grained or classic PAT with:

- Contents: read/write
- Pull requests: read/write

```bash
GITHUB_TOKEN=ghp_...
```

## 2. Repository mapping

In `config/workspace.yaml`:

```yaml
github_org: myorg
github_repos:
  - myrepo
```

The `@Coder` agent creates branches like `thekedar/THE-42-slug` and opens PRs against `main`.

## 3. Webhooks (optional — CI status on dashboard)

1. Repo → Settings → Webhooks → Add webhook
2. URL: `https://YOUR-TUNNEL/webhooks/github`
3. Secret: set `GITHUB_WEBHOOK_SECRET` in `.env`
4. Events: Pull requests, Check runs

## 4. Verify

```bash
uv run thekedar doctor
uv run thekedar mcp ping github
```

Send: `@Coder fix THE-42 login bug`

## Demo mode

Without `GITHUB_TOKEN`, PR URLs are simulated when demo mode is on.
