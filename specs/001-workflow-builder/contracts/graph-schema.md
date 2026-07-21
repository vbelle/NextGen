# Contract: Workflow Graph JSON Schema

This is the payload the canvas saves and the LangGraph compiler consumes (`WorkflowVersion.graph_json`). It is the concrete expression of Constitution IV ("Visual Graph Is the Source of Truth").

## Top-level shape

```json
{
  "nodes": [ /* Node[] */ ],
  "edges": [ /* Edge[] */ ]
}
```

## Node

```json
{
  "id": "string, unique within this graph",
  "type": "input | llm | decision | api | code | loop | memory | tool | subworkflow | merge | response | retry | variable",
  "name": "string, human-readable label shown on canvas",
  "config": { /* type-specific, see below */ },
  "position": { "x": 0, "y": 0 }
}
```

### Config by node type

- **input**: `{ "prompt": "string, question shown in chat", "required": true }`
- **llm**: `{ "provider": "ollama", "model": "string", "prompt": "string, supports {{variables}} and direct upstream refs", "timeout_seconds": 60 }`
- **decision**: `{ "left": "string, upstream field or {{variable}} reference", "operator": "equals | contains | gt | lt | truthy", "right": "string, comparison value (omitted for truthy)" }`
- **api**: `{ "method": "GET | POST | PUT | PATCH | DELETE", "url": "string, supports {{variables}}", "headers": {"...": "..."}, "body": "string, supports {{variables}}", "credential_id": "uuid, nullable", "timeout_seconds": 60 }`
- **code**: `{ "snippet": "string, Python", "timeout_seconds": 60 }`
- **loop**: `{ "collection_ref": "string, upstream field or {{variable}} resolving to a list", "body_start_node_id": "string, first node of the inner sub-path" }`
- **memory**: `{ "vector_store_ref": "string, configured store name", "query": "string, supports {{variables}}", "top_k": 5 }`
- **tool**: `{ "function_name": "string", "description": "string, shown to the LLM for function-calling", "implementation_ref": "string, maps to a registered backend tool" }`
- **subworkflow**: `{ "workflow_id": "uuid", "pinned_version_id": "uuid" }`
- **merge**: `{ "strategy": "combine-object | concat-list" }`
- **response**: `{ "content": "string, supports {{variables}} and direct upstream refs" }`
- **retry**: `{ "max_attempts": 3 }`
- **variable**: `{ "name": "string, unique within this graph" }`

## Edge

```json
{
  "id": "string, unique within this graph",
  "source": "node id",
  "source_port": "default | success | failure | true | false | retry | give-up",
  "target": "node id"
}
```

`source_port` MUST match the source node's type:
- `decision` → `true` or `false` (exactly one edge of each required)
- `api`, `llm`, `code`, `subworkflow` → `success` or `failure` (both required to be connected — FR-003)
- `retry` → `retry` (loops back to the ID of the node whose failure fed this Retry node) or `give-up` (both required to be connected)
- all other types → `default`

## Save-time validation (FR-003), enforced server-side before a WorkflowVersion is written

1. Every edge's `source`/`target` reference an existing node ID (no dangling edges).
2. Every `decision` node has exactly one outgoing `true` edge and one outgoing `false` edge.
3. Every `api`/`llm`/`code`/`subworkflow` node has both a `success` and a `failure` outgoing edge connected to something.
4. Every `retry` node has both a `retry` and a `give-up` outgoing edge connected to something.
5. Every `variable` node's `config.name` is unique among all `variable` nodes in this graph.
6. At least one `response` node is reachable from the `input` start node(s).
7. Exactly the node type's allowed `source_port` values are used (no `success` edge out of a `decision` node, etc.).

A save request failing any check is rejected with a 422 listing every violation found (not just the first), so the canvas can highlight all problem nodes/edges at once.
