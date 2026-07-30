# Phase 0 Research: Agentic Workflow Builder

All Technical Context fields in plan.md are resolved (none left as NEEDS CLARIFICATION). This document records the non-obvious decisions and why alternatives were rejected.

## 1. Compiling a visual graph into LangGraph

**Decision**: A `compiler.py` module walks the saved `graph_json` (nodes + typed edges) and builds a `langgraph.graph.StateGraph`. Every node type maps to one node function of shape `(state: GraphState) -> GraphState`. Nodes with more than one output port (Decision: true/false; API/LLM/Code/Sub-workflow: success/failure; Retry: retry/give-up) are wired using `add_conditional_edges`, where the node function writes its outcome into a per-node field of state and a small routing function reads it back to pick the next node ID.

**Rationale**: This keeps the canvas's visual model and the runtime model isomorphic — the constitution's "Visual Graph Is the Source of Truth" principle only holds if there's no translation step that can drift from what's drawn. LangGraph's conditional edges are designed for exactly this branch-on-prior-node-outcome pattern.

**Alternatives considered**: Generating LangChain LCEL (`RunnableBranch`/pipe syntax) directly instead of LangGraph — rejected because LCEL chains are fundamentally acyclic/expression-oriented, and the Retry node requires an actual cycle back to a prior node, which LangGraph supports natively and LCEL does not.

## 2. Human-in-the-loop pausing and resuming

**Decision**: Use LangGraph's native `interrupt()` inside the Input node's function when it's reached mid-flow, combined with `AsyncSqliteSaver` as the checkpointer (same SQLite file as the rest of the app). Each Run's `thread_id` (LangGraph's term) is the Run's own UUID. Resuming happens via `graph.ainvoke(Command(resume=user_reply), config={"configurable": {"thread_id": run_id}})`.

**Rationale**: This is precisely the scenario `interrupt()`/`Command(resume=...)` was built for in LangGraph, and it satisfies FR-011 (paused runs persist independent of any chat connection) for free — the checkpointer, not an in-memory object, is the source of truth for "what's this run waiting on."

**Alternatives considered**: Hand-rolled pause/resume (store "current node ID" + partial state in a custom table, manually re-invoke from that node on resume) — rejected as reinventing what the chosen runtime already provides, and higher risk of subtly losing state that `interrupt()`/checkpointing handles correctly (e.g., partial results from sibling branches in a not-yet-merged parallel section).

## 3. Retry as a bounded graph cycle

**Decision**: The Retry node's function reads `state["retry_counts"].get(retry_node_id, 0)`, increments it, and if `< max_attempts` (from the node's config) routes back to the ID of the node that failed into it; otherwise routes to the "give up" edge. `retry_counts` lives in `GraphState` so it's checkpointed like everything else and survives a pause/resume inside a retry loop (e.g., if attempt 2 itself pauses on an Input node somehow — edge case, but the state model handles it for free).

**Rationale**: Keeps retry logic entirely inside ordinary LangGraph state/routing rather than a separate subsystem; also means SC-008 ("exactly 3 attempts, never more") is enforced by a plain integer comparison, easy to unit test in isolation.

**Alternatives considered**: LangGraph's own `recursion_limit` as the retry bound — rejected as the wrong tool: it's a global safety valve for the whole graph (default 25), not a per-Retry-node, per-run, user-configurable count, and hitting it raises an error rather than cleanly routing to a "give up" edge.

## 4. Referencing `{{variables}}` and upstream node outputs

**Decision**: `GraphState` carries two dicts: `variables: dict[str, Any]` (written only by Variable nodes, keyed by the builder-chosen unique name) and `node_outputs: dict[str, Any]` (written by every node after it runs, keyed by node ID, used for direct upstream references that don't go through an explicit Variable node). Any config field marked as "interpolable" (LLM prompt, API URL/headers/body, Decision condition, Response content) is rendered through a small `render_template(text: str, state: GraphState) -> str` function that resolves `{{name}}` against `variables` first, matching FR-023/FR-025 (missing variable → failure of the referencing node, not empty-string).

**Rationale**: Two dicts instead of one keeps the explicit "I chose to remember this" (Variable) mechanism (FR-022) cleanly separated from the implicit "read my direct upstream neighbor's output" mechanism the other node types' configs already imply — they have different lifetimes and different failure semantics (FR-025 only applies to `{{variable}}` lookups, not direct edge-based references, which are guaranteed present by graph construction).

**Alternatives considered**: A single Jinja2 environment instead of a minimal hand-rolled `{{name}}` resolver — rejected for v1 as unnecessary surface area (Jinja2 supports loops/filters/arbitrary expressions the spec never asked for, and it's one more thing the Code node sandbox discussion would have to consider by association even though prompt templates aren't executed as code).

## 5. Code node sandboxing

**Decision**: Layered defense — (a) statically reject snippets containing disallowed imports (`socket`, `subprocess`, `os` beyond a small allowlist, `sys`) via `RestrictedPython`'s compiler, which also removes access to dunder attribute traversal (a common sandbox-escape vector); (b) execute the compiled snippet in a short-lived subprocess with `resource.setrlimit` caps on CPU time, address space, and open files, and a wall-clock timeout enforced by the parent process killing the subprocess; (c) no network namespace access — the subprocess's environment strips proxy variables and `RestrictedPython`'s import blocking prevents reaching `socket`/`http.client`/`urllib` in the first place, so there's no live network path to block at the OS level for the common case, with the process-level resource limits as backstop.

**Rationale**: Matches Constitution VI's threat model explicitly: "prevent accidents/mistakes among ~5 trusted teammates," not "withstand a malicious actor with subprocess-level exploit development skills." `RestrictedPython` is a real, maintained library built for exactly this (used by Zope/Plone for user-supplied code for years), and subprocess + `resource` limits are pure standard library — no new heavyweight infrastructure (no gVisor, no per-execution Docker-outside-of-Docker container) for a v1 prototype.

**Alternatives considered**: Per-execution ephemeral Docker container (`docker run --network none --rm`) — noted as the natural v2 upgrade if the threat model ever expands beyond trusted teammates, but rejected for v1 as it requires the app container to have Docker socket access (itself a meaningful privilege-escalation surface) purely to sandbox something a much lighter mechanism already covers for the stated threat model.

## 6. Serializing LLM calls to Ollama

**Decision**: A single process-wide `asyncio.Semaphore(1)` wraps every call the `OllamaProvider` makes. All concurrently-running graphs share the same provider instance and therefore the same semaphore.

**Rationale**: Directly implements FR-026. An in-process primitive is sufficient because the whole app is one FastAPI process (no horizontal scaling for a 5-person self-hosted tool) — no need for a distributed lock (Redis, etc.).

**Alternatives considered**: Configurable concurrency > 1 (a `Semaphore(N)`) — this was actually one of the options offered during clarification; the user chose strict serialization (N=1) for v1. The code still isolates this behind one constant so raising it later is a one-line change, not a redesign.

## 7. Background run execution without a distributed task queue

**Decision**: Each Run starts as an `asyncio.create_task(...)` inside the FastAPI process, tracked in an in-memory registry keyed by run_id for fast status lookups, with the LangGraph checkpointer as the durable source of truth for anything paused. On process restart, any Run whose last known status was "running" (not "paused") is marked "failed — server restarted mid-execution" on startup, since there's no way to safely resume a task that wasn't at a checkpoint boundary; "paused" runs are unaffected and resume normally since their state was already durably checkpointed.

**Rationale**: Celery/RQ/a Redis-backed queue would be disproportionate infrastructure for ~5 users and adds a service most self-hosters wouldn't want to operate. The explicit restart-reconciliation rule keeps the "known limitation" honest and bounded rather than silently losing runs.

**Alternatives considered**: A durable, restart-safe task queue (Celery+Redis) — rejected for v1 as scope disproportionate to team size; flagged as a natural upgrade path if NextGen ever needs multi-instance deployment.

## 8. Shared application password gate

**Decision**: A FastAPI middleware checks a signed session cookie (via `itsdangerous`), issued after a `POST /auth/login` compares the submitted password against `NEXTGEN_APP_PASSWORD` (env var) using constant-time comparison. No per-user accounts (Constitution: "Access control (v1)").

**Rationale**: Simplest implementation of the agreed v1 tradeoff; avoids building a user table/login UI that the spec explicitly deferred.

**Alternatives considered**: HTTP Basic Auth at a reverse-proxy layer instead of an app-level gate — viable and even simpler, but rejected as the default because it would require documenting a reverse-proxy as a hard deployment dependency; the app-level gate keeps `docker compose up` self-sufficient (SC-006), and a reverse proxy can still be layered in front for TLS termination without changing this.

## 9. Credential encryption

**Decision**: `cryptography.fernet.Fernet`, key from `NEXTGEN_CREDENTIAL_KEY` env var (generated once via `Fernet.generate_key()` and provided as a Docker secret/`.env` value at deploy time, documented in quickstart.md). `Credential` rows store `name` + `encrypted_value`; decrypted only transiently in-memory when a node execution needs it.

**Rationale**: Fernet is authenticated symmetric encryption, simple to operate correctly (no IV management footguns), and is the standard, well-reviewed choice for "encrypt a small secret at rest with a single key" in Python.

**Alternatives considered**: OS keychain integration — rejected as impractical inside a Linux Docker container with no consistent keychain daemon across self-hosting environments.
