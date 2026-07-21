import { useEffect, useState } from "react";
import { api, type WorkflowSummary } from "../api/client";

export function WorkflowList({
  onOpenBuilder,
  onOpenChat,
}: {
  onOpenBuilder: (workflowId?: string) => void;
  onOpenChat: () => void;
}) {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listWorkflows()
      .then(setWorkflows)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="ng-workflow-list">
      <div className="ng-toolbar">
        <button onClick={() => onOpenBuilder(undefined)}>+ New workflow</button>
        <button onClick={onOpenChat}>Open chat</button>
      </div>
      {loading ? (
        <p>Loading…</p>
      ) : workflows.length === 0 ? (
        <p>No workflows yet — build one to get started.</p>
      ) : (
        <ul>
          {workflows.map((w) => (
            <li key={w.id}>
              <button onClick={() => onOpenBuilder(w.id)}>{w.name}</button>
              <span className="ng-workflow-meta">
                {" "}
                — invoke in chat as "{w.name}"
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
