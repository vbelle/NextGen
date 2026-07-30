# Feature Specification: Agentic Workflow Builder (NextGen v1)

**Feature Branch**: `001-workflow-builder`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "A UI to build agentic workflows. From the UI you should be able to draw diagrams/nodes — an API node, an LLM node, a decision node, etc. Once drawn, save it and run it on a platform as a whole. Use LangChain and LangGraph at runtime. Self-hosted for a ~5-person team; users kick off saved flows by name through a built-in chat, and when a flow needs human input it asks for it in chat and resumes on reply."

## Clarifications

### Session 2026-07-11

- Q: Two different (not versions of the same) workflows both try to use the same chat-invocation name — what happens? → A: Reject the second save at save time with a clear error until it's renamed. No two workflows ever share a name.
- Q: A Merge node has multiple incoming branches and one fails — what should the Merge node do? → A: Superseded by a more general rule (see below): API, LLM, Code, and Sub-workflow nodes each expose separate **success** and **failure** outputs. Failure routing happens at the failing node itself (to a Retry node or directly to a Response node), not at the Merge node. A Merge node only ever combines completed "success" branches; a workflow that wants merge-time fallback values wires a failure output to a node that supplies a default before it reaches Merge.
- Q: How long should run/audit logs be kept? → A: Indefinitely in v1. No automatic expiry; retention/archival policy is future work.
- Q: Should LLM/API/Code nodes have an execution timeout? → A: Yes, configurable per node with a sane default (e.g. 60s). Input nodes remain the one exception — they wait indefinitely for a human. A timeout is treated as a failure and routes to that node's failure output, same as any other failure.
- Q: Ollama runs on one shared machine — what happens when 2+ people trigger LLM-using workflows concurrently? → A: LLM calls are serialized (queued, one at a time) against Ollama to avoid overloading a single local model server. Other node types (API, Code, etc.) may still execute concurrently across different runs.
- Q: Which node types get success/failure dual outputs? → A: API, LLM, Code, and Sub-workflow nodes — any node type that calls something that can fail (external service, model, sandboxed code, or an embedded workflow).
- Q: How should a failed node be retried? → A: A new **Retry** node type. A failure output wires into it; it manages its own internal attempt counter (no manual variable wiring needed), retries the originally-failed node up to a builder-configured max attempts, and once exhausted routes to a separate "give up" output the builder wires onward (typically to a Response node explaining the failure).
- Q: How should a value be saved and reused later in a run, independent of direct node-to-node wiring? → A: A new **Variable** node type. It accepts an input from any upstream node (success, failure, or any other output), stores it under a builder-assigned name unique within the workflow, and any later node's config fields can reference it via `{{variable_name}}` (Handlebars-style) interpolation — resolved at run time, readable from anywhere later in the same run regardless of direct graph connectivity.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build and run the core loop: Input → LLM → Response (Priority: P1)

A user drags an Input node, an LLM node, and a Response node onto the canvas, connects them in sequence, configures the LLM node's prompt to reference the Input node's value, and saves the workflow under a name. They then open the chat, type the workflow's name, get prompted for the Input value, and see the LLM's output appear as the chat response.

**Why this priority**: This is the entire point of the product distilled to its smallest useful shape. If this doesn't work, nothing else matters.

**Independent Test**: Build exactly this 3-node flow, save it, invoke it by name in chat, supply a value, and confirm the LLM's response is displayed.

**Acceptance Scenarios**:

1. **Given** a saved workflow named "echo-test" with Input → LLM → Response, **When** a user types the workflow name in chat, **Then** the chat asks for the Input node's value.
2. **Given** the chat is waiting for the Input value, **When** the user replies with a value, **Then** the LLM node runs using that value and the Response node's output is shown in chat.

---

### User Story 2 - Human-in-the-loop pause mid-flow (Priority: P2)

A workflow has an Input node placed *mid-graph* (not just at the start) — e.g., after an LLM drafts something, a second Input node asks the chat user to approve, edit, or reject it before the flow continues.

**Why this priority**: This is what makes it "agentic" rather than a static pipeline — the flow can stop and wait for a person, then continue with what they provided.

**Independent Test**: Build Input(start) → LLM → Input(mid-flow, "approve? y/n") → Decision → Response. Run it, confirm execution pauses at the mid-flow Input, confirm the user's reply determines which Decision branch fires.

**Acceptance Scenarios**:

1. **Given** a run has reached a mid-flow Input node, **When** the system pauses, **Then** the chat displays that node's configured question and no further nodes execute until answered.
2. **Given** the run is paused waiting on a mid-flow Input node, **When** the user replies in chat, **Then** execution resumes using that reply as the node's output, from exactly where it left off.
3. **Given** a run is paused, **When** the user closes and reopens the chat later, **Then** the paused run is still there waiting (state survives beyond a single chat session).

---

### User Story 3 - Decision node branches on prior output (Priority: P3)

A Decision node reads the output of one or more previous nodes in the same run, evaluates a true/false condition, and routes execution down exactly one of two branches, each of which can lead to its own Response node.

**Why this priority**: Conditional branching is core to "decision tree" behavior explicitly requested.

**Independent Test**: Build a flow where a Decision node checks whether an upstream API node's output field satisfies a condition, routing to Response A on true and Response B on false; verify the correct branch fires for both cases.

**Acceptance Scenarios**:

1. **Given** a Decision node configured to check an upstream field, **When** that field satisfies the condition, **Then** execution follows the "true" edge only.
2. **Given** the same Decision node, **When** the condition is not satisfied, **Then** execution follows the "false" edge only, and the "true" branch does not execute.

---

### User Story 4 - API node calls an external service, with success/failure routing (Priority: P4)

A user configures an API node with a method, URL, headers, and body; when the node executes, it makes the HTTP call and exposes the response to its **success** output on a 2xx response, or to its **failure** output on a timeout, non-2xx response, connection error, or exceeded execution timeout. The builder wires success to the happy path and wires failure to either a Response node (surface the error) or a Retry node (attempt recovery).

**Why this priority**: Real workflows need to reach outside the system; this was explicitly requested ("that could be an API"). Reliable handling of failure is not a nice-to-have here — it's the same priority as the call succeeding.

**Independent Test**: Configure an API node against a test HTTP endpoint. Confirm a successful call's response is available to nodes wired to its success output. Separately, point it at a failing/unreachable endpoint and confirm the failure output fires instead, with the success path not executing.

**Acceptance Scenarios**:

1. **Given** an API node configured with a valid endpoint, **When** the node executes and receives a 2xx response, **Then** its response (status, headers, body) is available to nodes connected to its success output, and its failure output does not fire.
2. **Given** an API node whose call fails (timeout, non-2xx, connection error) or exceeds its configured execution timeout, **When** the node executes, **Then** its failure output fires with error details available to whatever it's wired to, and its success output does not fire.

---

### User Story 5 - Variable node saves and reuses a value across the flow (Priority: P5)

A user places a Variable node after any node (e.g., an API node's success output), gives it a unique name (e.g. `customer_id`), and later — in a completely different, non-adjacent part of the graph — references `{{customer_id}}` inside an LLM prompt or another API node's URL.

**Why this priority**: Foundational plumbing other node types (Retry, Merge, later API/Code nodes) benefit from; needed early because later stories assume it exists.

**Independent Test**: Save a value early in a flow via a Variable node, then reference it via `{{name}}` in a node with no direct edge from the Variable node, and confirm the correct value resolves at run time.

**Acceptance Scenarios**:

1. **Given** a Variable node storing a value under a chosen name, **When** a later node's config contains `{{that_name}}`, **Then** it resolves to the stored value at run time, even without a direct edge between the two nodes.
2. **Given** a user tries to save a second Variable node using a name already used by another Variable node in the same workflow, **When** they attempt to save, **Then** the save is rejected with a clear "name already in use" error, consistent with workflow name collision handling.
3. **Given** a node references `{{some_name}}` where no Variable node with that name executed earlier in this particular run (e.g., it sits on a branch that never ran), **When** the referencing node executes, **Then** this is treated as that node's own failure condition rather than silently substituting an empty string.

---

### User Story 6 - Code node transforms data (sandboxed), with success/failure routing (Priority: P6)

A user writes a small Python snippet in a Code node that reads the outputs of connected upstream nodes (and/or `{{variables}}`) and returns a transformed value on its success output — e.g., reshaping an API response before it's used in an LLM prompt. Sandbox violations, exceptions, or timeouts route to its failure output instead.

**Why this priority**: Needed to glue nodes together when data shapes don't line up naturally; must be safe since it's shared by 5 people.

**Independent Test**: Configure a Code node that reshapes upstream JSON, confirm downstream nodes wired to its success output receive the transformed value; separately, confirm a snippet attempting a network call, filesystem access outside its scratch directory, or exceeding its time limit routes to its failure output with a clear error, rather than crashing the run.

**Acceptance Scenarios**:

1. **Given** a Code node with a valid transform snippet, **When** it executes, **Then** nodes wired to its success output receive its returned value.
2. **Given** a Code node attempting network access, out-of-scratch filesystem access, or exceeding its time/memory limit, **When** it executes, **Then** its failure output fires with a sandbox-violation or timeout error, and its success output does not fire.

---

### User Story 7 - Retry node recovers from a failure automatically (Priority: P7)

A user wires an API node's failure output into a Retry node configured for "max attempts: 3." On failure, the Retry node loops execution back to re-attempt the original API node. If it succeeds on attempt 2, the flow proceeds normally. If all 3 attempts fail, the Retry node's "give up" output fires, which the user has wired to a Response node explaining the failure.

**Why this priority**: Depends on API/Code nodes already having failure outputs (P4/P6); turns "a call might fail" from a dead end into recoverable behavior, which is core to reliable agentic workflows.

**Independent Test**: Point a Retry node (max attempts: 3) at a deliberately-always-failing API node; confirm it retries exactly 3 times (not more, not fewer) and then fires its "give up" output exactly once.

**Acceptance Scenarios**:

1. **Given** a Retry node configured for N max attempts wired to a failing node, **When** the wired node fails, **Then** the Retry node re-executes that node, up to N total attempts.
2. **Given** the wired node succeeds on any attempt within the limit, **When** that happens, **Then** the Retry node stops retrying and execution proceeds via the node's normal success output.
3. **Given** all N attempts fail, **When** the last attempt fails, **Then** the Retry node's "give up" output fires exactly once, and no further retries occur.

---

### User Story 8 - Save, version, and revert workflows (Priority: P8)

A user edits an existing saved workflow and saves again; the prior version remains accessible, viewable, and restorable.

**Why this priority**: Explicitly required ("versioning yes"); protects against accidental breakage of a working flow.

**Independent Test**: Save a workflow, edit and save it again, confirm both versions are listed with timestamps, revert to the first version, confirm running it reproduces the original behavior.

**Acceptance Scenarios**:

1. **Given** a saved workflow, **When** a user modifies and saves it again, **Then** a new version is created and the prior version remains retrievable (not overwritten).
2. **Given** a workflow with multiple versions, **When** a user selects an older version and restores it, **Then** it becomes the active version used by future chat invocations.

---

### User Story 9 - Loop node iterates over a collection (Priority: P9)

A Loop node takes a list/collection produced upstream and runs a defined sub-path once per item, making both per-item and aggregated results available downstream.

**Why this priority**: Needed for batch-style steps (e.g., "summarize each of these 5 documents").

**Independent Test**: Feed a 3-item list into a Loop node wrapping an LLM node, confirm the LLM runs 3 times (once per item) and the aggregated results are available to a downstream node.

**Acceptance Scenarios**:

1. **Given** a Loop node fed a list of N items, **When** it executes, **Then** its inner path runs exactly N times, once per item.
2. **Given** a Loop node has completed, **When** downstream nodes read its output, **Then** they receive the aggregated results of all N iterations.

---

### User Story 10 - Memory/Retrieval node grounds an LLM node (Priority: P10)

A Memory node queries a configured vector store for a given query and returns the top matches, typically feeding an LLM node's prompt (RAG-style).

**Why this priority**: Common agentic pattern; extends the LLM node's usefulness beyond its own context.

**Independent Test**: Configure a Memory node against a small test vector store, run a query through it, confirm the top-k results are passed into a connected LLM node's prompt.

**Acceptance Scenarios**:

1. **Given** a configured Memory node and a query from an upstream node, **When** it executes, **Then** it returns the top-matching stored items to downstream nodes.

---

### User Story 11 - Tool/function-calling node used by an LLM node (Priority: P11)

An LLM node is configured with access to one or more Tool nodes; the model can decide to invoke a tool mid-generation, the tool executes, and its result is returned to the model to continue reasoning.

**Why this priority**: Native LangChain/LangGraph function-calling pattern; core "agentic" behavior.

**Independent Test**: Configure an LLM node with one Tool node available (e.g., a simple calculator or lookup), prompt it with something requiring the tool, confirm the tool is invoked and its result reflected in the model's final output.

**Acceptance Scenarios**:

1. **Given** an LLM node with an available Tool node, **When** the model decides to call it, **Then** the Tool node executes and its result is returned to the model before the model produces its final output.

---

### User Story 12 - Sub-workflow node embeds another saved workflow, with success/failure routing (Priority: P12)

A saved workflow can be used as a single node inside another workflow, pinned to a specific version. Its success output fires if the embedded run completes normally; its failure output fires if the embedded run errors out unrecoverably.

**Why this priority**: Enables reuse/composition once several workflows exist; lower priority since it depends on other workflows already existing.

**Independent Test**: Save Workflow B, embed it as a Sub-workflow node inside Workflow A pinned to B's current version, run A, confirm B's full graph executes and its Response output is available via the Sub-workflow node's success output.

**Acceptance Scenarios**:

1. **Given** a Sub-workflow node pinned to a specific version of Workflow B, **When** the parent workflow runs and B completes normally, **Then** B's Response output becomes available on the Sub-workflow node's success output.
2. **Given** Workflow B has since been updated to a newer version, **When** the parent workflow runs, **Then** it still uses the pinned version, not the newer one, until a user explicitly repins it.
3. **Given** Workflow B's embedded run fails unrecoverably, **When** that happens, **Then** the Sub-workflow node's failure output fires, usable the same way as any other node's failure output (e.g., wired to Retry or Response).

---

### User Story 13 - Merge node combines parallel success branches (Priority: P13)

Two or more branches (e.g., two API calls fired in parallel) converge into a Merge node that combines their success outputs into a single value before continuing.

**Why this priority**: Needed once workflows branch and later need to recombine; lowest priority since it depends on multi-branch flows already existing.

**Independent Test**: Build two parallel branches (each ending in a node's success output) feeding one Merge node, confirm the flow waits for both to complete and produces a combined output.

**Acceptance Scenarios**:

1. **Given** a Merge node with multiple incoming success branches, **When** all required branches complete successfully, **Then** it produces a single combined output for downstream nodes.
2. **Given** one of the branches feeding a Merge node fails and its failure output is routed elsewhere (Retry/Response) rather than back toward the Merge node, **When** that happens, **Then** the Merge node simply never receives that branch and the run's behavior is governed by whatever the failure path does (e.g., the run ends via a Response node) — the Merge node itself does not need special partial-failure logic.

---

### Edge Cases

- What happens when a chat user types a workflow name that doesn't exist or is misspelled? (System should say so, not silently do nothing.)
- Can the same workflow be running more than once at the same time (same or different users)? Runs must not share state with each other.
- Does a paused, human-in-the-loop run ever expire, or can it wait forever? (Confirmed: no timeout in v1 — see Clarifications.)
- What happens when a Decision node's referenced upstream field or `{{variable}}` is missing or null?
- What happens if a Sub-workflow node's pinned version is later deleted?
- What happens if a user edits and saves a workflow while another run of an older version of that same workflow is still in progress? (The in-progress run keeps using the version it started with.)
- What happens when the credential-encryption key (env var/secret) is missing or wrong at startup?
- What happens if a Retry node's "give up" output is left unconnected? (Should be flagged at save-time validation, same as any other dangling failure path.)
- What happens if two Variable nodes in the same workflow are (mistakenly) given the same name? (Rejected at save time — see Clarifications/User Story 5.)
- What happens if `{{variable_name}}` is referenced but that Variable node never executed in the current run (e.g., it's on a branch that didn't run)? (Treated as a failure of the referencing node — see User Story 5, Acceptance Scenario 3 — not a silent empty-string substitution.)
- What happens if Ollama itself is unreachable when an LLM node executes? (Surfaces as that LLM node's failure output, same as any other failure — not a distinct system-level error class.)

## Requirements *(mandatory)*

### Functional Requirements

**Canvas / Builder**
- **FR-001**: Users MUST be able to create a workflow by placing nodes of all supported types (Input, LLM, Decision, API, Code, Loop, Memory/Retrieval, Tool, Sub-workflow, Merge, Response, Retry, Variable) on a canvas and connecting them with directed edges.
- **FR-002**: Users MUST be able to configure each node's type-specific parameters through a properties panel (e.g., LLM: provider, model, prompt referencing upstream node outputs and/or `{{variables}}`; Decision: condition against a named upstream field or variable; API: method/URL/headers/body/auth, each interpolable with `{{variables}}`; Code: Python snippet).
- **FR-003**: System MUST validate a workflow before it can be marked runnable: no dangling edges, each Decision node has exactly one "true" and one "false" outgoing edge, each API/LLM/Code/Sub-workflow node's failure output is connected to something (a Response node, a Retry node, or another node) rather than left unconnected, each Retry node's "give up" output is connected to something, each Variable node has a name unique within the workflow, and at least one path reaches a Response node.
- **FR-004**: Saving a workflow MUST create a new version rather than overwriting the previous one; saving a *new* workflow under a name already used by a different existing workflow MUST be rejected with a clear error rather than silently overwriting or auto-renaming.
- **FR-005**: Users MUST be able to view a workflow's version history and restore a prior version as the active one.

**Chat Runtime**
- **FR-006**: Users MUST be able to start a saved workflow from the built-in chat by name.
- **FR-007**: If the workflow's starting Input node(s) require parameters, the chat MUST prompt for each before execution begins.
- **FR-008**: When execution reaches an Input node mid-flow, the system MUST pause the run, present the node's configured question in chat, and resume using the user's reply as that node's output.
- **FR-009**: When execution reaches a Response node, the system MUST display the value it received in chat.
- **FR-010**: A workflow MAY have more than one Response node; whichever is reached in a given run is what's shown.
- **FR-011**: Paused runs MUST persist independently of any single chat connection/session (closing and reopening chat does not lose a paused run).

**Node Execution Semantics — Core**
- **FR-012**: The LLM node MUST call a model through a provider-agnostic interface; Ollama MUST be the default supported provider; adding another provider MUST NOT require changing existing workflow definitions, only provider configuration.
- **FR-013**: The Decision node MUST evaluate a condition against the output(s) of specified prior node(s) or `{{variables}}` in the same run and route to exactly one of two branches (true/false).
- **FR-014**: The Loop node MUST execute a defined sub-path once per item in an upstream collection and expose both per-item and aggregated results downstream.
- **FR-015**: The Memory/Retrieval node MUST query a configured vector store and return top-matching results to downstream nodes.
- **FR-016**: The Tool node MUST expose a callable function that an LLM node can invoke via function-calling and MUST return its result to the invoking LLM node.

**Node Execution Semantics — Success/Failure Routing**
- **FR-017**: API, LLM, Code, and Sub-workflow nodes MUST each expose two distinct outputs — success and failure — rather than a single generic output.
- **FR-018**: API, LLM, and Code nodes MUST support a configurable execution timeout with a sane default (e.g. 60 seconds); exceeding it MUST be treated as a failure and routed to that node's failure output, same as any other failure mode for that node type.
- **FR-019**: The Retry node MUST accept a failure-output connection, internally track its own attempt counter (scoped to that Retry node within the current run — no manual variable wiring required), re-execute the originally-failed node up to a builder-configured maximum attempts, and route to a distinct "give up" output once that maximum is exhausted.
- **FR-020**: The Merge node MUST combine outputs from multiple incoming *success* branches into one downstream value once all required branches complete; it has no special-cased partial-failure behavior of its own, since failure routing happens upstream at the failing node.
- **FR-021**: The Sub-workflow node MUST execute a previously saved workflow pinned to a specific version, expose that run's Response output on its own success output if the embedded run completes normally, and expose an error on its own failure output if the embedded run fails unrecoverably.

**Variables & Templating**
- **FR-022**: The Variable node MUST accept an input value from any upstream node (success output, failure output, or any other output) and store it under a builder-assigned name that is unique within the workflow.
- **FR-023**: Any node configuration field that accepts text (LLM prompts, API URL/headers/body, Decision conditions, Response content) MUST support `{{variable_name}}` (Handlebars-style) interpolation, resolved at run time using values set by Variable nodes earlier in that same run — readable regardless of direct graph connectivity between the Variable node and the referencing node.
- **FR-024**: Variable values MUST be stored as their native structured type (string, number, object, or list) — interpolated as a string when used inside a text field, but available as a structured value to nodes (e.g. Code) that consume it programmatically.
- **FR-025**: If a node references `{{variable_name}}` for a variable that was never set during the current run (e.g., it lives on a branch that never executed), this MUST be treated as a failure condition of the referencing node, not a silent empty-string substitution.

**Concurrency**
- **FR-026**: System MUST serialize LLM node calls to Ollama (process one at a time across all concurrent runs) to avoid overloading a single shared local model server; other node types (API, Code, etc.) MAY execute concurrently across different runs.

**Security & Data**
- **FR-027**: System MUST require a shared application password before any builder or chat functionality is reachable.
- **FR-028**: System MUST encrypt stored credentials at rest and MUST NOT persist raw credential values inside workflow definitions or version history.
- **FR-029**: System MUST log, per run: workflow name/version, start/end time, every value entered at an Input node, every node's input/output (including which output — success or failure — fired), and every Retry node's attempt count — retrievable later through an in-app log/audit view. Logs are retained indefinitely in v1; no automatic expiry.
- **FR-030**: The Code node's sandbox MUST block outbound network access and filesystem access outside an explicitly designated scratch area, by default.

**Deployment**
- **FR-031**: System MUST be deployable via Docker/docker-compose as a self-hosted service.
- **FR-032**: System MUST persist workflow definitions, versions, credentials, variables, and run/audit logs such that they survive container restarts (via a mounted volume).

### Key Entities *(include if feature involves data)*

- **Workflow**: A named, versioned graph. Has an ordered set of Versions and a unique invocation name used in chat; name uniqueness is enforced across all workflows at save time.
- **Workflow Version**: An immutable snapshot of a workflow's nodes, edges, and configuration at the time it was saved, with a timestamp.
- **Node**: A typed unit within a Workflow Version. Types: Input, LLM, Decision, API, Code, Loop, Memory/Retrieval, Tool, Sub-workflow, Merge, Response, Retry, Variable. API/LLM/Code/Sub-workflow nodes carry two distinct output ports (success, failure); Decision carries two (true, false); Retry carries two (retry-target, give-up).
- **Edge**: A directed connection between two node outputs and a downstream node; edges out of a Decision node carry a true/false label, edges out of API/LLM/Code/Sub-workflow nodes carry a success/failure label, edges out of Retry carry a retry/give-up label.
- **Run**: One execution of a specific Workflow Version. Has a status (running, paused, completed, failed), start/end time, an ordered sequence of Node Executions, and the current set of Variable values live for that run.
- **Node Execution**: A record of one node's input, output, timing, status (including which output fired: success/failure/true/false/retry/give-up), and — for Retry nodes — current attempt count, within a Run.
- **Variable**: A named, run-scoped value set by a Variable node during a Run and readable via `{{name}}` by any later node in that same Run. Names are unique within a workflow.
- **Credential**: An encrypted, named secret referenced by node configuration by name/ID, never embedded directly in a workflow.
- **Chat Session**: The conversational channel through which a user starts Runs and answers Input-node prompts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can build, save, and successfully run the P1 core loop (Input → LLM → Response) end-to-end via chat in one sitting, with no code editing.
- **SC-002**: In testing, a paused human-in-the-loop run resumes using the chat-supplied value correctly in 100% of attempts — no lost or mismatched state.
- **SC-003**: All 13 node types can be placed, configured, connected, saved, and successfully executed at least once in an acceptance-test workflow.
- **SC-004**: Reverting a workflow to a previous version and running it reproduces that version's recorded behavior exactly, with no drift from the current draft.
- **SC-005**: A deliberately malicious Code node snippet (attempting network access or reading outside its scratch directory) is blocked every time, reporting a clear sandbox-violation error rather than succeeding or affecting the host.
- **SC-006**: The full application (builder + chat runtime) starts from a single `docker compose up` on a clean machine, with only Ollama and env-configured secrets as external prerequisites.
- **SC-007**: Every run's node-by-node input/output (including which output fired) is viewable in an in-app audit/log view without external tooling.
- **SC-008**: A Retry node configured for max 3 attempts against a deliberately-always-failing API node retries exactly 3 times, then fires its "give up" output exactly once — never looping indefinitely.
- **SC-009**: A value saved by a Variable node early in a run is correctly readable via `{{name}}` by an unrelated (non-adjacent) node later in that same run, with no direct edge between them.

## Assumptions

- Ollama runs as its own reachable service (co-located in the same docker-compose stack or at a configured URL); NextGen does not bundle model weights itself.
- "Simple shared access" (one shared application password) is an accepted, deliberate v1 tradeoff — not an absence of security. Individual accounts/SSO are explicitly future work (see constitution).
- The team is ~5 trusted people. Concurrent runs by different people must not share execution state with each other, even without per-user login. LLM calls are serialized against Ollama; other node types may run concurrently.
- Decision node conditions are simple comparisons (equals, contains, greater/less-than, boolean truthy) against a named upstream field or `{{variable}}` — not a general scripting language; that's what the Code node is for.
- No external chat platform (Slack/Teams) integration in v1 — chat is a page within NextGen itself, built with room to add a Slack adapter later without rework.
- Human-in-the-loop pauses (Input nodes) have no automatic timeout in v1; a run can remain paused indefinitely at an Input node. This is distinct from the execution timeout on LLM/API/Code nodes (FR-018), which does apply.
- Run/audit logs are retained indefinitely in v1; no automatic expiry or archival policy yet.
