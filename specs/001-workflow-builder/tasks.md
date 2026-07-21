---

description: "Task list for Agentic Workflow Builder (NextGen v1)"
---

# Tasks: Agentic Workflow Builder (NextGen v1)

**Input**: Design documents from `/specs/001-workflow-builder/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: Included — plan.md commits to pytest/Vitest and a scripted quickstart smoke test, so contract/integration test tasks are generated alongside implementation, not as an afterthought.

**Organization**: Tasks are grouped by user story (spec.md priorities P1–P13) so each story is independently implementable, testable, and deployable as an increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US13)
- File paths are exact, per plan.md's Project Structure

---

## Phase 1: Setup

**Purpose**: Project initialization and basic structure

- [ ] T001 Create backend/ and frontend/ directory skeletons per plan.md Project Structure (empty `__init__.py`s, `app/` subpackages, `frontend/src/` subfolders)
- [ ] T002 [P] Initialize Python backend: `backend/pyproject.toml` with FastAPI, Uvicorn, SQLModel, LangChain, LangGraph, `langgraph-checkpoint-sqlite`, `cryptography`, `RestrictedPython`, `httpx`, `itsdangerous`, pytest, `httpx[ws]`
- [ ] T003 [P] Initialize frontend: `frontend/package.json` with React 18, TypeScript, Vite, `@xyflow/react`, Vitest, React Testing Library
- [ ] T004 [P] Configure backend linting/formatting (ruff + black) in `backend/pyproject.toml`
- [ ] T005 [P] Configure frontend linting/formatting (eslint + prettier) in `frontend/.eslintrc.cjs`
- [ ] T006 Write `Dockerfile` (pinned `python:3.11-slim` base, per plan.md Technical Context note on the 3.10-only sandbox) and `docker-compose.yml` (`app` + `ollama` services) at repo root
- [ ] T007 [P] Write `.env.example` at repo root with `NEXTGEN_APP_PASSWORD`, `NEXTGEN_CREDENTIAL_KEY`, `OLLAMA_BASE_URL` per quickstart.md Setup

**Checkpoint**: Repo builds and containers start empty — no functionality yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 [P] Define `Workflow` and `WorkflowVersion` SQLModel tables in `backend/app/models/workflow.py` per data-model.md
- [ ] T009 [P] Define `Run` and `NodeExecution` SQLModel tables in `backend/app/models/run.py` per data-model.md
- [ ] T010 [P] Define `RunVariable` SQLModel table in `backend/app/models/variable.py` per data-model.md
- [ ] T011 [P] Define `Credential` SQLModel table in `backend/app/models/credential.py` per data-model.md
- [ ] T012 [P] Define `ChatSession` and `ChatMessage` SQLModel tables in `backend/app/models/chat.py` per data-model.md
- [ ] T013 Setup SQLite engine/session management in `backend/app/db.py`, pointed at the same file `AsyncSqliteSaver` will use (depends on T008-T012)
- [ ] T014 Implement shared-password session middleware and `POST /auth/login` + `/auth/logout` in `backend/app/auth.py` per research.md §8 and contracts/rest-api.md
- [ ] T015 [P] Implement Fernet credential encryption utility (`encrypt`/`decrypt` using `NEXTGEN_CREDENTIAL_KEY`) in `backend/app/crypto.py` per research.md §9
- [ ] T016 [P] Implement Credential REST endpoints (`GET/POST /api/credentials`, `DELETE /api/credentials/{id}`) in `backend/app/api/credentials.py` per contracts/rest-api.md (depends on T011, T015)
- [ ] T017 Define shared `GraphState` TypedDict (`variables`, `node_outputs`, `retry_counts`, `pending_input`, `run_id`, `workflow_id`, `workflow_version`) in `backend/app/graph/state.py` per research.md §4
- [ ] T018 Implement node-type registry and Pydantic config schema base classes in `backend/app/graph/schema.py` per contracts/graph-schema.md
- [ ] T019 Implement `{{variable}}` template resolution (`render_template`), resolving against `state["variables"]` with FR-025 missing-variable-is-a-failure behavior, in `backend/app/graph/templating.py` per research.md §4
- [ ] T020 Implement the graph_json save-time validator (all 7 checks: dangling edges, Decision true/false completeness, API/LLM/Code/Sub-workflow success/failure completeness, Retry retry/give-up completeness, Variable name uniqueness, at least one reachable Response, valid `source_port` per node type) in `backend/app/graph/validation.py` per contracts/graph-schema.md (depends on T018)
- [ ] T021 Implement the LangGraph compiler (`graph_json` → `StateGraph`) with **generic** conditional-edge routing for every multi-port node type (Decision true/false; API/LLM/Code/Sub-workflow success/failure; Retry retry/give-up) in `backend/app/graph/compiler.py` per research.md §1 (depends on T017, T018)
- [ ] T022 Implement provider-agnostic `ModelProvider` base class in `backend/app/providers/base.py` and `OllamaProvider` with a process-wide `asyncio.Semaphore(1)` in `backend/app/providers/ollama_provider.py` per research.md §6
- [ ] T023 Implement the audit logging utility (writes one `NodeExecution` row — including `output_port` and `attempt_count` — immediately after each node executes) in `backend/app/runtime/audit.py` per data-model.md NodeExecution
- [ ] T024 Implement the run executor: `asyncio.create_task` per Run, `AsyncSqliteSaver` checkpointer wired with `thread_id = run_id`, and startup reconciliation marking stale `running` rows `failed` in `backend/app/runtime/executor.py` per research.md §2, §7 (depends on T013, T021, T023)
- [ ] T025 [P] Implement `GET/POST /api/workflows`, `GET /api/workflows/{id}`, `GET/POST /api/workflows/{id}/versions`, `POST /api/workflows/{id}/activate/{version_id}`, `DELETE /api/workflows/{id}` in `backend/app/api/workflows.py` per contracts/rest-api.md (depends on T008, T020)
- [ ] T026 [P] Implement `GET /api/runs/{id}`, `/executions`, `/variables`, and `GET /api/runs` list in `backend/app/api/runs.py` per contracts/rest-api.md (depends on T009, T010)
- [ ] T027 Implement the `/ws/chat` handler skeleton (message envelope dispatch, session creation/lookup, history replay on reconnect) in `backend/app/chat/websocket.py` per contracts/chat-websocket.md (depends on T012, T024)
- [ ] T028 [P] Implement the React Flow canvas shell (node palette, drag-drop, save/load via REST client) in `frontend/src/canvas/Canvas.tsx`
- [ ] T029 [P] Implement the typed REST + WebSocket client in `frontend/src/api/client.ts`
- [ ] T030 [P] Implement the password-gate login screen in `frontend/src/auth/Login.tsx`
- [ ] T031 Wire `backend/app/main.py`: mount all routers (auth, workflows, runs, credentials, chat websocket), password-gate middleware, and app startup reconciliation call (depends on T014, T016, T024, T025, T026, T027)

**Checkpoint**: Foundation ready — every user story phase below can now be implemented.

---

## Phase 3: User Story 1 - Build and run the core loop: Input → LLM → Response (Priority: P1) 🎯 MVP

**Goal**: A user can build Input → LLM → Response on the canvas, save it, invoke it by name in chat, and see the LLM's response.

**Independent Test**: Build exactly this 3-node flow, save it, invoke by name in chat, supply a value, confirm the response is displayed (quickstart.md Scenario 1).

### Tests for User Story 1

- [ ] T032 [P] [US1] Contract test for `POST /api/workflows` create+validate in `backend/tests/contract/test_workflows_api.py`
- [ ] T033 [P] [US1] Integration test scripting quickstart.md Scenario 1 (core loop) against the real WebSocket endpoint in `backend/tests/integration/test_core_loop.py`

### Implementation for User Story 1

- [ ] T034 [P] [US1] Implement Input node config schema + execution function (start-of-flow parameter collection via `interrupt()`) in `backend/app/graph/nodes/input_node.py`
- [ ] T035 [P] [US1] Implement LLM node config schema + execution function (calls `OllamaProvider`, success/failure output, configurable execution timeout per FR-018) in `backend/app/graph/nodes/llm_node.py` (depends on T022)
- [ ] T036 [P] [US1] Implement Response node config schema + execution function (renders `content` via `templating.py`, terminal node) in `backend/app/graph/nodes/response_node.py` (depends on T019)
- [ ] T037 [US1] Wire `start_workflow` / `provide_input` / `input_request` / `response` / `status` / `workflow_not_found` message handling in `backend/app/chat/websocket.py` (depends on T027, T034-T036)
- [ ] T038 [P] [US1] Implement Input/LLM/Response canvas node components in `frontend/src/canvas/nodes/InputNode.tsx`, `LlmNode.tsx`, `ResponseNode.tsx` (depends on T028)
- [ ] T039 [P] [US1] Implement `ChatWindow.tsx` and `useChatSocket.ts` in `frontend/src/chat/` (depends on T029)
- [ ] T040 [US1] Implement workflow list + "open in chat" entry point in `frontend/src/workflows/WorkflowList.tsx` (depends on T038, T039)

**Checkpoint**: MVP complete — Input → LLM → Response works end-to-end via chat.

---

## Phase 4: User Story 2 - Human-in-the-loop pause mid-flow (Priority: P2)

**Goal**: An Input node placed mid-graph pauses the run and asks in chat; the run resumes on reply, surviving a closed/reopened chat tab.

**Independent Test**: Build Input(start) → LLM → Input(mid-flow) → Decision → Response; confirm pause, reconnect, reply, resume (quickstart.md Scenario 2).

### Tests for User Story 2

- [ ] T041 [P] [US2] Integration test scripting quickstart.md Scenario 2 (pause survives reconnect) in `backend/tests/integration/test_pause_resume.py`

### Implementation for User Story 2

- [ ] T042 [US2] Extend Input node execution function to support mid-flow `interrupt()` calls and persist `Run.pending_prompt` in `backend/app/graph/nodes/input_node.py` (depends on T034)
- [ ] T043 [US2] Implement WebSocket reconnection replay (`history` message + re-sending any pending `input_request` for a paused Run tied to the session) in `backend/app/chat/websocket.py` per contracts/chat-websocket.md Reconnection behavior (depends on T037)
- [ ] T044 [P] [US2] Implement paused-run indicator/resume affordance in `frontend/src/chat/ChatWindow.tsx` (depends on T039)

**Checkpoint**: Mid-flow pauses survive a closed/reopened chat tab (FR-011).

---

## Phase 5: User Story 3 - Decision node branches on prior output (Priority: P3)

**Goal**: A Decision node evaluates a condition against upstream output/`{{variables}}` and routes true/false.

**Independent Test**: Decision node checks an upstream field, routes to distinct Response nodes on true vs. false.

### Tests for User Story 3

- [ ] T045 [P] [US3] Integration test for Decision true/false branching (both directions) in `backend/tests/integration/test_decision_branching.py`

### Implementation for User Story 3

- [ ] T046 [US3] Implement Decision node config schema + execution function (`equals`/`contains`/`gt`/`lt`/`truthy` operators against an upstream field or `{{variable}}`) in `backend/app/graph/nodes/decision_node.py` (depends on T019, T021)
- [ ] T047 [P] [US3] Implement Decision canvas node component (condition builder UI) in `frontend/src/canvas/nodes/DecisionNode.tsx` (depends on T028)

**Checkpoint**: Decision node correctly routes true/false based on prior node output.

---

## Phase 6: User Story 4 - API node calls an external service, with success/failure routing (Priority: P4)

**Goal**: An API node makes an HTTP call; 2xx routes to success, failures (timeout/non-2xx/connection error/exceeded timeout) route to failure.

**Independent Test**: Valid endpoint → success output fires; failing/unreachable endpoint → failure output fires, success does not (quickstart.md Scenario 1's optional failure branch).

### Tests for User Story 4

- [ ] T048 [P] [US4] Contract test for API node success and failure execution paths in `backend/tests/contract/test_api_node.py`

### Implementation for User Story 4

- [ ] T049 [US4] Implement API node config schema + execution function (`httpx` call, credential resolution via `backend/app/crypto.py`, success/failure output, configurable execution timeout) in `backend/app/graph/nodes/api_node.py` (depends on T015, T019, T021)
- [ ] T050 [P] [US4] Implement API canvas node component (method/URL/headers/body fields, credential picker) in `frontend/src/canvas/nodes/ApiNode.tsx` (depends on T028)

**Checkpoint**: API node calls succeed or fail correctly and route accordingly (FR-014, FR-017, FR-018).

---

## Phase 7: User Story 5 - Variable node saves and reuses a value across the flow (Priority: P5)

**Goal**: A Variable node stores a value under a unique name; any later node references it via `{{name}}` regardless of direct wiring.

**Independent Test**: Save a value early, reference `{{name}}` in a non-adjacent later node, confirm correct resolution (SC-009).

### Tests for User Story 5

- [ ] T051 [P] [US5] Integration test for cross-graph variable resolution (SC-009) in `backend/tests/integration/test_variable_scope.py`
- [ ] T052 [P] [US5] Integration test for referencing an unset `{{variable}}` producing a failure, not an empty string (FR-025) in `backend/tests/integration/test_variable_unset_failure.py`

### Implementation for User Story 5

- [ ] T053 [US5] Implement Variable node config schema + execution function (writes to `state["variables"]` and a `RunVariable` row) in `backend/app/graph/nodes/variable_node.py` (depends on T010, T017)
- [ ] T054 [US5] Extend `backend/app/graph/validation.py` with the Variable-name-uniqueness-within-a-workflow check (depends on T020, T053)
- [ ] T055 [P] [US5] Implement Variable canvas node component in `frontend/src/canvas/nodes/VariableNode.tsx` (depends on T028)

**Checkpoint**: Values set by a Variable node are correctly readable via `{{name}}` from anywhere later in the same run.

---

## Phase 8: User Story 6 - Code node transforms data (sandboxed), with success/failure routing (Priority: P6)

**Goal**: A Code node runs a sandboxed Python snippet; violations/timeouts route to failure instead of crashing the run.

**Independent Test**: Valid transform succeeds via success output; a snippet attempting network/filesystem access or exceeding its limit routes to failure (quickstart.md Scenario 4).

### Tests for User Story 6

- [ ] T056 [P] [US6] Integration test scripting quickstart.md Scenario 4 (sandbox blocks malicious code) in `backend/tests/integration/test_code_sandbox.py`

### Implementation for User Story 6

- [ ] T057 [US6] Implement `RestrictedPython` compilation + subprocess execution with `resource.setrlimit` CPU/memory/file caps and a wall-clock timeout in `backend/app/sandbox/run_snippet.py` per research.md §5
- [ ] T058 [US6] Implement Code node config schema + execution function (calls `run_snippet.py`, success/failure routing) in `backend/app/graph/nodes/code_node.py` (depends on T019, T021, T057)
- [ ] T059 [P] [US6] Implement Code canvas node component (code editor field) in `frontend/src/canvas/nodes/CodeNode.tsx` (depends on T028)

**Checkpoint**: Code node transforms data safely; malicious/runaway snippets are blocked, not silently succeeding or crashing the app (SC-005).

---

## Phase 9: User Story 7 - Retry node recovers from a failure automatically (Priority: P7)

**Goal**: A Retry node re-attempts a failed node up to a configured max, then gives up cleanly.

**Independent Test**: Point Retry (max 3) at an always-failing API node; confirm exactly 3 attempts then "give up" fires once (quickstart.md Scenario 3, SC-008).

### Tests for User Story 7

- [ ] T060 [P] [US7] Integration test scripting quickstart.md Scenario 3 (retries exactly N times, never more) in `backend/tests/integration/test_retry_node.py`

### Implementation for User Story 7

- [ ] T061 [US7] Implement Retry node config schema + execution function (`state["retry_counts"]` increment/check against `max_attempts`, retry/give-up routing back to the originating node's ID) in `backend/app/graph/nodes/retry_node.py` per research.md §3 (depends on T017, T021, T049)
- [ ] T062 [P] [US7] Implement Retry canvas node component (`max_attempts` field, retry-loop visual affordance back to the source node) in `frontend/src/canvas/nodes/RetryNode.tsx` (depends on T028)

**Checkpoint**: Retry node retries exactly `max_attempts` times then gives up, never looping indefinitely (SC-008).

---

## Phase 10: User Story 8 - Save, version, and revert workflows (Priority: P8)

**Goal**: Editing and saving a workflow creates a new version; reverting to a prior version reproduces its exact behavior.

**Independent Test**: Save, edit, save again, confirm both versions listed, revert to first, confirm original behavior reproduced (SC-004).

### Tests for User Story 8

- [ ] T063 [P] [US8] Contract test for `POST /api/workflows/{id}/versions` and `/activate/{version_id}` in `backend/tests/contract/test_workflow_versioning.py`
- [ ] T064 [P] [US8] Integration test: save v2, revert to v1, run, confirm v1's recorded behavior exactly reproduced in `backend/tests/integration/test_versioning.py`

### Implementation for User Story 8

- [ ] T065 [US8] Confirm/extend version-history and activate endpoints in `backend/app/api/workflows.py` per contracts/rest-api.md (depends on T025 — largely already covered by Foundational; this task closes any gaps found by T063/T064)
- [ ] T066 [P] [US8] Implement version history list + revert action UI in `frontend/src/workflows/VersionHistory.tsx` (depends on T040)

**Checkpoint**: Editing never destroys history; reverting reproduces prior behavior exactly (SC-004).

---

## Phase 11: User Story 9 - Loop node iterates over a collection (Priority: P9)

**Goal**: A Loop node runs its inner sub-path once per item in an upstream collection and aggregates results.

**Independent Test**: Feed a 3-item list into a Loop wrapping an LLM node; confirm 3 executions and an aggregated downstream result.

### Tests for User Story 9

- [ ] T067 [P] [US9] Integration test for a Loop node iterating a 3-item list in `backend/tests/integration/test_loop_node.py`

### Implementation for User Story 9

- [ ] T068 [US9] Implement Loop node config schema + execution function (per-item sub-path invocation + result aggregation) in `backend/app/graph/nodes/loop_node.py` (depends on T021)
- [ ] T069 [P] [US9] Implement Loop canvas node component (collection reference field, inner sub-path grouping/selection) in `frontend/src/canvas/nodes/LoopNode.tsx` (depends on T028)

**Checkpoint**: Loop node executes its inner path exactly once per item and exposes aggregated results downstream.

---

## Phase 12: User Story 10 - Memory/Retrieval node grounds an LLM node (Priority: P10)

**Goal**: A Memory node queries a configured vector store and returns top-k matches to a downstream LLM node.

**Independent Test**: Configure against a small test vector store, run a query, confirm top-k results feed a connected LLM node's prompt.

### Tests for User Story 10

- [ ] T070 [P] [US10] Integration test for a Memory node returning top-k results in `backend/tests/integration/test_memory_node.py`

### Implementation for User Story 10

- [ ] T071 [US10] Implement Memory/Retrieval node config schema + execution function (LangChain retriever interface query, top_k) in `backend/app/graph/nodes/memory_node.py` (depends on T021)
- [ ] T072 [P] [US10] Implement Memory canvas node component (vector store selector, query field, top_k) in `frontend/src/canvas/nodes/MemoryNode.tsx` (depends on T028)

**Checkpoint**: Memory node correctly grounds a downstream LLM node with retrieved context.

---

## Phase 13: User Story 11 - Tool/function-calling node used by an LLM node (Priority: P11)

**Goal**: An LLM node can invoke a wired Tool node mid-generation via function-calling and use its result.

**Independent Test**: LLM node with one Tool node available; prompt requiring the tool; confirm invocation and result use.

### Tests for User Story 11

- [ ] T073 [P] [US11] Integration test for an LLM node invoking a Tool node mid-generation in `backend/tests/integration/test_tool_node.py`

### Implementation for User Story 11

- [ ] T074 [US11] Implement Tool node config schema + backend tool registry (maps `implementation_ref` to a callable) in `backend/app/graph/nodes/tool_node.py`
- [ ] T075 [US11] Extend LLM node execution function to bind wired Tool nodes as LangChain tools for function-calling in `backend/app/graph/nodes/llm_node.py` (depends on T035, T074)
- [ ] T076 [P] [US11] Implement Tool canvas node component (function name/description, LLM-node linkage) in `frontend/src/canvas/nodes/ToolNode.tsx` (depends on T028)

**Checkpoint**: LLM node can invoke a wired Tool node and incorporate its result into its final output.

---

## Phase 14: User Story 12 - Sub-workflow node embeds another saved workflow, with success/failure routing (Priority: P12)

**Goal**: A Sub-workflow node runs a pinned version of another saved workflow as a single node, with its own success/failure outputs.

**Independent Test**: Save Workflow B, embed pinned in Workflow A, run A, confirm B's Response output surfaces on the Sub-workflow node's success output; confirm pinning ignores later updates to B.

### Tests for User Story 12

- [ ] T077 [P] [US12] Integration test embedding a pinned Workflow B inside Workflow A, including a later-B-update-is-ignored check in `backend/tests/integration/test_subworkflow_node.py`

### Implementation for User Story 12

- [ ] T078 [US12] Implement Sub-workflow node config schema + execution function (compiles and invokes the pinned `WorkflowVersion`'s graph as a nested `StateGraph` run, maps its Response output to this node's success output, unrecoverable errors to failure) in `backend/app/graph/nodes/subworkflow_node.py` (depends on T021, T024)
- [ ] T079 [P] [US12] Implement Sub-workflow canvas node component (workflow + pinned-version picker) in `frontend/src/canvas/nodes/SubworkflowNode.tsx` (depends on T028)

**Checkpoint**: A parent workflow correctly runs an embedded, version-pinned child workflow end to end.

---

## Phase 15: User Story 13 - Merge node combines parallel success branches (Priority: P13)

**Goal**: A Merge node combines multiple incoming success branches into one downstream value once all complete.

**Independent Test**: Two parallel success branches feeding one Merge node; confirm it waits for both and produces a combined output.

### Tests for User Story 13

- [ ] T080 [P] [US13] Integration test for a Merge node combining two parallel success branches in `backend/tests/integration/test_merge_node.py`

### Implementation for User Story 13

- [ ] T081 [US13] Implement Merge node config schema + execution function (`combine-object`/`concat-list` strategies, waits for all incoming success branches per LangGraph's native multi-predecessor join behavior) in `backend/app/graph/nodes/merge_node.py` (depends on T021)
- [ ] T082 [P] [US13] Implement Merge canvas node component in `frontend/src/canvas/nodes/MergeNode.tsx` (depends on T028)

**Checkpoint**: All 13 node types are implemented, connectable, and independently functional (SC-003).

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that span multiple user stories

- [ ] T083 [P] Implement the audit/log viewer UI (per-run node execution list including which output fired) in `frontend/src/audit/RunLog.tsx` (SC-007)
- [ ] T084 [P] Implement the Credential management UI in `frontend/src/credentials/CredentialManager.tsx` (depends on T016)
- [ ] T085 [P] Write `backend/tests/integration/test_quickstart_scenarios.py` scripting all 4 quickstart.md scenarios end-to-end as the CI acceptance gate
- [ ] T086 Run full quickstart.md validation manually against a `docker compose up` stack on a clean machine (SC-006)
- [ ] T087 Security hardening pass: grep the codebase and a sample run's `graph_json`/`input_json`/`output_json`/logs to confirm no raw credential value ever appears outside `backend/app/crypto.py`'s decrypt call site (Constitution VI)
- [ ] T088 [P] Write `README.md` covering `docker compose up` setup (mirrors quickstart.md Setup)
- [ ] T089 Responsiveness check: confirm chat sends a `status` acknowledgment within ~500ms of `start_workflow` even while an LLM node is mid-generation elsewhere (plan.md Performance Goals)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–15)**: All depend on Foundational completion.
  - US1 (P1) has no dependency on other stories — it's the MVP.
  - US2 depends on US1's Input node existing (extends it).
  - US3 is independent of US1/US2 beyond Foundational.
  - US4 is independent beyond Foundational; introduces the success/failure pattern other stories reuse.
  - US5 is independent beyond Foundational.
  - US6 is independent beyond Foundational; reuses the success/failure pattern from US4.
  - US7 depends on US4 existing (retries a failing node) — implemented and tested against the API node specifically, but the Retry node itself is generic to any success/failure node type.
  - US8 is independent beyond Foundational (versioning endpoints are mostly built in Foundational; this phase is about closing gaps + UI).
  - US9–US13 are each independent beyond Foundational and may be built in any order or in parallel.
- **Polish (Final Phase)**: Depends on all desired user stories being complete.

### Parallel Opportunities

- All Setup tasks marked [P] run in parallel.
- All Foundational tasks marked [P] run in parallel (respecting the explicit `depends on` notes above).
- Once Foundational completes, US3, US4, US5, US6, US9, US10, US11, US13 can all start in parallel (US2 needs US1 first; US7 needs US4 first; US12 needs Foundational's executor/compiler only).
- Within each story, the canvas node component task is `[P]` against its backend node-function task (different files, frontend/backend split).

---

## Parallel Example: User Story 1

```bash
# Backend node functions (different files, no cross-dependency):
Task: "Implement Input node config schema + execution function in backend/app/graph/nodes/input_node.py"
Task: "Implement LLM node config schema + execution function in backend/app/graph/nodes/llm_node.py"
Task: "Implement Response node config schema + execution function in backend/app/graph/nodes/response_node.py"

# Frontend, in parallel with the backend node functions above:
Task: "Implement Input/LLM/Response canvas node components in frontend/src/canvas/nodes/"
Task: "Implement ChatWindow.tsx and useChatSocket.ts in frontend/src/chat/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational — this is the largest phase (T008–T031) because the chat protocol, LangGraph compiler, and audit logging are all shared infrastructure every story depends on; there's no shortcut around it.
3. Complete Phase 3: User Story 1.
4. **STOP and VALIDATE**: run quickstart.md Scenario 1 end-to-end.
5. This is the MVP — a working prototype per the agreed v1 scope.

### Incremental Delivery

Recommended order beyond MVP, following spec.md's priorities and the dependency notes above: US2 (pause/resume) → US3 (Decision) → US4 (API + success/failure) → US5 (Variable) → US6 (Code sandbox) → US7 (Retry, needs US4) → US8 (versioning UI) → US9–US13 (Loop, Memory, Tool, Sub-workflow, Merge — any order, independent of each other). Each story is a demo-able increment; validate against its own Independent Test before moving on.

### Parallel Team Strategy

Once Foundational is done, a small team could split as: Developer A on US1→US2 (the chat/pause critical path), Developer B on US3+US4+US7 (Decision/API/Retry, since US7 needs US4), Developer C on US5+US6 (Variable/Code — both foundational-adjacent, low cross-dependency), remaining developers on US9–US13 in any order. All converge for the Final Phase.

---

## Notes

- [P] tasks touch different files with no unfinished dependency between them.
- [Story] labels trace every task back to a spec.md user story for scope accountability.
- The success/failure dual-output pattern (FR-017) is implemented generically once in the Foundational compiler (T021) — story-specific tasks for API/LLM/Code/Sub-workflow only add their own node function, not new routing logic.
- Commit after each task or logical group; stop at any Checkpoint to validate a story independently before continuing.
- Avoid: vague tasks, two tasks editing the same file marked `[P]` against each other, and cross-story dependencies that would break a story's independent testability.
