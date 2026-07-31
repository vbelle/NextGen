import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";

interface Credential {
  id: string;
  name: string;
  created_at: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
}

/** Extract the detail string from an ApiError body regardless of its shape. */
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

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export function CredentialManager({ open, onClose }: Props) {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(false);
  const [newName, setNewName] = useState("");
  const [newValue, setNewValue] = useState("");
  const [showValue, setShowValue] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  function load() {
    setLoading(true);
    api
      .listCredentials()
      .then((rows) => setCredentials(rows))
      .catch(() => setCredentials([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) {
      load();
      setError(null);
      setSuccessMessage(null);
      // Focus name input when modal opens
      setTimeout(() => nameInputRef.current?.focus(), 50);
    }
  }, [open]);

  function showSuccess(msg: string) {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    const value = newValue.trim();
    if (!name || !value) {
      setError("Both name and value are required.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await api.createCredential(name, value);
      setNewName("");
      setNewValue("");
      setShowValue(false);
      load();
      showSuccess(`✓ Credential "${name}" added`);
    } catch (err) {
      setError(extractDetail(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(cred: Credential) {
    if (
      !window.confirm(
        `Delete credential "${cred.name}"?\n\nThis cannot be undone. Any workflow using it will fail at run time.`,
      )
    )
      return;
    setError(null);
    setDeletingId(cred.id);
    try {
      await api.deleteCredential(cred.id);
      load();
      showSuccess(`✓ Credential "${cred.name}" deleted`);
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
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Credential Manager"
      >
        {/* Header */}
        <div className="ng-code-modal-header">
          <strong>🔑 Credentials</strong>
          <button onClick={onClose} aria-label="Close">
            ✕ Close
          </button>
        </div>

        {/* Success toast */}
        {successMessage && (
          <div className="ng-cred-toast">{successMessage}</div>
        )}

        {/* Credential list */}
        <div className="ng-cred-list">
          {loading && credentials.length === 0 ? (
            <p className="ng-cred-empty">Loading…</p>
          ) : credentials.length === 0 ? (
            <p className="ng-cred-empty">
              No credentials yet. Add one below.
            </p>
          ) : (
            credentials.map((cred) => (
              <div key={cred.id} className="ng-cred-row">
                <span className="ng-cred-name" title={cred.id}>
                  {cred.name}
                </span>
                <span className="ng-cred-date">
                  {formatDate(cred.created_at)}
                </span>
                <button
                  className="ng-cred-delete"
                  onClick={() => handleDelete(cred)}
                  disabled={deletingId === cred.id}
                  aria-label={`Delete credential ${cred.name}`}
                >
                  {deletingId === cred.id ? "Deleting…" : "Delete"}
                </button>
              </div>
            ))
          )}
        </div>

        {/* Add form */}
        <form className="ng-cred-form" onSubmit={handleCreate} noValidate>
          <p className="ng-cred-form-title">Add a new credential</p>
          <div>
            <label htmlFor="ng-cred-name-input">Name</label>
            <input
              id="ng-cred-name-input"
              ref={nameInputRef}
              type="text"
              placeholder="e.g. github-token, openai-key"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              disabled={submitting}
            />
          </div>
          <div>
            <label htmlFor="ng-cred-value-input">Value</label>
            <div className="ng-cred-value-row">
              <input
                id="ng-cred-value-input"
                type={showValue ? "text" : "password"}
                placeholder="Paste the secret value"
                value={newValue}
                onChange={(e) => setNewValue(e.target.value)}
                autoComplete="new-password"
                disabled={submitting}
              />
              <button
                type="button"
                className="ng-cred-toggle"
                onClick={() => setShowValue((v) => !v)}
                aria-label={showValue ? "Hide value" : "Show value"}
                title={showValue ? "Hide value" : "Show value"}
              >
                {showValue ? "🙈" : "👁"}
              </button>
            </div>
          </div>
          {error && <p className="ng-cred-error" role="alert">{error}</p>}
          <button
            type="submit"
            className="ng-cred-submit"
            disabled={submitting}
          >
            {submitting ? "Adding…" : "Add credential"}
          </button>
        </form>
      </div>
    </div>
  );
}
