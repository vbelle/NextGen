import { useEffect, useState } from "react";
import { api } from "../api/client";

interface ObsidianStatus {
  vault_path: string;
  total_vault_notes: number;
  last_synced_at: string | null;
  notes_parsed: number;
  chunks_indexed: number;
  collection_name: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ObsidianManager({ open, onClose }: Props) {
  const [status, setStatus] = useState<ObsidianStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  function loadStatus() {
    setLoading(true);
    api
      .getObsidianStatus()
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
      const updated = await api.syncObsidianVault();
      setStatus(updated);
      setMessage(`✓ Vault synced! Indexed ${updated.notes_parsed} notes (${updated.chunks_indexed} chunks) into '${updated.collection_name}'.`);
    } catch {
      setMessage("Failed to sync Obsidian vault.");
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
        aria-label="Obsidian Vault RAG Sync"
      >
        <div className="ng-code-modal-header">
          <strong>📓 Obsidian Vault RAG Engine</strong>
          <button onClick={onClose} aria-label="Close">
            ✕ Close
          </button>
        </div>

        {message && <div className="ng-cred-toast">{message}</div>}

        <div style={{ padding: "16px", fontSize: "13px", lineHeight: "1.6" }}>
          <p style={{ margin: "0 0 12px 0", color: "#555" }}>
            Indexes your local Obsidian Markdown notes (including headers, tags like <code>#finance</code>, and wikilinks like <code>[[Note Name]]</code>) into ChromaDB for canvas Memory RAG queries.
          </p>

          {loading ? (
            <p>Loading status…</p>
          ) : status ? (
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "6px", padding: "12px", marginBottom: "16px" }}>
              <div style={{ marginBottom: "6px" }}>
                <strong>Vault Location:</strong> <code>{status.vault_path}</code>
              </div>
              <div style={{ marginBottom: "6px" }}>
                <strong>Total Notes Found:</strong> {status.total_vault_notes}
              </div>
              <div style={{ marginBottom: "6px" }}>
                <strong>Indexed Chunks:</strong> {status.chunks_indexed} (collection: <code>{status.collection_name}</code>)
              </div>
              <div>
                <strong>Last Sync:</strong> {status.last_synced_at ? new Date(status.last_synced_at).toLocaleString() : "Never synced"} (Auto-syncs daily at 2:00 AM)
              </div>
            </div>
          ) : null}

          <button
            onClick={handleSync}
            disabled={syncing}
            className="ng-cred-submit"
            style={{ width: "100%", padding: "10px", fontSize: "14px", fontWeight: "bold" }}
          >
            {syncing ? "Syncing Obsidian Vault…" : "🔄 Sync Obsidian Vault Now"}
          </button>
        </div>
      </div>
    </div>
  );
}
