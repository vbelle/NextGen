import { useEffect, useState } from "react";
import { api } from "../api/client";

interface InterviewStatus {
  vault_path: string;
  total_files: number;
  last_synced_at: string | null;
  files_parsed: number;
  chunks_indexed: number;
  collection_name: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function InterviewManager({ open, onClose }: Props) {
  const [status, setStatus] = useState<InterviewStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function loadStatus() {
    setLoading(true);
    api
      .getInterviewStatus()
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) {
      loadStatus();
      setMessage(null);
    }
  }, [open]);

  async function handleSync() {
    setSyncing(true);
    setMessage(null);
    try {
      const updated = await api.syncInterviewVault();
      setStatus(updated);
      setMessage(`✓ Interview Vault synced! Indexed ${updated.files_parsed} files (${updated.chunks_indexed} chunks) into '${updated.collection_name}'.`);
    } catch {
      setMessage("Failed to sync Interview vault.");
    } finally {
      setSyncing(false);
    }
  }

  if (!open) return null;

  return (
    <div className="ng-code-overlay" onClick={onClose} role="presentation">
      <div
        className="ng-cred-modal"
        style={{ width: "580px", display: "flex", flexDirection: "column" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Interview Repository RAG Sync"
      >
        <div className="ng-code-modal-header">
          <strong>💼 Interview Knowledge RAG Engine</strong>
          <button onClick={onClose} aria-label="Close">
            ✕ Close
          </button>
        </div>

        {message && <div className="ng-cred-toast">{message}</div>}

        <div style={{ padding: "16px", fontSize: "13px", lineHeight: "1.6" }}>
          <p style={{ margin: "0 0 12px 0", color: "#555" }}>
            Indexes your <code>vbelle/Interview</code> repository (interview prep, company briefs, technical cheatsheets, resumes, and job descriptions) into ChromaDB for canvas RAG queries and function-calling via the <code>interview_search</code> tool.
          </p>

          {loading ? (
            <p>Loading status…</p>
          ) : status ? (
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "6px", padding: "12px", marginBottom: "16px" }}>
              <div style={{ marginBottom: "6px" }}>
                <strong>Vault Location:</strong> <code>{status.vault_path}</code>
              </div>
              <div style={{ marginBottom: "6px" }}>
                <strong>Total Files Found:</strong> {status.total_files}
              </div>
              <div style={{ marginBottom: "6px" }}>
                <strong>Indexed Chunks:</strong> {status.chunks_indexed} (collection: <code>{status.collection_name}</code>)
              </div>
              <div>
                <strong>Last Sync:</strong> {status.last_synced_at ? new Date(status.last_synced_at).toLocaleString() : "Never synced"} (Auto-syncs daily at 3:00 AM)
              </div>
            </div>
          ) : null}

          <button
            onClick={handleSync}
            disabled={syncing}
            className="ng-cred-submit"
            style={{ width: "100%", padding: "10px", fontSize: "14px", fontWeight: "bold" }}
          >
            {syncing ? "Syncing Interview Vault…" : "🔄 Sync Interview Vault Now"}
          </button>
        </div>
      </div>
    </div>
  );
}
