# M7 Coding Pipeline

Thekedar M7 replaces the simulated `@Coder` path with a multi-stage, approval-gated pipeline that uses global codebase context, impact analysis, IDE-backed execution, tests, and user-directed publish actions.

## Flow

1. **Load context** — index or refresh repo snapshot (`ContextSnapshot` + `ContextChunk`)
2. **Impact assessment** — hybrid static + policy analysis; `impact_review` approval
3. **Execution plan** — files, tests, branch; `plan_review` approval (up to 3 amendment rounds)
4. **Coding** — Cloud Workstation (prod) or local IDE fallback via `IDEAdapter`
5. **Tests** — real pytest/npm when `THEKEDAR_LOCAL_REPO_PATH` is set
6. **Completion report** — summary + dashboard link; `publish_review` approval
7. **Publish** — push branch and/or create PR per user instruction

## Approvals

| Stage | Type | Resume trigger |
|-------|------|----------------|
| Impact | `impact_review` | Slack button, dashboard API, Redis resume queue |
| Plan | `plan_review` | Same |
| Publish | `publish_review` | Same + optional `user_message` (`create pr`, `push branch`) |

## Commands

```bash
uv run thekedar context index --repo org/repo --path .
uv run thekedar context status --repo org/repo
uv run thekedar doctor   # includes IDE adapter check
```

## Environment

See `.env.example` for `THEKEDAR_LOCAL_IDE`, `THEKEDAR_LOCAL_REPO_PATH`, `THEKEDAR_IDE_ADAPTER`, `THEKEDAR_LLM_PROVIDER`.

## Invariants

- No raw diffs in Slack/WhatsApp (summaries + dashboard links)
- Publish blocked unless commits > 0 and tests pass
- Tenant-scoped context and approvals
- Bounded coding iterations (`THEKEDAR_MAX_CODING_ITERATIONS`)
