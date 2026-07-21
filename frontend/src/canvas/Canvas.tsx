import { useCallback, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { InputNode } from "./nodes/InputNode";
import { LlmNode } from "./nodes/LlmNode";
import { ResponseNode } from "./nodes/ResponseNode";
import { DecisionNode } from "./nodes/DecisionNode";
import { ApiNode } from "./nodes/ApiNode";
import { VariableNode } from "./nodes/VariableNode";
import { CodeNode } from "./nodes/CodeNode";
import { RetryNode } from "./nodes/RetryNode";
import { api, ApiError, type GraphJson } from "../api/client";

const nodeTypes = {
  input: InputNode,
  llm: LlmNode,
  response: ResponseNode,
  decision: DecisionNode,
  api: ApiNode,
  variable: VariableNode,
  code: CodeNode,
  retry: RetryNode,
};

let idCounter = 0;
function nextId(prefix: string): string {
  idCounter += 1;
  return `${prefix}-${idCounter}`;
}

const DEFAULT_CONFIG: Record<string, Record<string, unknown>> = {
  input: { prompt: "" },
  llm: { provider: "ollama", model: "llama3.2", prompt: "" },
  response: { content: "" },
  decision: { left: "{{previous}}", operator: "truthy", right: "" },
  api: {
    method: "GET",
    url: "",
    headers: {},
    body: "",
    credential_id: null,
    timeout_seconds: 60,
  },
  variable: { name: "" },
  code: { snippet: "", timeout_seconds: 60 },
  retry: { max_attempts: 3 },
};

interface CanvasProps {
  workflowId?: string;
  initialGraph?: GraphJson;
  onSaved?: (workflowId: string) => void;
}

export function Canvas({ workflowId, initialGraph, onSaved }: CanvasProps) {
  const toFlowNodes = (graph?: GraphJson): Node[] =>
    (graph?.nodes ?? []).map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: { name: n.name, config: n.config, onConfigChange: () => {} },
    }));
  const toFlowEdges = (graph?: GraphJson): Edge[] =>
    (graph?.edges ?? []).map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.source_port === "default" ? undefined : e.source_port,
    }));

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(
    toFlowNodes(initialGraph),
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(
    toFlowEdges(initialGraph),
  );
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges],
  );

  function addNode(type: keyof typeof DEFAULT_CONFIG) {
    const id = nextId(type);
    setNodes((nds) => [
      ...nds,
      {
        id,
        type,
        position: { x: 100 + nds.length * 40, y: 100 + nds.length * 40 },
        data: {
          name: type,
          config: { ...DEFAULT_CONFIG[type] },
          onConfigChange: (config: Record<string, unknown>) =>
            updateNodeConfig(id, config),
        },
      },
    ]);
  }

  function updateNodeConfig(id: string, config: Record<string, unknown>) {
    setNodes((nds) =>
      nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, config } } : n)),
    );
  }

  function toGraphJson(): GraphJson {
    return {
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type ?? "unknown",
        name: (n.data as { name?: string }).name ?? n.type ?? n.id,
        config: (n.data as { config?: Record<string, unknown> }).config ?? {},
        position: n.position,
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        source_port: e.sourceHandle ?? "default",
        target: e.target,
      })),
    };
  }

  async function handleSave() {
    setSaving(true);
    setErrors([]);
    try {
      const graph_json = toGraphJson();
      if (workflowId) {
        await api.saveVersion(workflowId, graph_json);
        onSaved?.(workflowId);
      } else {
        if (!name.trim()) {
          setErrors(["Workflow name is required."]);
          return;
        }
        const created = await api.createWorkflow(name.trim(), graph_json);
        onSaved?.(created.id);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        const detail = err.body as {
          detail?: { errors?: { field: string; issue: string }[] };
        };
        setErrors(
          (detail.detail?.errors ?? []).map((e) => `${e.field}: ${e.issue}`),
        );
      } else if (err instanceof ApiError && err.status === 409) {
        setErrors(["That workflow name is already in use."]);
      } else {
        setErrors(["Save failed — see console for details."]);
        console.error(err);
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="ng-toolbar">
        <button onClick={() => addNode("input")}>+ Input</button>
        <button onClick={() => addNode("llm")}>+ LLM</button>
        <button onClick={() => addNode("response")}>+ Response</button>
        <button onClick={() => addNode("decision")}>+ Decision</button>
        <button onClick={() => addNode("api")}>+ API</button>
        <button onClick={() => addNode("variable")}>+ Variable</button>
        <button onClick={() => addNode("code")}>+ Code</button>
        <button onClick={() => addNode("retry")}>+ Retry</button>
        {!workflowId && (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Workflow name (chat invocation name)"
          />
        )}
        <button onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : workflowId ? "Save new version" : "Save"}
        </button>
      </div>
      {errors.length > 0 && (
        <ul className="ng-errors">
          {errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      )}
      <div style={{ flex: 1 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          nodeTypes={nodeTypes}
          fitView
        >
          <Background />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  );
}
