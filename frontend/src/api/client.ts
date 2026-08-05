// Typed REST + WebSocket client. Mirrors specs/001-workflow-builder/contracts/.

export interface WorkflowSummary {
  id: string;
  name: string;
  active_version_id: string | null;
  created_at: string;
}

export interface WorkflowDetail extends WorkflowSummary {
  graph_json: GraphJson | null;
}

export interface WorkflowVersionSummary {
  id: string;
  version_number: number;
  created_at: string;
}

export interface GraphNode {
  id: string;
  type: string;
  name: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  source_port: string;
  target: string;
}

export interface GraphJson {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RunDetail {
  id: string;
  status: string;
  workflow_version_id: string;
  pending_prompt: unknown;
  started_at: string;
  ended_at: string | null;
}

export interface NodeExecutionEntry {
  id: string;
  node_id: string;
  node_type: string;
  output_port: string;
  input: unknown;
  output: unknown;
  attempt_count: number | null;
  started_at: string;
  ended_at: string | null;
}

export interface ApiErrorBody {
  detail:
    string | { detail: string; errors?: { field: string; issue: string }[] };
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    const message =
      typeof body === "object" &&
      body &&
      "detail" in (body as Record<string, unknown>)
        ? JSON.stringify((body as ApiErrorBody).detail)
        : `Request failed with status ${status}`;
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      // no body
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  login: (password: string) =>
    request<{ authenticated: boolean }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),
  logout: () =>
    request<{ authenticated: boolean }>("/api/auth/logout", { method: "POST" }),

  listWorkflows: () => request<WorkflowSummary[]>("/api/workflows"),
  getWorkflow: (id: string) => request<WorkflowDetail>(`/api/workflows/${id}`),
  createWorkflow: (name: string, graph_json: GraphJson) =>
    request<WorkflowSummary>("/api/workflows", {
      method: "POST",
      body: JSON.stringify({ name, graph_json }),
    }),
  saveVersion: (workflowId: string, graph_json: GraphJson) =>
    request<{ id: string; version_number: number; created_at: string }>(
      `/api/workflows/${workflowId}/versions`,
      { method: "POST", body: JSON.stringify({ graph_json }) },
    ),
  listVersions: (workflowId: string) =>
    request<WorkflowVersionSummary[]>(`/api/workflows/${workflowId}/versions`),
  activateVersion: (workflowId: string, versionId: string) =>
    request<WorkflowSummary>(
      `/api/workflows/${workflowId}/activate/${versionId}`,
      { method: "POST" },
    ),

  getRun: (runId: string) => request<RunDetail>(`/api/runs/${runId}`),
  getRunExecutions: (runId: string) =>
    request<NodeExecutionEntry[]>(`/api/runs/${runId}/executions`),

  listCredentials: () =>
    request<{ id: string; name: string; created_at: string }[]>(
      "/api/credentials",
    ),
  createCredential: (name: string, value: string) =>
    request<{ id: string; name: string; created_at: string }>("/api/credentials", {
      method: "POST",
      body: JSON.stringify({ name, value }),
    }),
  deleteCredential: (id: string) =>
    request<void>(`/api/credentials/${id}`, { method: "DELETE" }),

  listVectorStores: () => request<{ name: string }[]>("/api/vector-stores"),

  listToolImplementations: () =>
    request<{ implementation_ref: string }[]>("/api/tools"),

  listCustomTools: () =>
    request<{
      id: string;
      name: string;
      description: string;
      python_code: string;
      created_at: string;
      updated_at: string;
    }[]>("/api/custom-tools"),

  createCustomTool: (name: string, description: string, python_code: string) =>
    request<{
      id: string;
      name: string;
      description: string;
      python_code: string;
      created_at: string;
      updated_at: string;
    }>("/api/custom-tools", {
      method: "POST",
      body: JSON.stringify({ name, description, python_code }),
    }),

  deleteCustomTool: (id: string) =>
    request<void>(`/api/custom-tools/${id}`, { method: "DELETE" }),

  codegenLangGraph: (graph_json: GraphJson) =>
    request<{ code: string }>("/api/codegen/langgraph", {
      method: "POST",
      body: JSON.stringify({ graph_json }),
    }),
};

// --- Chat WebSocket (contracts/chat-websocket.md) ---

export type ChatServerMessage =
  | {
      type: "history";
      payload: {
        session_id: string;
        messages: { role: string; content: string; run_id: string | null }[];
      };
    }
  | {
      type: "status";
      payload: {
        run_id: string;
        status: string;
        workflow_name: string;
        version_number: number;
      };
    }
  | {
      type: "input_request";
      payload: { run_id: string; prompt: string; node_id: string };
    }
  | { type: "response"; payload: { run_id: string; content: unknown } }
  | { type: "run_failed"; payload: { run_id: string; message: string } }
  | { type: "workflow_not_found"; payload: { name: string } };

export type ChatClientMessage =
  | { type: "start_workflow"; payload: { name: string } }
  | { type: "provide_input"; payload: { run_id: string; value: string } };

export function connectChat(
  sessionId: string | null,
  onMessage: (msg: ChatServerMessage) => void,
): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/chat${qs}`);
  ws.onmessage = (event) => {
    onMessage(JSON.parse(event.data) as ChatServerMessage);
  };
  return ws;
}

export function sendChatMessage(ws: WebSocket, msg: ChatClientMessage): void {
  ws.send(JSON.stringify(msg));
}
