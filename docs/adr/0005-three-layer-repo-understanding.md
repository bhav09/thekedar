# ADR-0005: Three-Layer Repository Understanding Model for AI Agents

## Status

Accepted

## Context

A frequent failure pattern of AI coding agents is "context overload" and "context rot". 
1. If an agent tries to understand a repository by reading every file over the GitHub API, it quickly consumes its context window, loses its place, and runs up massive token bills.
2. If we dump the entire codebase layout and all symbol definitions into the initial system prompt, we overwhelm the model’s focus and trigger hallucinations on stale definitions.
3. If the agent clones the repository locally without any search index, it must grep files sequentially, which is slow and inaccurate.

We need a layered, structured context delivery mechanism that acts as the "hands and eyes" of our Antigravity SDK agent, ensuring deep repository comprehension without token bankruptcy.

## Decision

We decide to implement a **three-layer repository understanding model** that separates indexing, metadata retrieval, and local editing into distinct boundaries.

```
┌────────────────────────────────────────────────────────┐
│  Layer 1: Thekedar Context Index (Primary Source)       │
│  - Chunked, SHA-gated, pre-computed symbol & doc tables │
│  - Exposed as dynamic retrieval tools to the SDK agent │
└──────────────────────────┬─────────────────────────────┘
                           │ Fallback / Supplement
┌──────────────────────────▼─────────────────────────────┐
│  Layer 2: GitHub MCP (Live Metadata & Single Files)     │
│  - Standard stdio/HTTP server plugged into the SDK     │
│  - Restricted to issues, PRs, and targeted file reads │
└──────────────────────────┬─────────────────────────────┘
                           │ Actual File Modification
┌──────────────────────────▼─────────────────────────────┐
│  Layer 3: Local Workspace Files (Execution Only)       │
│  - Epstein workstation clone synchronized via Git      │
│  - Local file editing and CLI test runs                │
└────────────────────────────────────────────────────────┘
```

1. **Layer 1: Thekedar Context Index (Primary):** The database remains the primary source of truth for the codebase’s architecture, symbols, files, and tests. We expose this index to the agent using a custom SDK retrieval tool: `search_codebase_context(query, chunk_types)`.
2. **Layer 2: GitHub MCP (Live Metadata):** The official GitHub MCP server is attached as a supplementary tool. It is used exclusively to fetch live issues, pull requests, and file metadata. We explicitly block (via policies) bulk tree reads or recursive file downloads over the GitHub API to prevent context overload.
3. **Layer 3: Local Workspace Files (Execution):** The agent interacts with the actual repository workspace on the workstation VM using native file tools. This workspace is synchronized via Git *before* the agent starts. The agent is blocked from initiating raw Git clones of arbitrary URLs.

## Consequences

- **Extreme Token Efficiency:** Instead of dumping thousands of lines into the prompt, the agent starts with a tight "seed pack" and queries the Context Index or GitHub MCP dynamically only when it needs details.
- **No Private Repo Auth Leaks:** The agent does not need to handle high-privilege credentials directly; authentication is managed securely at the MCP server layer using tenant-specific tokens.
- **Consistent Codebase Comprehension:** Because the Context Index matches the workstation Git HEAD, we maintain an unbroken freshness contract. If a mid-run push occurs, we trigger an incremental re-index and notify the agent session.
