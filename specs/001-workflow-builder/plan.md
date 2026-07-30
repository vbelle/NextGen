# Implementation Plan: Agentic Workflow Builder (NextGen v1)

**Branch**: `001-workflow-builder` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-workflow-builder/spec.md`

## Summary

Build a self-hosted, small-team (~5 person) web app with two surfaces: a React Flow canvas for visually authoring agentic workflows out of 13 node types (Input, LLM, Decision, API, Code, Loop, Memory/Retrieval, Tool, Sub-workflow, Merge, Response, Retry, Variable), and a built-in chat for invoking saved workflows by name and answering human-in-the-loop prompts. Saved graphs compile into LangGraph `StateGraph`s at run time; LangGraph's native `interrupt()`/checkpointing handles pausing and resuming, success/failure dual outputs map to LangGraph conditional edges, and Retry loops are ordinary graph cycles bounded by a per-node attempt counter carried in graph state. FastAPI serves both the REST API (workflow CRUD/versioning, credentials, audit logs) and a WebSocket chat endpoint; SQLite persists everything (workflows, versions, runs, node executions, variables, encrypted credentials); Ollama is the default LLM provider, called through a provider-agnostic LangChain chat-model wrapper with a process-wide semaphore serializing calls.

## Technical Context

**Language/Version**: Python 3.11 (backend runtime — the LangGraph/LangChain ecosystem's primary, most mature target; the local sandbox for this project only had 3.10 available and required a manual apt install of 3.11, so the Dockerfile must pin `python:3.11-slim` explicitly rather than relying on a base image default), TypeScript 5.x + React 18 (frontend)

**Primary Dependencies**: FastAPI, Uvicorn, LangChain, LangGraph (with `langgraph-checkpoint-sqlite`), SQLModel (SQLAlchemy + Pydantic), `cryptography` (Fernet), `RestrictedPython` (Code node sandboxing), `httpx` (API node + Ollama calls); React, `@xyflow/react` (React Flow), Vite, native WebSocket client (no extra chat SDK needed for v1)

**Storage**: SQLite, single file on a mounted Docker volume. LangGraph's own checkpointer also targets the same SQLite file (via `AsyncSqliteSaver`) so run/pause state and the app's own tables live in one place, one volume, one backup target.

**Testing**: pytest + `httpx.AsyncClient` (backend contract/integration tests), Vitest + React Testing Library (frontend component tests), a scripted end-to-end smoke test driving the P1 core loop through the real WebSocket chat endpoint (see quickstart.md)

**Target Platform**: Linux server via Docker Compose (self-hosted), accessed by the team through a browser on the local network/VPN

**Project Type**: web (frontend + backend)

**Performance Goals**: Not a scale-driven system — success is "responsive for 5 people," not throughput. Chat should acknowledge a typed command within ~500ms even while an LLM node is mid-generation elsewhere (non-blocking runs, per Constitution III). No hard latency target on LLM node completion itself since that's bounded by Ollama/hardware, not NextGen.

**Constraints**: LLM calls to Ollama are serialized process-wide (one at a time) per the spec's concurrency clarification (FR-026); Code node executions are resource-limited (CPU/wall-clock/memory) and network-isolated (FR-030); SQLite's single-writer model is an accepted constraint at this scale, not a bottleneck to engineer around.

**Scale/Scope**: ~5 users, expected tens of saved workflows, hundreds of runs, indefinite log retention in v1 (FR-029) — SQLite comfortably covers this for years before it would need reconsideration.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (see bottom of this section).*

| Principle | Check | Status |
|---|---|---|
| I. Self-Hosted, Small-Team First | Single Docker Compose stack, no multi-tenant isolation, one shared password gate | PASS |
| II. Chat Is the Runtime Interface | WebSocket chat endpoint is the only way to start/interact with a run; canvas never exposes a "Run" button that bypasses chat | PASS |
| III. LangGraph as the Execution Engine (NON-NEGOTIABLE) | All execution compiles to and runs through a LangGraph `StateGraph`; runs execute as background asyncio tasks, never inline in an HTTP request/response cycle | PASS |
| IV. Visual Graph Is the Source of Truth | `graph_json` (nodes+edges+config) saved by the canvas is the only input to the LangGraph compiler; no separate "workflow code" authoring path exists | PASS |
| V. Provider-Agnostic Model Layer | LLM node calls go through a single `ModelProvider` interface; Ollama is the only concrete implementation shipped in v1, but adding another means adding a class, not touching workflow schemas | PASS |
| VI. Sandboxed Execution, Encrypted Secrets (NON-NEGOTIABLE) | Code node runs under `RestrictedPython` + subprocess resource limits + no network; credentials encrypted at rest via Fernet, referenced by ID only | PASS |
| VII. Every Run Is Audited | Every node execution (including which output port fired) is written to `node_executions` before the graph proceeds to the next node | PASS |

**Initial gate result**: PASS, no violations to justify. (Re-checked after Phase 1 design below — still PASS; see end of Complexity Tracking.)

## Project Structure

### Documentation (this feature)

```text
specs/001-workflow-builder/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── rest-api.md
│   ├── chat-websocket.md
│   └── graph-schema.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                  # FastAPI app, password-gate middleware, router mounting
│   ├── auth.py                  # Shared-password session middleware
│   ├── db.py                    # SQLModel engine/session setup (single SQLite file)
│   ├── models/                  # SQLModel table definitions
│   │   ├── workflow.py          # Workflow, WorkflowVersion
│   │   ├── run.py                # Run, NodeExecution
│   │   ├── variable.py          # RunVariable
│   │   └── credential.py        # Credential (encrypted)
│   ├── graph/                   # LangGraph compilation layer
│   │   ├── schema.py            # Pydantic node/edge config schemas (mirrors contracts/graph-schema.md)
│   │   ├── compiler.py          # graph_json -> LangGraph StateGraph
│   │   ├── state.py             # Shared GraphState TypedDict (variables, node_outputs, retry_counts, ...)
│   │   └── nodes/                # One module per node type's execution function
│   │       ├── input_node.py
│   │       ├── llm_node.py
│   │       ├── decision_node.py
│   │       ├── api_node.py
│   │       ├── code_node.py
│   │       ├── loop_node.py
│   │       ├── memory_node.py
│   │       ├── tool_node.py
│   │       ├── subworkflow_node.py
│   │       ├── merge_node.py
│   │       ├── response_node.py
│   │       ├── retry_node.py
│   │       └── variable_node.py
│   ├── providers/               # Provider-agnostic LLM layer (Constitution V)
│   │   ├── base.py
│   │   └── ollama_provider.py
│   ├── sandbox/                  # Code node sandboxing (Constitution VI)
│   │   └── run_snippet.py
│   ├── runtime/                  # Run orchestration
│   │   ├── executor.py           # Background asyncio task per run, drives graph.invoke/resume
│   │   ├── ollama_semaphore.py   # Process-wide serialization of LLM calls (FR-026)
│   │   └── audit.py              # Writes NodeExecution rows as the graph executes
│   ├── api/                      # REST routers (see contracts/rest-api.md)
│   │   ├── workflows.py
│   │   ├── runs.py
│   │   └── credentials.py
│   └── chat/
│       └── websocket.py          # /ws/chat handler (see contracts/chat-websocket.md)
└── tests/
    ├── contract/                 # One test file per contracts/*.md
    ├── integration/              # Full workflow build -> save -> run -> chat scenarios (per spec user stories)
    └── unit/                     # Node compiler, sandbox, provider, crypto unit tests

frontend/
├── src/
│   ├── canvas/                   # React Flow builder
│   │   ├── Canvas.tsx
│   │   ├── nodes/                 # One custom node component per type, matching backend node modules
│   │   └── validation.ts         # Client-side mirror of FR-003 save-time checks (fast feedback)
│   ├── chat/                     # Chat runtime UI
│   │   ├── ChatWindow.tsx
│   │   └── useChatSocket.ts
│   ├── workflows/                 # Workflow list, version history/revert UI
│   ├── audit/                     # Run/log viewer (SC-007)
│   └── api/                       # Typed REST + WebSocket client
└── tests/

docker-compose.yml                 # app (backend + built frontend static files) + ollama
Dockerfile                         # backend build, pinned python:3.11-slim
```

**Structure Decision**: Web application split (`backend/` + `frontend/`), matching Option 2 of the template. A single `app` container serves both the FastAPI API/WebSocket and the built frontend static assets (simplest Compose topology for a 5-person self-hosted deploy — avoids a separate nginx/reverse-proxy container as a v1 requirement); `ollama` is the second Compose service, with its URL overridable via env var if the team points at an Ollama instance running elsewhere.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*

**Post-Phase 1 re-check**: After completing data-model.md and the contracts, the design still routes every execution path through LangGraph (III), keeps `graph_json` as the sole workflow authoring surface (IV), isolates the Ollama call behind one provider class plus one semaphore (V), and sandboxes the Code node before any output reaches `node_executions` (VI, VII). No new violations introduced by the detailed design. **Gate result: PASS.**
