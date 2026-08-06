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

  async function handleDeleteWorkflow(id: string, name: string) {
    if (!window.confirm(`Are you sure you want to delete workflow '${name}'?`)) {
      return;
    }
    try {
      await api.deleteWorkflow(id, true);
      loadWorkflows();
    } catch {
      alert(`Failed to delete workflow '${name}'`);
    }
  }

  const [aiOpen, setAiOpen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiName, setAiName] = useState("");
  const [aiGenerating, setAiGenerating] = useState(false);

  async function handleAiGenerateSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!aiPrompt.trim()) {
      setError("Please enter a natural language prompt describing your workflow");
      return;
    }
    setError(null);
    setAiGenerating(true);
    try {
      const generatedWf = await api.generateWorkflow(
        aiPrompt.trim(),
        aiName.trim() || undefined
      );
      setAiOpen(false);
      setAiPrompt("");
      setAiName("");
      loadWorkflows();
      onOpenBuilder(generatedWf.id);
    } catch (err: any) {
      const msg = err.body?.detail || err.message || "AI generation failed";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setAiGenerating(false);
    }
  }

  return (
    <div className="ng-workflow-list">
      <div className="ng-toolbar">
        <button onClick={() => onOpenBuilder(undefined)}>+ New workflow</button>
        <button onClick={() => setAiOpen(true)} style={{ background: "#7c3aed", color: "#fff" }}>
          ✨ AI Generate Workflow
        </button>
        <button onClick={() => setImportOpen(true)}>📥 Import workflow</button>
        <button onClick={onOpenChat}>Open chat</button>
      </div>

      {aiOpen && (
        <div
          className="ng-code-overlay"
          onClick={() => !aiGenerating && setAiOpen(false)}
          role="presentation"
        >
          <div
            className="ng-cred-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
          >
            <div className="ng-code-modal-header">
              <strong>✨ AI Workflow Generator</strong>
              <button disabled={aiGenerating} onClick={() => setAiOpen(false)}>
                ✕ Close
              </button>
            </div>
            <form className="ng-cred-form" onSubmit={handleAiGenerateSubmit}>
              <div>
                <label>Workflow Name (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. multi_agent_researcher"
                  value={aiName}
                  onChange={(e) => setAiName(e.target.value)}
                  disabled={aiGenerating}
                />
              </div>
              <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                <label>Describe the Workflow & Agents in Plain English</label>
                <textarea
                  style={{
                    width: "100%",
                    height: "150px",
                    fontFamily: "inherit",
                    fontSize: "13px",
                    padding: "8px",
                  }}
                  placeholder="e.g. Build a 3-agent team: a RAG Memory Researcher that searches Obsidian, a System Architect agent, and a Synthesis Critic that consolidates their findings..."
                  value={aiPrompt}
                  onChange={(e) => setAiPrompt(e.target.value)}
                  disabled={aiGenerating}
                />
              </div>
              {error && <p className="ng-cred-error">{error}</p>}
              <button
                type="submit"
                className="ng-cred-submit"
                disabled={aiGenerating}
                style={{ background: "#7c3aed", color: "#fff" }}
              >
                {aiGenerating ? "⚡ Generating AI Graph & Wiring Nodes..." : "✨ Generate & Open Workflow"}
              </button>
            </form>
          </div>
        </div>
      )}

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
            <li key={w.id} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <button onClick={() => onOpenBuilder(w.id)} style={{ flex: 1, textAlign: "left" }}>
                {w.name}
              </button>
              <button
                className="ng-workflow-run"
                onClick={() => onRunWorkflow(w.name)}
              >
                ▶ Run
              </button>
              <button
                onClick={() => handleDeleteWorkflow(w.id, w.name)}
                style={{
                  background: "#fee2e2",
                  color: "#991b1b",
                  border: "1px solid #fca5a5",
                  borderRadius: "4px",
                  padding: "4px 8px",
                  cursor: "pointer",
                  fontSize: "12px",
                }}
                title="Delete Workflow"
              >
                🗑 Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
