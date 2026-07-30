# NextGen Constitution

## Core Principles

### I. Self-Hosted, Small-Team First
NextGen is built for a self-hosted deployment (Docker) serving a small team (~5 people), not a multi-tenant SaaS. Every design decision defaults to "good enough for 5 trusted users behind a shared access gate," not internet-scale or public multi-tenancy. Multi-tenant isolation, per-user accounts, and public signup are explicitly out of scope unless a future amendment adds them.

### II. Chat Is the Runtime Interface
Workflows are invoked and interacted with through the built-in web chat — not a separate "click Run and wait" screen. A user starts a flow by name in chat, optionally supplying initial parameters; if the flow needs a value mid-run, the chat asks for it and the user's reply resumes execution. The canvas is for *building* workflows; chat is for *running* them.

### III. LangGraph as the Execution Engine (NON-NEGOTIABLE)
All workflow execution runs on LangGraph's stateful graph engine so that pausing (human-in-the-loop), checkpointing, and resume-from-interrupt are native capabilities, not bolted on. Every run is asynchronous/background by construction — there is no synchronous, blocking "run and wait in the HTTP request" path, because any node may pause indefinitely for human input.

### IV. Visual Graph Is the Source of Truth
The React Flow canvas is the only supported way to author a workflow. The saved graph (nodes + edges + config) is the canonical representation and is compiled into a LangGraph graph at run time. There is no hand-written workflow code path that bypasses the canvas — if it can't be expressed as nodes and edges, it isn't a v1 feature.

### V. Provider-Agnostic Model Layer
LLM nodes talk to models through a swappable provider abstraction. Ollama (local models) is the default and first-supported provider. Adding another provider (Gemini, OpenAI, Claude, etc.) must be a configuration change, never a change to existing workflow definitions or node schemas.

### VI. Sandboxed Execution, Encrypted Secrets (NON-NEGOTIABLE)
The Code node executes arbitrary Python and MUST run sandboxed: no filesystem or network access by default, and enforced CPU/time/memory limits. Credentials (API keys, tokens) are never stored in workflow JSON or version history; they are encrypted at rest and referenced by name/ID. This principle is non-negotiable because the tool is shared by multiple people and executes arbitrary code.

### VII. Every Run Is Audited
Every flow invocation, every value a user enters at an Input node, and every node's input/output within a run is logged and retrievable per run. With shared access instead of individual accounts, the audit log is the primary accountability mechanism — it must record what ran, what was entered, and what came out, even if it can't always attribute "who" beyond a session/name field.

## Technology & Security Constraints

- **Backend**: Python + FastAPI. **Workflow runtime**: LangChain + LangGraph. **Frontend**: React + React Flow. **Storage**: SQLite (workflow definitions with version history, run/audit logs, encrypted credentials). **Deployment**: Docker / docker-compose, self-hosted.
- **Default LLM provider**: Ollama (local). Provider abstraction must support adding Gemini or others without workflow migration.
- **Code node sandbox**: isolated subprocess or container per execution; no network/filesystem access unless explicitly granted; hard resource and wall-clock limits.
- **Access control (v1)**: a single shared application password gates both the builder UI and the chat runtime. This is a conscious v1 tradeoff, not a security absence — individual accounts/SSO are a future amendment, not silently skipped.
- **Credential storage**: encrypted at rest (symmetric encryption, key supplied via environment variable / Docker secret at deploy time), never embedded in workflow definitions.
- **Decision nodes**: binary (true/false) only in v1, evaluated against outputs of prior node(s) in the same run. Multi-way branching is achieved by chaining decision nodes, not by a native N-way branch node.
- **Response node**: terminal node; any non-conditional node may connect to it; whatever value reaches it is what's shown back to the user in chat. A workflow may have more than one Response node (different branches may each terminate independently).
- **Sub-workflows**: when Workflow A embeds Workflow B as a node, it pins to a specific saved version of B for reproducibility; updating to a newer version of B is a manual, explicit action.
- **Success/failure routing**: API, LLM, Code, and Sub-workflow nodes each expose distinct success and failure outputs (not one generic output); a failure output must be routed to either a Retry node or a Response node. Execution timeouts on these node types are treated as failures.
- **Retry node**: manages its own internal attempt counter (no manual variable wiring); retries the node whose failure feeds it up to a configured max, then fires a separate "give up" output.
- **Variable node + templating**: a named, run-scoped value store; any later node can reference a stored value via `{{variable_name}}` (Handlebars-style) interpolation regardless of direct graph connectivity. Variable and workflow names are both validated unique at save time.

## Development Workflow

NextGen is built via Spec-Driven Development using Spec Kit: `/speckit-constitution` (this document) → `/speckit-specify` (feature spec, WHAT/WHY) → `/speckit-clarify` (de-risk ambiguity) → `/speckit-plan` (technical HOW) → `/speckit-tasks` (actionable breakdown) → `/speckit-implement`. A feature's spec.md is reviewed and confirmed by the project owner before `/speckit-plan` begins. Given the v1 node set is large (13 node types), `/speckit-tasks` is expected to sequence delivery (e.g., core loop first: Input → LLM → Response, before Loop/Sub-workflow/Memory nodes) rather than requiring all nodes simultaneously.

## Governance

This constitution supersedes ad hoc technical choices. Any deviation (e.g., adding a synchronous run path, storing a raw credential in a workflow file, or shipping the Code node unsandboxed) requires an explicit amendment to this document with rationale, not a silent exception. Amendments are recorded by bumping the version below and updating "Last Amended."

**Version**: 1.0.0 | **Ratified**: 2026-07-10 | **Last Amended**: 2026-07-10
