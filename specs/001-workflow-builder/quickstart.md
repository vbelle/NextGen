# Quickstart: Validating the Agentic Workflow Builder

This is a runnable validation guide, not a design document — it proves the feature works end-to-end (SC-001, SC-006) and gives a repeatable smoke test. Implementation code lives in tasks.md/the actual source tree, not here.

## Prerequisites

- Docker + Docker Compose installed on the host.
- Ollama reachable — either let Compose start the bundled `ollama` service, or set `OLLAMA_BASE_URL` to point at one already running on the network.
- At least one model pulled in Ollama (e.g. `ollama pull llama3.2`) — the bundled service starts empty; pulling a model is a one-time manual step, not automated by Compose (models are large; auto-pulling on every `up` would be a poor default).

## Setup

```bash
cp .env.example .env
# edit .env: set NEXTGEN_APP_PASSWORD and NEXTGEN_CREDENTIAL_KEY
# generate a credential key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

docker compose up -d
docker compose exec ollama ollama pull llama3.2   # first run only
```

Expected: `docker compose ps` shows `app` and `ollama` both `running`/`healthy`. Open `http://localhost:8000` (or the configured port) — the shared password prompt appears (SC-006: this is the *only* setup beyond Ollama + secrets).

## Validation Scenario 1 — Core loop (SC-001, User Story 1)

1. Log in with `NEXTGEN_APP_PASSWORD`.
2. In the builder, create three nodes: **Input** (`prompt`: "What's your name?"), **LLM** (`prompt`: `"Say hello to {{input_value}}"` — or reference the Input node's direct output per graph-schema.md), **Response** (`content`: direct reference to the LLM node's success output).
3. Connect: Input → LLM (default port) → LLM success output → Response.
4. Save as workflow name `hello-test`. Expected: save succeeds (all FR-003 checks pass — LLM has both success/failure wired... see note below).

   **Note**: this minimal example doesn't wire the LLM node's `failure` output anywhere. Per graph-schema.md's save-time validation, that's actually a required connection. For this quickstart, wire LLM's `failure` output directly to a second Response node with `content`: `"Something went wrong."` — this exercises FR-017 in the same walkthrough at no extra cost.
5. Open chat, type `hello-test`.
6. Expected: chat sends `input_request` with "What's your name?"; reply e.g. `Ada`; expected: chat sends `response` with LLM-generated text greeting Ada, within a few seconds (bounded by local Ollama generation speed, not the app).

## Validation Scenario 2 — Human-in-the-loop pause survives reconnect (SC-002, User Story 2)

1. Extend `hello-test` (save as a new version) by inserting a mid-flow Input node ("Approve this greeting? yes/no") between the LLM node's success output and Response.
2. Activate the new version. Invoke `hello-test` in chat, answer the name prompt.
3. Expected: chat now pauses again with "Approve this greeting? yes/no" — **close the browser tab** before answering.
4. Reopen chat (same `session_id` if the client persisted it, or check `GET /runs?status=paused`). Expected: the pending prompt is still there (FR-011) — reply `yes`.
5. Expected: `response` message arrives, `GET /runs/{id}/executions` shows every node including the two Input pauses, in order.

## Validation Scenario 3 — Retry recovers from failure (SC-008, User Story 7)

1. Build: API node pointed at an intentionally-invalid URL (e.g. `http://localhost:1/does-not-exist`) → its `failure` output → Retry node (`max_attempts: 3`) whose `retry` output loops back to the same API node, and whose `give-up` output → Response (`content`: "Failed after 3 attempts").
2. Save, activate, invoke via chat.
3. Expected: `GET /runs/{id}/executions` shows exactly 3 `NodeExecution` rows for the API node (each `output_port: failure`, `attempt_count` 1/2/3 on the corresponding Retry rows), then the `give-up` path, then the Response firing with the expected message — never a 4th attempt.

## Validation Scenario 4 — Code node sandbox (SC-005)

1. Build a Code node with a snippet attempting `import socket; socket.socket()`.
2. Wire its `failure` output to a Response node.
3. Invoke via chat.
4. Expected: `response` message shows a sandbox-violation error (not the run hanging, crashing the container, or silently succeeding); `docker compose logs app` shows no evidence the socket call actually executed.

## Automated smoke test

`backend/tests/integration/test_quickstart_scenarios.py` scripts Scenarios 1–4 above against a real (test-configured) Ollama and the app's own WebSocket endpoint using `httpx.AsyncClient`'s WebSocket support, run in CI as the acceptance gate for this feature before `/speckit-implement` is considered done for a given task.
