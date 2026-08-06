import { useEffect, useState } from "react";
import { api } from "../api/client";

interface GitHubStatus {
  owner: string;
  repo: string;
  branch: string;
  files_parsed: number;
  chunks_indexed: number;
  last_synced_at: string | null;
  status: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function GitHubSyncManager({ open, onClose }: Props) {
  const [owner, setOwner] = useState("vbelle");
  const [repo, setRepo] = useState("Interview");
  const [branch, setBranch] = useState("");
  const [token, setToken] = useState("");
  const [targetCollection, setTargetCollection] = useState("interview_vault");
  const [reset, setReset] = useState(true);
  const [status, setStatus] = useState<GitHubStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function loadStatus() {
    setLoading(true);
    api
      .getGitHubStatus(owner, repo)
      .then(setStatus)
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) {
      loadStatus();
      setMessage(null);
      setError(null);
    }
  }, [open]);

  async function handleSync(e: React.FormEvent) {
    e.preventDefault();
    if (!owner.trim() || !repo.trim()) {
      setError("Owner and Repository Name are required.");
      return;
    }

    setSyncing(true);
    setMessage(null);
    setError(null);

    try {
      const res = await api.syncGitHubRepo(
        owner.trim(),
        repo.trim(),
        branch.trim() || undefined,
        token.trim() || undefined,
        targetCollection,
        reset,
      );
      setStatus(res);
      setMessage(
        `✓ GitHub Repo '${res.owner}/${res.repo}' synced! Indexed ${res.files_parsed} files (${res.chunks_indexed} chunks) into '${res.target_collection}'.`,
      );
    } catch (err) {
      setError(
        typeof err === "object" && err !== null && "message" in err
          ? String((err as { message?: string }).message)
          : "GitHub sync failed. Verify repo name and Personal Access Token.",
      );
    } finally {
      setSyncing(false);
    }
  }

  if (!open) return null;

  return (
    <div className="ng-code-overlay" onClick={onClose} role="presentation">
      <div
        className="ng-cred-modal"
        style={{ width: "620px", display: "flex", flexDirection: "column" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Direct GitHub RAG Sync"
      >
        <div className="ng-code-modal-header">
          <strong>🐙 GitHub Repository Direct RAG Sync</strong>
          <button onClick={onClose} aria-label="Close">
            ✕ Close
          </button>
        </div>

        {message && <div className="ng-cred-toast">{message}</div>}

        <form onSubmit={handleSync} style={{ padding: "16px", fontSize: "13px", lineHeight: "1.6" }}>
          <p style={{ margin: "0 0 12px 0", color: "#555" }}>
            Fetches files directly from GitHub repos (e.g. <code>vbelle/Interview</code> or <code>vbelle/Obsidian</code>) via GitHub API — no local filesystem required!
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "10px" }}>
            <div>
              <label style={{ fontSize: "11px", fontWeight: "bold" }}>GitHub Owner / Org</label>
              <input
                type="text"
                placeholder="vbelle"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                disabled={syncing}
                style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
              />
            </div>
            <div>
              <label style={{ fontSize: "11px", fontWeight: "bold" }}>Repository Name</label>
              <input
                type="text"
                placeholder="Interview"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                disabled={syncing}
                style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
              />
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "10px" }}>
            <div>
              <label style={{ fontSize: "11px", fontWeight: "bold" }}>Branch (Optional)</label>
              <input
                type="text"
                placeholder="main (or master)"
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                disabled={syncing}
                style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
              />
            </div>
            <div>
              <label style={{ fontSize: "11px", fontWeight: "bold" }}>Target Collection</label>
              <select
                value={targetCollection}
                onChange={(e) => setTargetCollection(e.target.value)}
                disabled={syncing}
                style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
              >
                <option value="interview_vault">interview_vault</option>
                <option value="obsidian_vault">obsidian_vault</option>
              </select>
            </div>
          </div>

          <div style={{ marginBottom: "14px" }}>
            <label style={{ fontSize: "11px", fontWeight: "bold" }}>GitHub Personal Access Token (Required for Private Repos)</label>
            <input
              type="password"
              placeholder="ghp_xxxxxxxxxxxxxxxxxxxx (leave blank if repo is public)"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              disabled={syncing}
              style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
            />
          </div>

          <div style={{ marginBottom: "14px", display: "flex", alignItems: "center", gap: "8px" }}>
            <input
              type="checkbox"
              id="reset-check"
              checked={reset}
              onChange={(e) => setReset(e.target.checked)}
              disabled={syncing}
            />
            <label htmlFor="reset-check" style={{ fontSize: "12px", color: "#b91c1c", fontWeight: "bold", cursor: "pointer" }}>
              🧹 Reset Collection & Re-Index Cleanly (Wipe Old Chunks)
            </label>
          </div>

          {status && (
            <div style={{ background: "#f8fafc", border: "1px solid #e2e8f0", borderRadius: "6px", padding: "10px", marginBottom: "14px" }}>
              <div><strong>Status:</strong> {status.status.toUpperCase()}</div>
              <div><strong>Last Sync:</strong> {status.last_synced_at ? new Date(status.last_synced_at).toLocaleString() : "Never"}</div>
              <div><strong>Files / Chunks:</strong> {status.files_parsed} files ({status.chunks_indexed} chunks)</div>
            </div>
          )}

          {error && <p className="ng-cred-error" role="alert">{error}</p>}

          <button
            type="submit"
            disabled={syncing}
            className="ng-cred-submit"
            style={{ width: "100%", padding: "10px", fontSize: "14px", fontWeight: "bold" }}
          >
            {syncing ? "Syncing from GitHub API…" : "🐙 Sync GitHub Repository Now"}
          </button>
        </form>
      </div>
    </div>
  );
}
