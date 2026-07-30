import { useEffect, useState } from "react";
import { api, type WorkflowVersionSummary } from "../api/client";

interface VersionHistoryProps {
  workflowId: string;
  activeVersionId: string | null;
  onReverted: () => void;
}

export function VersionHistory({
  workflowId,
  activeVersionId,
  onReverted,
}: VersionHistoryProps) {
  const [versions, setVersions] = useState<WorkflowVersionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [revertingId, setRevertingId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .listVersions(workflowId)
      .then(setVersions)
      .finally(() => setLoading(false));
  }, [workflowId]);

  async function handleActivate(versionId: string) {
    setRevertingId(versionId);
    try {
      await api.activateVersion(workflowId, versionId);
      onReverted();
    } finally {
      setRevertingId(null);
    }
  }

  if (loading) {
    return <p className="ng-version-history">Loading version history…</p>;
  }

  const sorted = [...versions].sort(
    (a, b) => b.version_number - a.version_number,
  );

  return (
    <div className="ng-version-history">
      <h4>Version history</h4>
      <ul>
        {sorted.map((v) => (
          <li key={v.id}>
            <span>
              v{v.version_number} — {new Date(v.created_at).toLocaleString()}
            </span>
            {v.id === activeVersionId ? (
              <span className="ng-version-active"> active</span>
            ) : (
              <button
                onClick={() => handleActivate(v.id)}
                disabled={revertingId === v.id}
              >
                {revertingId === v.id ? "Reverting…" : "Revert to this"}
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
