# Pin to digest in config/mcp-servers.yaml for production.
FROM ghcr.io/github/github-mcp-server:v1.1.2

# GitHub MCP defaults to stdio; use with Bifrost stdio_config in the same pod (K8s).
# For HTTP, prefer GitHub-hosted remote MCP: https://api.githubcopilot.com/mcp/
