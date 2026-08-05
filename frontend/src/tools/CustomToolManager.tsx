import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";

interface CustomTool {
  id: string;
  name: string;
  description: string;
  python_code: string;
  created_at: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

const DEFAULT_PYTHON_TEMPLATE = `def my_custom_tool(query: str) -> str:
    """Description of what your custom tool does (used by the LLM)."""
    # Write your Python code here
    return f"Processed query: {query}"
`;

function extractDetail(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as Record<string, unknown> | null;
    if (body && typeof body.detail === "string") return body.detail;
    if (body && typeof body.detail === "object" && body.detail !== null) {
      const d = body.detail as Record<string, unknown>;
      if (typeof d.detail === "string") return d.detail;
    }
  }
  return "An unexpected error occurred.";
}

export function CustomToolManager({ open, onClose }: Props) {
  const [tools, setTools] = useState<CustomTool[]>([]);
  const [loading, setLoading] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [pythonCode, setPythonCode] = useState(DEFAULT_PYTHON_TEMPLATE);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  function load() {
    setLoading(true);
    api
      .listCustomTools()
      .then(setTools)
      .catch(() => setTools([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) {
      load();
      setError(null);
      setSuccessMessage(null);
      setTimeout(() => nameInputRef.current?.focus(), 50);
    }
  }, [open]);

  function showSuccess(msg: string) {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const toolName = name.trim();
    const toolDesc = description.trim();
    const code = pythonCode.trim();

    if (!toolName || !toolDesc || !code) {
      setError("Name, description, and Python code are all required.");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      await api.createCustomTool(toolName, toolDesc, code);
      setName("");
      setDescription("");
      setPythonCode(DEFAULT_PYTHON_TEMPLATE);
      load();
      showSuccess(`✓ Custom tool "${toolName}" created!`);
    } catch (err) {
      setError(extractDetail(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(tool: CustomTool) {
    if (
      !window.confirm(
        `Delete custom tool "${tool.name}"?\n\nThis action cannot be undone.`,
      )
    )
      return;

    setError(null);
    setDeletingId(tool.id);
    try {
      await api.deleteCustomTool(tool.id);
      load();
      showSuccess(`✓ Custom tool "${tool.name}" deleted`);
    } catch (err) {
      setError(extractDetail(err));
    } finally {
      setDeletingId(null);
    }
  }

  if (!open) return null;

  return (
    <div
      className="ng-code-overlay"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="ng-cred-modal"
        style={{ width: "650px", maxHeight: "85vh", display: "flex", flexDirection: "column" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Custom Tools Manager"
      >
        {/* Header */}
        <div className="ng-code-modal-header">
          <strong>🛠️ Native Custom Python Tools</strong>
          <button onClick={onClose} aria-label="Close">
            ✕ Close
          </button>
        </div>

        {/* Success Toast */}
        {successMessage && (
          <div className="ng-cred-toast">{successMessage}</div>
        )}

        {/* List of Custom Tools */}
        <div className="ng-cred-list" style={{ maxHeight: "160px", overflowY: "auto" }}>
          {loading && tools.length === 0 ? (
            <p className="ng-cred-empty">Loading…</p>
          ) : tools.length === 0 ? (
            <p className="ng-cred-empty">
              No custom Python tools yet. Write one below to register it!
            </p>
          ) : (
            tools.map((t) => (
              <div key={t.id} className="ng-cred-row">
                <span className="ng-cred-name" title={t.description}>
                  ⚙️ <strong>{t.name}</strong> — <small>{t.description}</small>
                </span>
                <button
                  className="ng-cred-delete"
                  onClick={() => handleDelete(t)}
                  disabled={deletingId === t.id}
                >
                  {deletingId === t.id ? "Deleting…" : "Delete"}
                </button>
              </div>
            ))
          )}
        </div>

        {/* Create Tool Form */}
        <form
          className="ng-cred-form"
          onSubmit={handleCreate}
          style={{ flex: 1, display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}
        >
          <p className="ng-cred-form-title">Register a Custom Python Tool</p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <div>
              <label htmlFor="ng-tool-name">Tool Name (python_name)</label>
              <input
                id="ng-tool-name"
                ref={nameInputRef}
                type="text"
                placeholder="e.g. fetch_stock_quote"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={submitting}
              />
            </div>
            <div>
              <label htmlFor="ng-tool-desc">LLM Description</label>
              <input
                id="ng-tool-desc"
                type="text"
                placeholder="e.g. Fetches live stock quotes for a ticker"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>

          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <label htmlFor="ng-tool-code">Python Function Code</label>
            <textarea
              id="ng-tool-code"
              style={{
                width: "100%",
                height: "160px",
                fontFamily: "monospace",
                fontSize: "12px",
                padding: "8px",
                borderRadius: "4px",
                border: "1px solid #ccc",
                backgroundColor: "#1e1e1e",
                color: "#d4d4d4",
                lineHeight: "1.4",
              }}
              value={pythonCode}
              onChange={(e) => setPythonCode(e.target.value)}
              disabled={submitting}
              spellCheck={false}
            />
          </div>

          {error && <p className="ng-cred-error" role="alert">{error}</p>}

          <button
            type="submit"
            className="ng-cred-submit"
            disabled={submitting}
          >
            {submitting ? "Registering…" : "Register Custom Tool"}
          </button>
        </form>
      </div>
    </div>
  );
}
