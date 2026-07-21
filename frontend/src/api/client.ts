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
    request<{ id: string; version_number: number; created_at: string }[]>(
      `/api/workflows/${workflowId}/versions`,
    ),
  activateVersion: (workflowId: string, versionId: string) =>
    request<WorkflowSummary>(
      `/api/workflows/${workflowId}/activate/${versionId}`,
      { method: "POST" },
    ),

  getRun: (runId: string) =>
    request<Record<string, unknown>>(`/api/runs/${runId}`),
  getRunExecutions: (runId: string) =>
    request<Record<string, unknown>[]>(`/api/runs/${runId}/executions`),

  listCredentials: () =>
    request<{ id: string; name: string; created_at: string }[]>(
      "/api/credentials",
    ),
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
  | { type: "status"; payload: { run_id: string; status: string } }
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
