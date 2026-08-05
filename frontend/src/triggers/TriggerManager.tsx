import { useEffect, useState } from "react";
import { api, ApiError, type WorkflowSummary } from "../api/client";

interface Trigger {
  id: string;
  workflow_id: string;
  workflow_name: string | null;
  trigger_type: string;
  cron_expression: string | null;
  webhook_secret: string | null;
  enabled: boolean;
  created_at: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

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

export function TriggerManager({ open, onClose }: Props) {
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const [triggerType, setTriggerType] = useState<"webhook" | "cron">("webhook");
  const [cronExpression, setCronExpression] = useState("0 9 * * *");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([api.listTriggers(), api.listWorkflows()])
      .then(([tRows, wRows]) => {
        setTriggers(tRows);
        setWorkflows(wRows);
        if (wRows.length > 0 && !selectedWorkflowId) {
          setSelectedWorkflowId(wRows[0].id);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) {
      load();
      setError(null);
      setSuccessMessage(null);
    }
  }, [open]);

  function showSuccess(msg: string) {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedWorkflowId) {
      setError("Please select a workflow.");
      return;
    }

    if (triggerType === "cron" && !cronExpression.trim()) {
      setError("Cron expression is required for scheduled triggers.");
      return;
    }

    setError(null);
    setSubmitting(true);
    try {
      await api.createTrigger(
        selectedWorkflowId,
        triggerType,
        triggerType === "cron" ? cronExpression.trim() : undefined,
        webhookSecret.trim() || undefined,
        true,
      );
      setWebhookSecret("");
      load();
      showSuccess(`✓ ${triggerType === "webhook" ? "Webhook" : "Cron Schedule"} Trigger created!`);
    } catch (err) {
      setError(extractDetail(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(t: Trigger) {
    if (!window.confirm("Delete this trigger?")) return;
    setError(null);
    setDeletingId(t.id);
    try {
      await api.deleteTrigger(t.id);
      load();
      showSuccess("✓ Trigger deleted");
    } catch (err) {
      setError(extractDetail(err));
    } finally {
      setDeletingId(null);
    }
  }

  function getWebhookUrl(wfName: string | null): string {
    const name = wfName || "workflow_name";
    return `${window.location.protocol}//${window.location.host}/api/triggers/webhook/${name}`;
  }

  function copyCurl(t: Trigger) {
    const url = getWebhookUrl(t.workflow_name);
    const secretHeader = t.webhook_secret ? ` -H "X-NextGen-Secret: ${t.webhook_secret}"` : "";
    const cmd = `curl -X POST "${url}"${secretHeader} -H "Content-Type: application/json" -d '{"question": "Hello NextGen"}'`;
    navigator.clipboard.writeText(cmd);
    setCopiedId(t.id);
    setTimeout(() => setCopiedId(null), 2000);
  }

  if (!open) return null;

  return (
    <div className="ng-code-overlay" onClick={onClose} role="presentation">
      <div
        className="ng-cred-modal"
        style={{ width: "680px", maxHeight: "85vh", display: "flex", flexDirection: "column" }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Automation Triggers Manager"
      >
        {/* Header */}
        <div className="ng-code-modal-header">
          <strong>⚡ Automation Triggers (Webhooks & Cron)</strong>
          <button onClick={onClose} aria-label="Close">
            ✕ Close
          </button>
        </div>

        {/* Success Toast */}
        {successMessage && <div className="ng-cred-toast">{successMessage}</div>}

        {/* List of Triggers */}
        <div className="ng-cred-list" style={{ maxHeight: "200px", overflowY: "auto" }}>
          {loading && triggers.length === 0 ? (
            <p className="ng-cred-empty">Loading…</p>
          ) : triggers.length === 0 ? (
            <p className="ng-cred-empty">No active triggers. Configure one below to automate workflows!</p>
          ) : (
            triggers.map((t) => (
              <div key={t.id} className="ng-cred-row" style={{ flexDirection: "column", alignItems: "flex-start" }}>
                <div style={{ display: "flex", width: "100%", justifyContent: "space-between", alignItems: "center" }}>
                  <span>
                    <strong>{t.workflow_name || t.workflow_id}</strong> —{" "}
                    <small style={{ color: t.trigger_type === "webhook" ? "#2563eb" : "#9333ea", fontWeight: "bold" }}>
                      {t.trigger_type.toUpperCase()}
                    </small>
                    {t.cron_expression && <code> ({t.cron_expression})</code>}
                  </span>
                  <div style={{ display: "flex", gap: "6px" }}>
                    {t.trigger_type === "webhook" && (
                      <button className="ng-cred-toggle" style={{ fontSize: "11px" }} onClick={() => copyCurl(t)}>
                        {copiedId === t.id ? "✓ Copied Curl!" : "📋 Copy Curl"}
                      </button>
                    )}
                    <button
                      className="ng-cred-delete"
                      onClick={() => handleDelete(t)}
                      disabled={deletingId === t.id}
                    >
                      {deletingId === t.id ? "Deleting…" : "Delete"}
                    </button>
                  </div>
                </div>
                {t.trigger_type === "webhook" && (
                  <div style={{ fontSize: "11px", color: "#666", marginTop: "4px" }}>
                    URL: <code>{getWebhookUrl(t.workflow_name)}</code>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Create Trigger Form */}
        <form
          className="ng-cred-form"
          onSubmit={handleCreate}
          style={{ flex: 1, display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}
        >
          <p className="ng-cred-form-title">Configure New Trigger</p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
            <div>
              <label htmlFor="ng-trigger-wf">Select Workflow</label>
              <select
                id="ng-trigger-wf"
                value={selectedWorkflowId}
                onChange={(e) => setSelectedWorkflowId(e.target.value)}
                disabled={submitting}
                style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
              >
                {workflows.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="ng-trigger-type">Trigger Type</label>
              <select
                id="ng-trigger-type"
                value={triggerType}
                onChange={(e) => setTriggerType(e.target.value as "webhook" | "cron")}
                disabled={submitting}
                style={{ width: "100%", padding: "6px", borderRadius: "4px" }}
              >
                <option value="webhook">HTTP Webhook Endpoint</option>
                <option value="cron">Recurring Cron Schedule</option>
              </select>
            </div>
          </div>

          {triggerType === "cron" ? (
            <div>
              <label htmlFor="ng-trigger-cron">Cron Expression (e.g. 0 9 * * * or */15 * * * *)</label>
              <div style={{ display: "flex", gap: "6px" }}>
                <input
                  id="ng-trigger-cron"
                  type="text"
                  placeholder="0 9 * * *"
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  disabled={submitting}
                />
                <button
                  type="button"
                  className="ng-cred-toggle"
                  style={{ fontSize: "11px" }}
                  onClick={() => setCronExpression("*/15 * * * *")}
                >
                  Every 15 mins
                </button>
                <button
                  type="button"
                  className="ng-cred-toggle"
                  style={{ fontSize: "11px" }}
                  onClick={() => setCronExpression("0 * * * *")}
                >
                  Hourly
                </button>
                <button
                  type="button"
                  className="ng-cred-toggle"
                  style={{ fontSize: "11px" }}
                  onClick={() => setCronExpression("0 9 * * *")}
                >
                  Daily 9am
                </button>
              </div>
            </div>
          ) : (
            <div>
              <label htmlFor="ng-trigger-secret">Webhook Verification Secret (Optional X-NextGen-Secret header)</label>
              <input
                id="ng-trigger-secret"
                type="text"
                placeholder="e.g. secret-token-123 (leave empty for open webhook)"
                value={webhookSecret}
                onChange={(e) => setWebhookSecret(e.target.value)}
                disabled={submitting}
              />
            </div>
          )}

          {error && <p className="ng-cred-error" role="alert">{error}</p>}

          <button type="submit" className="ng-cred-submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create Trigger"}
          </button>
        </form>
      </div>
    </div>
  );
}
