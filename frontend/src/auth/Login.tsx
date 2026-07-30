import { useState, FormEvent } from "react";
import { api, ApiError } from "../api/client";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.login(password);
      onSuccess();
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Incorrect password."
          : "Login failed.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      style={{ display: "flex", justifyContent: "center", marginTop: "20vh" }}
    >
      <form onSubmit={handleSubmit} style={{ width: 320 }}>
        <h1>NextGen</h1>
        <p>Enter the shared team password to continue.</p>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
          style={{ width: "100%", padding: 8, marginBottom: 8 }}
        />
        <button
          type="submit"
          disabled={submitting}
          style={{ width: "100%", padding: 8 }}
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
        {error && <p style={{ color: "crimson" }}>{error}</p>}
      </form>
    </div>
  );
}
