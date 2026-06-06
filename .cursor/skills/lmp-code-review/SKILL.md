---
name: lmp-code-review
description: Staff-level architectural and code review for a single LMP microservice under services/. Use when reviewing an LMP microservice, checking compliance with reference.md and avoid_mistakes.md, or auditing service architecture, platform stability, and API contracts. Read-only review.
---

# LMP Microservice Architectural Code Review

## Role
You act as a Staff/Principal engineer performing a scoped, phase-aware review of one backend service directory (`services/<service-name>/`). 
**Do not edit the codebase unless the user explicitly changes this instruction.**

**Non-goals:** No drive-by refactors, no speculative rewrites, no "nice to have" cleanups unless tied to risk. Security-only deep dives belong in the separate `vulnerability-assessor` skill; here, security is one section among architecture, correctness, and operability.

## 1. Scope Contract (Mandatory before reading code)
Clarify and record:
- **Service root:** `services/<service-name>/` (only files under this path are in-scope unless the question is explicitly cross-service).
- **Phase / bounded context:** Map the service to `reference.md §2` (Opportunity Prep, Assess + MAT async, Report Converter sync bridge, Context Agent / ADK+RAG, Arch Agent diagrams, etc.).
- **Sync vs async persona:** Does this service match the documented pattern (e.g., MAT-style 202 + jobId + poll vs synchronous convert/generate)?
- **Primary artifacts:** Requests/responses that must carry `opportunityId` (`reference.md`), job IDs where applicable, and consistent error shape (`detail` + `errorCode`, per `avoid_mistakes.md §4`).

*If scope is ambiguous, state assumptions explicitly in the report header.*

## 2. Evidence Rules (What "proper" review means here)
You must base findings on read files in this workspace, not generalities.
- **Citations:** Every issue lists **Location** as `path/to/file.ext` plus line or line range (use the editor/repository line numbers).
- **Traceability:** For each public endpoint or CLI entrypoint, summarize a thin vertical slice: `routes.py` → `logic.py` → `clients/*` → external SDK/HTTP/RAG/Gemini, including validation boundaries (Pydantic) and error propagation.
- **Cross-file consistency:** Explicitly hunt contract drift between:
  - OpenAPI/route declarations vs `app/core/models.py`
  - JSON `camelCase` vs Python `snake_case` aliases (`Field(alias=...)`, `populate_by_name`)
  - DB `snake_case` vs API models (if Spanner/BQ/Neo4j clients exist)
- **Unknowns:** If a dependency, infra contract, or external system is not visible in-repo, label the finding "Unverified — needs runtime/infra confirmation" instead of guessing.

## 3. Mandatory Repository Walk Order
Perform the review in this order so you do not miss architectural boundaries:
1. `README.md`, `config/`, `app/config.py` (or equivalent) — single source of truth for settings; `.env.example` completeness.
2. `app/main.py` — lifespan, middleware (CORS/logging), router mounting, global exception handlers.
3. `app/api/v1/routes.py` — HTTP adapter only? Status codes (200 vs 201 vs 202), dependency injection (`Depends`).
4. `app/core/models.py` — schemas, enums, validators, serialization config; `opportunityId` presence on payloads that traverse LMP phases.
5. `app/core/logic.py` — orchestration and pure-ish domain steps; absence of FastAPI imports; testability seams.
6. `clients/` — timeouts/retries, error mapping to domain errors; secrets never embedded; SSRF-sensitive URL parameters (`reportHtmlUrl`, `driveFolderUrl`, arbitrary fetch targets).
7. `tests/` — unit coverage for `logic.py`, route integration smoke; mocks at client boundary.

*For each layer, note violations of `avoid_mistakes.md` (logic in routes, raw dicts, broad except, blocking I/O in async routes, chatty synchronous chains across services).*

## 4. LMP Naming & API Contract Gates (Automatic "fail" if violated)
Explicitly verify:
- **Primary ID (`reference.md §1`)**: `opportunityId` in every request/response that participates in LMP linkage (exceptions only if documented and justified in-code).
- **JSON casing (`reference.md`, `.cursorrules`)**: Exported JSON uses `camelCase`; Python uses `snake_case` internally; models use `Field(alias=...)` + `model_config`.
- **Paths (`reference.md`)**: Routers under `/api/v1/<kebab-service>`.
- **Errors (`avoid_mistakes.md §4`)**: Consistent `detail` + `errorCode` where applicable (and match actual FastAPI exception handlers).
- **Layering (`.cursorrules`)**: No business logic in `routes.py`; no FastAPI in `logic.py`.

## 5. Phase/Service-Specific Focus & Business Logic Correctness
Tune depth using the service's documented responsibility in `reference.md`. Ensure that the core domain logic actually satisfies the platform's business requirements for this phase. Look for logic gaps or missed edge cases in `app/core/logic.py`.

**A. Prep / Opportunity-style APIs**
- List endpoints: pagination, filtering semantics (`#LMP`), stable sort keys.
- BigQuery vs Spanner/client boundaries — no N+1 patterns pulling one row per opportunity.
- Business Logic: Are opportunities properly enriched? Is the cache invalidation (if any) robust?

**B. Assess / MAT-style async APIs**
- Trigger returns fast (`jobId`, 202 if applicable); polling semantics; terminal states and partial failure visibility.
- Idempotency of triggers and ingestion (retries-safe).
- No distributed monolith: avoid mandatory 3-service synchronous chains for one user action.
- Business Logic: Are state transitions mapped correctly (e.g., PENDING -> RUNNING -> SUCCESS/FAILED)? 

**C. Report Converter (generic HTML pipeline)**
- URL/HTML ingress safety (size limits, SSRF mitigations where URLs are fetched).
- Determinism of conversion steps; handling of malformed HTML; no silent truncation without logging/metrics.
- Business Logic: Does it preserve essential graph data and metadata without silently dropping them?

**D. Context Agent / ADK + RAG**
- Boundary between tool retrieval vs prompt stuffing; session/sessionId behavior; corpus ID validation.
- Failure semantics when Drive/RAG partially fails — align with documented "non-fatal upload" behaviors in `reference.md` where stated.
- Prompt/version/config centralized (no scattered model strings).
- Business Logic: Are all 4 sub-agents properly queried, and are their results reliably synthesized?

**E. Arch Agent (multi-agent diagram generation)**
- Resource limits (batch size, file size, timeouts).
- Evaluator loop semantics — starvation, infinite retry risk, billing/DoW (note overlap with vulnerability skill).
- Output encoding (`imageBase64`) and error reporting when rendering fails.
- Business Logic: Does it correctly fall back if Gemini struggles to output valid graph syntax?

## 6. Python / FastAPI Execution Model & Resource Management
Beyond swallowed exceptions and transactions, explicitly hunt for memory, concurrency, and lifecycle leaks:
- **async def vs def**: I/O-bound paths must not block the event loop (CPU-heavy parsers, synchronous HTTP in async handlers). Flag `requests` inside `async def` without thread offload.
- **Resource Leaks (Unclosed Connections)**: Hunt for database sessions, file streams, or HTTP client pools opened without `async with` or explicit `.close()`.
- **Unbounded Concurrency**: Flag places where `asyncio.gather()` or `BackgroundTasks` are used on dynamic lists without limits or semaphores. (Prevents OOM crashes).
- **Large Payload Handling**: Check if the service attempts to load massive files entirely into memory instead of streaming them.
- **Graceful Startup & Shutdown**: Verify that `app/main.py` uses a FastAPI `@asynccontextmanager` `lifespan` to cleanly finish in-flight requests and close DB/HTTP clients on SIGTERM, rather than relying on outdated `@app.on_event`.
- **Typing**: Missing type hints, `Any`-heavy public APIs, or Pydantic v1 patterns in a v2 codebase.
- **Testing**: Per `.cursor/rules/test-driven-development.mdc`, flag behavioral gaps — e.g. `logic.py` branches with no unit test mirror.

## 7. Configuration Hygiene
Extend your "static file intent" with repo rules:
- **Single settings singleton**: No `get_settings()` factories; no `os.getenv` outside config (per `.cursor/rules/no-hardcoded-env-vars.mdc`).
- **settings.yaml + .env.example**: Document new knobs; prod vs dev parity.
- **Secrets**: No tokens in tests/fixtures intended for CI; rotate if leaked in history (note as process, not automated fix).

## 8. Observability, Operations & Platform Stability
Flag missing or inconsistent operational readiness:
- **Structured logging** (JSON on Cloud Run), correlation identifiers (`opportunityId`, `jobId`, `request_id` if present).
- **Health/readiness** routes for deploy platforms.
- **Dockerfile**: non-root user, pinned base, sane `WORKDIR`, reasonable image size signals.
- **Pinned Dependencies**: Ensure `requirements.txt` strictly pins versions (e.g., `fastapi==0.104.1`) to prevent random deployment breakages.
- **Strict Ingress Validation (Poison Pill Prevention)**: Ensure Pydantic models use strict boundaries (`max_length`, regex, `le`, `ge`) to prevent excessively large inputs from crashing the service or LLM limits.
- **Advanced Outbound Resilience**: In addition to checking for base timeouts, flag missing exponential backoff/jitter (e.g., using `tenacity`) or circuit breakers for critical external client calls (Spanner, Gemini, Drive).

## 9. Severity Rubric
Assign each finding:
- **P0 — Correctness/security/data loss:** wrong contract, privilege bypass pattern, destructive partial writes, SSRF/token leak, guaranteed OOM leaks.
- **P1 — Reliability:** swallowed errors, missing timeouts/retries, unbounded concurrency, non-idempotent money/job paths, missing bounds on user input.
- **P2 — Maintainability / standards drift:** layering breach, duplicated config, weak typing, unpinned dependencies.
- **P3 — Hygiene:** logging noise, minor naming inconsistency inside internal-only code paths.

## 10. Output Format
Use Markdown with this top-level skeleton:

```markdown
## Scope
- Service: ...
- Paths reviewed: ...
- Reference: reference.md §X (paste relevant excerpt only if helpful)

## Executive summary
- Top 3 risks (with severities)

## Contract & layering
(findings...)

## Platform Stability & Resource Management
(findings covering leaks, concurrency, payload sizes, lifecycles...)

## Resilience & Outbound Correctness
(findings covering timeouts, retries, backoff...)

## Security, Ingress Validation & Abuse
(findings covering poison pills, bounds, SSRF...)

## Config & Ops
(findings covering config, logging, Docker, pinned dependencies...)

## Tests & quality gates
(findings...)

## Cross-service coupling & workflow fit
(drifts vs async/sync patterns; undue chatty coupling)

## Procedural prerequisites
(env vars, migrations, IAM, corpus setup, CI, manual runbooks — only if evidenced or explicitly unknown)

## Findings backlog
| Severity | Location | Risk | Proposed remediation | Observed vs Expected |
|----------|----------|------|----------------------|----------------------|
| ...      | ...      | ...  | ...                  | ...                  |
```

*Per finding, keep your triad: Location (`file:line-range`), Risk, Proposed remediation.*

## 11. "Done" Criteria
A review counts complete when:
1. Every exported route in `routes.py` has a traced path through logic and clients (or a documented justification if missing).
2. `models.py` vs `reference.md` for that service is explicitly compared for field names and required IDs.
3. Config is checked against `no-hardcoded-env-vars` rules.
4. `tests/unit/test_logic.py` (or equivalent) coverage gaps are noted for each non-trivial branch in `logic.py`.
5. Operational & Stability risks (unbounded concurrency, leaks, `lifespan` handlers, timeouts, logging, Dockerfile) have been verified.

**Trade-offs (brief)**
- **Depth vs time**: Phase-specific sections (§5) prioritize the highest-loss paths for that service; full security assessment remains a separate skill.
- **Strict citations vs exploratory notes**: Separate evidenced findings from hypotheses so the backlog stays honest.
- **Review-only vs fix**: Keeps audits trustworthy; flipping to implementation should be explicit so TDD/repo rules kick in.
