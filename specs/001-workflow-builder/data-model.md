# Phase 1 Data Model: Agentic Workflow Builder

SQLite, accessed via SQLModel. All tables below are the app's own tables; LangGraph's checkpointer manages its own internal tables (`checkpoints`, `checkpoint_writes`, etc., created automatically by `AsyncSqliteSaver`) in the same SQLite file — they are not modeled here since the app never queries them directly, only through the LangGraph API.

## Workflow

Represents a named, versioned workflow. Maps to spec **Workflow** entity.

| Field | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| name | str, unique, indexed | The chat-invocation name. Enforced unique across ALL workflows at the DB level (FR-004) — a `UNIQUE` constraint, not just app-level validation, so the "reject at save time" rule can't be raced. |
| active_version_id | UUID (FK → WorkflowVersion.id), nullable | Which version chat invocation currently runs; set on create and on explicit revert (FR-005). |
| created_at | datetime | |

**Validation rules**: `name` non-empty, unique (DB constraint + friendly 409 error surfaced by the API). Creating a Workflow with a name colliding with an existing one is rejected outright (spec Clarifications: reject-at-save-time), not merged into the existing row.

## WorkflowVersion

Immutable snapshot. Maps to spec **Workflow Version** entity.

| Field | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| workflow_id | UUID (FK → Workflow.id) | |
| version_number | int | Monotonically increasing per workflow, starting at 1. |
| graph_json | JSON (text) | The full canvas save payload — see `contracts/graph-schema.md`. Immutable once written. |
| created_at | datetime | |

**Validation rules**: `graph_json` must pass the FR-003 structural checks (no dangling edges, Decision has true/false, every API/LLM/Code/Sub-workflow failure output connected, every Retry give-up output connected, Variable names unique within this version, at least one path reaches a Response node) before a row is written — validation happens in the API layer before persistence, not as a DB constraint (too structural for SQL to express).

**State transitions**: none — versions are immutable. "Editing" a workflow always produces a new WorkflowVersion row; "reverting" only changes `Workflow.active_version_id`, it never mutates a WorkflowVersion.

## Run

One execution of a specific WorkflowVersion. Maps to spec **Run** entity.

| Field | Type | Notes |
|---|---|---|
| id | UUID (PK) | Also used as the LangGraph checkpointer `thread_id`. |
| workflow_version_id | UUID (FK → WorkflowVersion.id) | Pinned at start — later edits to the workflow don't affect an in-flight or completed Run. |
| status | enum: `running`, `paused`, `completed`, `failed` | |
| pending_prompt | JSON (text), nullable | Set when `status = paused`; holds the Input node's question shown in chat. Cleared on resume. |
| started_at | datetime | |
| ended_at | datetime, nullable | |
| chat_session_id | UUID (FK → ChatSession.id) | Which chat conversation this Run belongs to. |

**State transitions**: `running → paused` (hits an Input node mid-flow) → `running` (user replies, resumed) → ... → `completed` (a Response node reached) or `failed` (unhandled failure — a failure output routed to nothing recoverable, or the process-restart reconciliation rule in research.md §7).

## NodeExecution

One node's execution record within a Run. Maps to spec **Node Execution** entity.

| Field | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| run_id | UUID (FK → Run.id) | |
| node_id | str | The node's ID within the workflow's `graph_json` (stable across a version). |
| node_type | str | e.g. `"api"`, `"llm"`, `"retry"` — denormalized for fast audit queries without joining back to `graph_json`. |
| output_port | str | Which output fired: `success`/`failure`, `true`/`false`, `retry`/`give-up`, or `"default"` for single-output node types. |
| input_json | JSON (text) | What the node received (post-`{{variable}}` resolution, so the audit log shows what actually ran). |
| output_json | JSON (text) | What the node produced. |
| attempt_count | int, nullable | Only meaningful for Retry nodes — current attempt number at this execution. |
| started_at | datetime | |
| ended_at | datetime | |

Satisfies FR-029 (full node-by-node audit trail, including which output fired) and SC-007.

## RunVariable

A queryable mirror of Variable-node writes for a Run, satisfying spec **Variable** entity and making SC-009 checkable without inspecting LangGraph's internal checkpoint blobs directly.

| Field | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| run_id | UUID (FK → Run.id) | |
| name | str | The Variable node's configured name. |
| value_json | JSON (text) | |
| set_at | datetime | |

**Note**: this table is a write-through audit copy. The live source of truth *during* execution is `GraphState["variables"]` inside the LangGraph checkpoint (research.md §4) — `RunVariable` rows are written by the same node function immediately after updating state, purely so the audit/log UI (and SC-009 verification) doesn't need to reach into checkpoint internals.

**Validation rules**: uniqueness of variable *names* is enforced at the WorkflowVersion/`graph_json` level (two Variable nodes in the same version can't share a name — FR-003/User Story 5 Acceptance Scenario 2), not at this table's level, since the same name legitimately recurs across different Runs of the same workflow.

## Credential

Encrypted secret, referenced by name/ID from node configs. Maps to spec **Credential** entity.

| Field | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| name | str, unique | What node configs reference (e.g. `{{cred:openai-key}}`-style reference in provider config — resolved server-side only, never sent to the frontend after creation). |
| encrypted_value | bytes | Fernet ciphertext (research.md §9). |
| created_at | datetime | |

**Validation rules**: `encrypted_value` is never returned by any GET endpoint (write-only from the API consumer's perspective; only `name` and `created_at` are readable). Never appears in `graph_json`, `input_json`, or `output_json` — node configs store the Credential's `id`/`name`, resolved server-side at execution time only.

## ChatSession / ChatMessage

The conversational channel. Maps to spec **Chat Session** entity.

| ChatSession | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| created_at | datetime | |

| ChatMessage | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| chat_session_id | UUID (FK) | |
| role | enum: `user`, `system` | `system` covers both Input-node prompts and Response-node outputs shown back to the user. |
| content | str | |
| run_id | UUID (FK → Run.id), nullable | Which Run this message relates to, if any (a bare "workflow not found" system message has none). |
| created_at | datetime | |

**Relationship note**: `ChatSession` is intentionally decoupled from `Run` — one chat conversation can start multiple Runs over time (invoke workflow A, get a response, invoke workflow B next), and this table is what actually renders as the chat transcript in the UI, separate from the structured `NodeExecution` audit log.

## Entity Relationship Summary

```text
Workflow 1---* WorkflowVersion 1---* Run 1---* NodeExecution
                                        |  1---* RunVariable
                                        *---1 ChatSession 1---* ChatMessage
Credential (standalone, referenced by id/name from graph_json node configs)
```
