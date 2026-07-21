# Contract: Chat WebSocket

`WS /ws/chat?session_id={uuid, optional}` — requires the same session cookie as the REST API (cookies are sent automatically on the WebSocket handshake by the browser). Omitting `session_id` starts a new `ChatSession`; passing one resumes an existing conversation's transcript (FR-011: reopening chat later still shows a paused run waiting).

## Message envelope (both directions)

```json
{ "type": "string", "payload": { ... } }
```

## Client → Server

- `{"type": "start_workflow", "payload": {"name": "string"}}` — user typed a workflow name. Server looks it up by `Workflow.name`; if not found, responds with `workflow_not_found` (Edge Case: misspelled/nonexistent name must produce a clear error, not silence). If the starting Input node(s) need parameters, server responds `input_request`, blocking the run from actually starting until parameters arrive.
- `{"type": "provide_input", "payload": {"run_id": "uuid", "value": "string"}}` — answers the most recent `input_request` for that run, whether it's the initial parameter prompt or a mid-flow pause (FR-007/FR-008 use the same message shape — from the chat's perspective, "flow needs a value" looks identical whether it's the very first prompt or node #40).

## Server → Client

- `{"type": "input_request", "payload": {"run_id": "uuid", "prompt": "string"}}` — chat should render this as a question and wait for `provide_input`. Sent both for initial-parameter collection (FR-007) and mid-flow pauses (FR-008); the client doesn't need to distinguish these cases, it just always shows the prompt and collects a reply.
- `{"type": "response", "payload": {"run_id": "uuid", "content": "..."}}` — a Response node fired (FR-009); `content` is whatever value reached it, rendered as the chat's answer.
- `{"type": "run_failed", "payload": {"run_id": "uuid", "message": "string"}}` — a failure output reached a dead end (nothing recoverable wired to it) or an unrecoverable system error occurred; shown as a chat error message, not a silent drop.
- `{"type": "workflow_not_found", "payload": {"name": "string"}}` — see `start_workflow` above.
- `{"type": "status", "payload": {"run_id": "uuid", "status": "running"}}` — lightweight acknowledgment sent immediately on `start_workflow` (before any node has necessarily finished) so the UI can show "working..." within the ~500ms responsiveness goal (plan.md Performance Goals) even while, say, an LLM node is still generating.

## Reconnection behavior

On WebSocket (re)connect with a known `session_id`, the server replays that `ChatSession`'s `ChatMessage` history as a batch (`{"type": "history", "payload": {"messages": [...]}}`) before resuming live message delivery, then — if any `Run` tied to this session is currently `paused` — immediately re-sends its `input_request` so a reconnecting client doesn't have to guess whether something is still waiting on them.
