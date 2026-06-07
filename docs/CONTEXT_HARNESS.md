# Thekedar Context Harness

Thekedar implements a secure, reliable, and high-performance context delivery pipeline that feeds global codebase knowledge into LLMs and IDE adapters while maintaining a strict freshness contract.

---

## 1. Freshness Contract & SHA Gate

Before any `@Coder` run executes a coding task, the system asserts context freshness:

```
┌─────────────────────┐         Compare         ┌────────────────────────┐
│  Latest Snapshot    │ <=====================> │ Remote Workstation HEAD│
│  (Indexed Context)  │                         │ (Current Git SHA)      │
└─────────────────────┘                         └────────────────────────┘
```

* **Staleness Warnings:** In local development or demo environments, a SHA mismatch emits a warning header to chat prompts but allows continuation.
* **The SHA Gate (Staging/Production):** If `THEKEDAR_ENVIRONMENT` is set to `staging` or `prod`, a SHA mismatch **blocks execution immediately** with an aborted status.
* **Bypass Overrides:** Stale context can be bypassed if the user explicitly authorizes it by replying with `"override"` or `"override stale"`, which sets the `override_stale_context` flag in the pipeline state.
* **Resume Freshness Validation:** Freshness is re-checked during `resume()` calls before advancing to coding, protecting against staleness when an approval remains pending across multiple developer commits.

---

## 2. Context Indexing & Retrieval

The repository is indexed into logical database partitions represented by `ContextChunk` rows:

* `repo_manifest`: Metadata from configuration and manifest files (e.g., `pyproject.toml`, `package.json`).
* `doc_chunks`: Human-written markdown documents and guides.
* `symbol_index`: Classes, functions, and method signatures extracted from Python source files.
* `test_map`: Available test paths and CI workflow locations.
* `security_profile`: Hardening parameters, compliance targets, and security paths.

### Filtering by Chunk Types

The `ContextRetriever` supports targeted filtering on `ContextQuery` parameters using `chunk_types`:

```python
# Query only humans-written docs and python symbol signatures
query = ContextQuery(
    tenant_id="default",
    repo="my-repo",
    keywords=["authentication"],
    chunk_types=["doc", "symbol"]
)
hits = retriever.query(session, query)
```

---

## 3. Evidence Linkage on Execution Plans

To ensure transparency and explainability, every generated `ExecutionPlan` contains explicit evidence linkage. The planner maps the affected file list to specific indexed chunk IDs in the database:

```json
{
  "summary": "Fix login auth redirect issues",
  "files_to_touch": ["packages/shared/src/thekedar_shared/auth.py"],
  "evidence": [
    {
      "filepath": "packages/shared/src/thekedar_shared/auth.py",
      "chunk_ids": ["doc-chunk-auth_py", "impact-evidence-auth_py"]
    }
  ]
}
```

---

## 4. Prompt Isolation & Security Hardening

To mitigate prompt injection attacks, user requests are sanitized and strictly isolated from instructions:

1. **Tag Filtering:** `sanitize_user_text(request_text)` strips tag boundaries (e.g. `</user_query>`, `<ground_truth_context>`) to prevent context escapes.
2. **Encapsulation:** The user query is placed inside isolated `<user_query>` tags.
3. **Ground Truth:** Structured codebase context is wrapped inside `<ground_truth_context>` tags. System prompts treat this block as immutable read-only input.

---

## 5. Context Evaluation (CI Gates)

We run continuous verification suites to guard against indexing or retrieval regressions:

* `tests/eval/context_retrieval_golden.jsonl`: 50 golden retrieval query-expected file mappings.
* `tests/eval/impact_injection_adversarial.jsonl`: Adversarial prompt injection payloads checking sanitization security.
* `tests/eval/approval_confusion.jsonl`: Multi-phased approval intents ensuring robust classification.
