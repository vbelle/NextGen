import { useEffect, useState } from "react";
import { api, type NodeExecutionEntry } from "../api/client";

export interface LogsSidecarProps {
  open: boolean;
  onClose: () => void;
  /** The run currently tracked by the chat sidecar (see
   * ChatSidecar's onRunIdChange). Null until a flow has been started. */
  runId: string | null;
  /** True while the chat sidecar is also open, so this panel can slide in
   * next to it instead of underneath it. */
  pushLeft?: boolean;
}

const POLL_MS = 1500;

// No backend change was needed for this: app/graph/compiler.py already
// writes a NodeExecution row for every node as it runs (see
// record_node_execution), and GET /api/runs/{run_id}/executions already
// exposes them — there's just no live WebSocket push of them yet, so this
// polls instead. Simplest option that needed zero backend changes.
export function LogsSidecar({
  open,
  onClose,
  runId,
  pushLeft,
}: LogsSidecarProps) {
  const [entries, setEntries] = useState<NodeExecutionEntry[]>([]);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!open || !runId) {
      setEntries([]);
      setRunStatus(null);
      return;
    }
    let cancelled = false;
    function poll() {
      if (!runId) return;
      api
        .getRunExecutions(runId)
        .then((rows) => {
          if (!cancelled) setEntries(rows);
        })
        .catch(() => undefined);
      api
        .getRun(runId)
        .then((run) => {
          if (!cancelled) setRunStatus(run.status);
        })
        .catch(() => undefined);
    }
    poll();
    const timer = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [open, runId]);

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div
      className={[
        "ng-logs-sidecar",
        open ? "ng-logs-sidecar-open" : "",
        pushLeft ? "ng-logs-sidecar-pushed" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="ng-chat-sidecar-header">
        <span className="ng-chat-sidecar-title">Logs</span>
        <span className="ng-chat-status">
          {runId ? (runStatus ?? "…") : "no run yet"}
        </span>
        <button className="ng-chat-close" onClick={onClose} title="Close">
          ✕
        </button>
      </div>
      <div className="ng-logs-list">
        {!runId && (
          <p className="ng-chat-picker-hint">
            Start a flow in Chat to see its node-by-node log here.
          </p>
        )}
        {runId && entries.length === 0 && (
          <p className="ng-chat-picker-hint">No node executions yet…</p>
        )}
        {entries.map((e) => (
          <div
            key={e.id}
            className="ng-logs-entry"
            onClick={() => toggle(e.id)}
          >
            <div className="ng-logs-entry-row">
              <span className="ng-logs-node">{e.node_type}</span>
              <span className="ng-logs-port">{e.output_port}</span>
            </div>
            <div className="ng-logs-entry-sub">{e.node_id}</div>
            {expanded.has(e.id) && (
              <pre className="ng-logs-io">
                {JSON.stringify({ input: e.input, output: e.output }, null, 2)}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
