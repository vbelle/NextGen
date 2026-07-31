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
import { LoopNode } from "./nodes/LoopNode";
import { MemoryNode } from "./nodes/MemoryNode";
import { ToolNode } from "./nodes/ToolNode";
import { SubworkflowNode } from "./nodes/SubworkflowNode";
import { MergeNode } from "./nodes/MergeNode";
import { VersionHistory } from "../workflows/VersionHistory";
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
  loop: LoopNode,
  memory: MemoryNode,
  tool: ToolNode,
  subworkflow: SubworkflowNode,
  merge: MergeNode,
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
  loop: { collection_ref: "{{previous}}", body_start_node_id: "" },
  memory: { vector_store_ref: "", query: "{{previous}}", top_k: 5 },
  tool: { function_name: "", description: "", implementation_ref: "" },
  subworkflow: { workflow_id: "", pinned_version_id: "" },
  merge: { strategy: "combine-object" },
};

interface CanvasProps {
  workflowId?: string;
  initialGraph?: GraphJson;
  activeVersionId?: string | null;
  onSaved?: (workflowId: string) => void;
  onReverted?: () => void;
}

export function Canvas({
  workflowId,
  initialGraph,
  activeVersionId,
  onSaved,
  onReverted,
}: CanvasProps) {
  const toFlowNodes = (graph?: GraphJson): Node[] =>
    (graph?.nodes ?? []).map((n) => ({
      id: n.id,
      type: n.type,
      position: n.position,
      data: {
        name: n.name,
        config: n.config,
        // Bug fix: this used to be a no-op, which meant every field on every
        // node became silently uneditable as soon as you reopened a
        // previously-saved workflow (only brand-new nodes added via the
        // toolbar, wired up in addNode() below, ever got a real handler).
        onConfigChange: (config: Record<string, unknown>) =>
          updateNodeConfig(n.id, config),
      },
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
  const [savedMessage, setSavedMessage] = useState(false);
  const [versionRefreshKey, setVersionRefreshKey] = useState(0);
  const [showCode, setShowCode] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);
  const [copiedLangGraph, setCopiedLangGraph] = useState(false);
  const [langGraphCode, setLangGraphCode] = useState<string | null>(null);
  const [langGraphLoading, setLangGraphLoading] = useState(false);

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

  // Click a node (or shift-click several) to select it, then either press
  // Backspace/Delete or click this button. Cleans up any edges attached to
  // whatever got deleted either way, so a removed node never leaves a
  // dangling edge behind.
  const onNodesDelete = useCallback(
    (deleted: Node[]) => {
      const deletedIds = new Set(deleted.map((n) => n.id));
      setEdges((eds) =>
        eds.filter(
          (e) => !deletedIds.has(e.source) && !deletedIds.has(e.target),
        ),
      );
    },
    [setEdges],
  );

  // Bug fix: this used to only look at selected nodes, so clicking a lone
  // edge (without either endpoint node also selected) and hitting this
  // button silently did nothing — you had to select an edge and press
  // Backspace instead, which React Flow already handles for free via
  // onEdgesChange. Now the button covers both, matching Backspace/Delete.
  function deleteSelected() {
    const selectedNodeIds = new Set(
      nodes.filter((n) => n.selected).map((n) => n.id),
    );
    const selectedEdgeIds = new Set(
      edges.filter((e) => e.selected).map((e) => e.id),
    );
    if (selectedNodeIds.size === 0 && selectedEdgeIds.size === 0) return;
    setNodes((nds) => nds.filter((n) => !selectedNodeIds.has(n.id)));
    setEdges((eds) =>
      eds.filter(
        (e) =>
          !selectedEdgeIds.has(e.id) &&
          !selectedNodeIds.has(e.source) &&
          !selectedNodeIds.has(e.target),
      ),
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

  function openCodeModal() {
    setShowCode(true);
    // Both sections show at once now (stacked in one pane), so fetch the
    // LangGraph rendering right away instead of waiting for a tab click —
    // JSON is already available synchronously from toGraphJson().
    setLangGraphLoading(true);
    api
      .codegenLangGraph(toGraphJson())
      .then((res) => setLangGraphCode(res.code))
      .catch(() => setLangGraphCode("# Failed to generate LangGraph code."))
      .finally(() => setLangGraphLoading(false));
  }

  function copyText(text: string, onDone: (copied: boolean) => void) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        onDone(true);
        setTimeout(() => onDone(false), 2000);
      })
      .catch(() => undefined);
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
      // Stay on this page (onSaved above just lets the parent know the
      // workflow's id, e.g. for version history) — show a transient
      // confirmation instead of navigating away.
      setSavedMessage(true);
      setTimeout(() => setSavedMessage(false), 3000);
      // VersionHistory only refetches when its workflowId prop changes, so
      // remounting it here is what makes the just-saved version show up
      // without needing to leave and come back to this page.
      setVersionRefreshKey((k) => k + 1);
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
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        position: "relative",
      }}
    >
      <div className="ng-toolbar">
        <button onClick={() => addNode("input")}>+ Input</button>
        <button onClick={() => addNode("llm")}>+ LLM</button>
        <button onClick={() => addNode("response")}>+ Response</button>
        <button onClick={() => addNode("decision")}>+ Decision</button>
        <button onClick={() => addNode("api")}>+ API</button>
        <button onClick={() => addNode("variable")}>+ Variable</button>
        <button onClick={() => addNode("code")}>+ Code</button>
        <button onClick={() => addNode("retry")}>+ Retry</button>
        <button onClick={() => addNode("loop")}>+ Loop</button>
        <button onClick={() => addNode("memory")}>+ Memory</button>
        <button onClick={() => addNode("tool")}>+ Tool</button>
        <button onClick={() => addNode("subworkflow")}>+ Sub-workflow</button>
        <button onClick={() => addNode("merge")}>+ Merge</button>
        <button
          onClick={deleteSelected}
          title="Select a node or edge (click it, shift-click for more) then delete it — or press Backspace/Delete"
        >
          🗑 Delete selected
        </button>
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
        <button onClick={openCodeModal}>{"</>"} View code</button>
      </div>
      {errors.length > 0 && (
        <ul className="ng-errors">
          {errors.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      )}
      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        <div style={{ flex: 1 }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodesDelete={onNodesDelete}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            deleteKeyCode={["Backspace", "Delete"]}
            fitView
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {workflowId && (
          <VersionHistory
            key={versionRefreshKey}
            workflowId={workflowId}
            activeVersionId={activeVersionId ?? null}
            onReverted={() => onReverted?.()}
          />
        )}
      </div>
      {savedMessage && <div className="ng-saved-toast">✓ Saved</div>}
      {showCode && (
        <div
          className="ng-code-overlay"
          onClick={() => setShowCode(false)}
          role="presentation"
        >
          <div
            className="ng-code-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-label="Generated code"
          >
            <div className="ng-code-modal-header">
              <strong>Generated code</strong>
              <button onClick={() => setShowCode(false)}>Close</button>
            </div>
            <div className="ng-code-sections">
              <div className="ng-code-section">
                <div className="ng-code-section-header">
                  <span>Graph JSON</span>
                  <button
                    onClick={() =>
                      copyText(
                        JSON.stringify(toGraphJson(), null, 2),
                        setCopiedJson,
                      )
                    }
                  >
                    {copiedJson ? "Copied!" : "Copy"}
                  </button>
                </div>
                <pre className="ng-code-pre">
                  {JSON.stringify(toGraphJson(), null, 2)}
                </pre>
              </div>
              <div className="ng-code-section">
                <div className="ng-code-section-header">
                  <span>LangGraph code</span>
                  <button
                    onClick={() =>
                      copyText(langGraphCode ?? "", setCopiedLangGraph)
                    }
                  >
                    {copiedLangGraph ? "Copied!" : "Copy"}
                  </button>
                </div>
                <pre className="ng-code-pre">
                  {langGraphLoading
                    ? "Generating…"
                    : (langGraphCode ?? "Could not generate — try reopening.")}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
