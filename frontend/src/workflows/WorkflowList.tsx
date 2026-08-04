import { useEffect, useState } from "react";
import { api, type WorkflowSummary } from "../api/client";

export function WorkflowList({
  onOpenBuilder,
  onOpenChat,
  onRunWorkflow,
}: {
  onOpenBuilder: (workflowId?: string) => void;
  onOpenChat: () => void;
  onRunWorkflow: (name: string) => void;
}) {
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [importOpen, setImportOpen] = useState(false);
  const [importJson, setImportJson] = useState("");
  const [importName, setImportName] = useState("");
  const [error, setError] = useState<string | null>(null);

  function loadWorkflows() {
    setLoading(true);
    api
      .listWorkflows()
      .then(setWorkflows)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadWorkflows();
  }, []);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const text = evt.target?.result as string;
        const parsed = JSON.parse(text);
        if (parsed.name && !importName) {
          setImportName(parsed.name);
        }
        setImportJson(JSON.stringify(parsed.graph_json || parsed, null, 2));
        setError(null);
      } catch (err) {
        setError("Failed to parse JSON file");
      }
    };
    reader.readAsText(file);
  }

  async function handleImportSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!importName.trim() || !importJson.trim()) {
      setError("Workflow name and graph JSON are required");
      return;
    }
    setError(null);
    try {
      const parsedGraph = JSON.parse(importJson);
      const graph_json = parsedGraph.graph_json || parsedGraph;
      await api.createWorkflow(importName.trim(), graph_json);
      setImportOpen(false);
      setImportName("");
      setImportJson("");
      loadWorkflows();
    } catch (err: any) {
      const msg = err.body?.detail?.detail || err.message || "Import failed";
      setError(msg);
    }
  }

  return (
    <div className="ng-workflow-list">
      <div className="ng-toolbar">
        <button onClick={() => onOpenBuilder(undefined)}>+ New workflow</button>
        <button onClick={() => setImportOpen(true)}>📥 Import workflow</button>
        <button onClick={onOpenChat}>Open chat</button>
      </div>

      {importOpen && (
        <div
          className="ng-code-overlay"
          onClick={() => setImportOpen(false)}
          role="presentation"
        >
          <div
            className="ng-cred-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
          >
            <div className="ng-code-modal-header">
              <strong>📥 Import Workflow</strong>
              <button onClick={() => setImportOpen(false)}>✕ Close</button>
            </div>
            <form className="ng-cred-form" onSubmit={handleImportSubmit}>
              <div>
                <label>Upload JSON file</label>
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileSelect}
                  style={{ marginBottom: "8px" }}
                />
              </div>
              <div>
                <label>Workflow Name</label>
                <input
                  type="text"
                  placeholder="e.g. fact_search_assistant"
                  value={importName}
                  onChange={(e) => setImportName(e.target.value)}
                />
              </div>
              <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                <label>Graph JSON</label>
                <textarea
                  style={{
                    width: "100%",
                    height: "180px",
                    fontFamily: "monospace",
                    fontSize: "11px",
                    padding: "6px",
                  }}
                  placeholder="Paste workflow JSON here..."
                  value={importJson}
                  onChange={(e) => setImportJson(e.target.value)}
                />
              </div>
              {error && <p className="ng-cred-error">{error}</p>}
              <button type="submit" className="ng-cred-submit">
                Import Workflow
              </button>
            </form>
          </div>
        </div>
      )}

      {loading ? (
        <p>Loading…</p>
      ) : workflows.length === 0 ? (
        <p>No workflows yet — build one or import JSON to get started.</p>
      ) : (
        <ul>
          {workflows.map((w) => (
            <li key={w.id}>
              <button onClick={() => onOpenBuilder(w.id)}>{w.name}</button>
              <button
                className="ng-workflow-run"
                onClick={() => onRunWorkflow(w.name)}
              >
                ▶ Run
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
