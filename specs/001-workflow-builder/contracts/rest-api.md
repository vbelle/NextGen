# Contract: REST API

Base path `/api`. All endpoints except `/auth/login` require the session cookie set by `/auth/login` (research.md §8) — an unauthenticated request gets `401` and the frontend redirects to a password prompt.

## Auth

- `POST /auth/login` — body `{ "password": "string" }`. Sets session cookie on success. `401` on wrong password.
- `POST /auth/logout` — clears session cookie.

## Workflows

- `GET /workflows` — list all workflows (`id`, `name`, `active_version_id`, `created_at`; no `graph_json`, keep the list light).
- `POST /workflows` — create a new workflow. Body: `{ "name": "string", "graph_json": {...} }`. Runs FR-003 validation (contracts/graph-schema.md §Save-time validation) then creates `Workflow` + its first `WorkflowVersion` (version 1). `409` if `name` already exists (spec Clarifications: reject-at-save-time), body includes the conflicting workflow's `id` so the UI can offer "open the existing one" instead of just erroring.
- `GET /workflows/{id}` — workflow metadata + its active version's `graph_json`.
- `GET /workflows/{id}/versions` — list versions (`id`, `version_number`, `created_at`), no `graph_json` (keep list light; matches FR-005 "view version history").
- `GET /workflows/{id}/versions/{version_id}` — one version's full `graph_json`.
- `POST /workflows/{id}/versions` — save an edit. Body: `{ "graph_json": {...} }`. Validates (same as create), writes a new `WorkflowVersion` with `version_number = max + 1`, does **not** change `active_version_id` automatically — editing and saving a draft is separate from making it active, so a team member can save work-in-progress without affecting what chat currently runs. *(Design choice not explicit in the spec; flagged for confirmation — see Complexity/open-questions note in plan.md if this should instead auto-activate.)*
- `POST /workflows/{id}/activate/{version_id}` — sets `active_version_id`. This is the "revert to a prior version" action (FR-005 Acceptance Scenario 2) — reverting is just activating an older version, no special-cased revert endpoint needed.
- `DELETE /workflows/{id}` — only permitted if no `Run` references any of its versions (referential integrity for the audit log, Constitution VII); otherwise `409`.

## Runs & Audit

- `GET /runs/{id}` — status, `pending_prompt` if paused, `workflow_version_id`.
- `GET /runs/{id}/executions` — ordered `NodeExecution` rows for this run (the audit/log view, SC-007).
- `GET /runs/{id}/variables` — `RunVariable` rows for this run (SC-009 verification / debugging aid).
- `GET /runs?workflow_id=&status=` — filterable run history list.

## Credentials

- `GET /credentials` — list `{ id, name, created_at }` only — `encrypted_value` never serialized (data-model.md Credential validation rules).
- `POST /credentials` — body `{ "name": "string", "value": "string" }`; encrypts server-side before storing, request body is never logged (audit log FR-029 covers node executions, not credential management actions with raw secret material).
- `DELETE /credentials/{id}` — only permitted if no node config in any workflow's *active* version references it; a soft warning (not a hard block) is returned if older, inactive versions still reference it, since those are immutable history, not runnable.

## Error shape (all endpoints)

```json
{ "detail": "human-readable message", "errors": [ { "field": "...", "issue": "..." } ] }
```

`errors` is populated for the multi-violation validation case (graph-schema.md §Save-time validation); omitted (or empty) for single-cause errors like `401`/`404`.
