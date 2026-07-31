import { useEffect, useRef, useState, FormEvent } from "react";
import { useChatSocket } from "./useChatSocket";
import { api, type WorkflowSummary } from "../api/client";

type Mode = "picker" | "chat";

export interface ChatSidecarProps {
  open: boolean;
  onClose: () => void;
  /** Set by e.g. a workflow list's "Run" button to immediately start a
   * specific workflow and switch straight to the transcript. */
  autoStartWorkflow?: string | null;
  onAutoStartHandled?: () => void;
  /** Fired whenever the run this chat session is currently on changes, so a
   * separate Logs sidecar (which doesn't own its own WebSocket connection)
   * knows which run to poll. */
  onRunIdChange?: (runId: string | null) => void;
}

export function ChatSidecar({
  open,
  onClose,
  autoStartWorkflow,
  onAutoStartHandled,
  onRunIdChange,
}: ChatSidecarProps) {
  const {
    transcript,
    pendingInput,
    connected,
    starting,
    currentRunId,
    startWorkflow,
    provideInput,
    clearTranscript,
  } = useChatSocket();

  useEffect(() => {
    onRunIdChange?.(currentRunId);
  }, [currentRunId, onRunIdChange]);
  const [mode, setMode] = useState<Mode>("picker");
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [draft, setDraft] = useState("");
  const autoStartedRef = useRef<string | null>(null);

  useEffect(() => {
    if (mode === "picker") {
      api
        .listWorkflows()
        .then(setWorkflows)
        .catch(() => setWorkflows([]));
    }
  }, [mode]);

  // A run that was already paused before this sidecar connected — drop
  // straight into the transcript instead of the picker.
  useEffect(() => {
    if (pendingInput?.resumed) {
      setMode("chat");
    }
  }, [pendingInput]);

  // Fired from outside (a workflow list's "Run" button): start that flow and
  // switch to the transcript immediately.
  useEffect(() => {
    if (
      open &&
      autoStartWorkflow &&
      autoStartedRef.current !== autoStartWorkflow
    ) {
      autoStartedRef.current = autoStartWorkflow;
      startWorkflow(autoStartWorkflow);
      setMode("chat");
      onAutoStartHandled?.();
    } else if (!autoStartWorkflow) {
      // Bug fix: without this, autoStartedRef kept every workflow name it had
      // ever auto-started for the sidecar's whole (now-permanent) lifetime.
      // Clicking "Run" a second time on the same workflow left the guard
      // above permanently false for that name — startWorkflow silently never
      // fired again, so the sidecar just opened with nothing happening.
      // Re-arm the guard as soon as the parent clears autoStartWorkflow
      // (which it does immediately after this effect consumes it), so the
      // same name can trigger a fresh run next time.
      autoStartedRef.current = null;
    }
  }, [open, autoStartWorkflow, startWorkflow, onAutoStartHandled]);

  function handlePickWorkflow(name: string) {
    startWorkflow(name);
    setMode("chat");
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || !pendingInput) return;
    setDraft("");
    provideInput(text);
  }

  return (
    <div className={`ng-chat-sidecar ${open ? "ng-chat-sidecar-open" : ""}`}>
      <div className="ng-chat-sidecar-header">
        {mode === "chat" && (
          <button
            className="ng-chat-back"
            onClick={() => setMode("picker")}
            title="Back to flow list"
          >
            ← Flows
          </button>
        )}
        <span className="ng-chat-sidecar-title">Chat</span>
        <span className="ng-chat-status">
          {connected ? "connected" : "connecting…"}
        </span>
        {mode === "chat" && transcript.length > 0 && (
          <button
            className="ng-chat-clear"
            onClick={clearTranscript}
            title="Clear this transcript (doesn't cancel a paused run)"
          >
            Clear
          </button>
        )}
        <button className="ng-chat-close" onClick={onClose} title="Close">
          ✕
        </button>
      </div>

      {mode === "picker" && (
        <div className="ng-chat-picker">
          <p className="ng-chat-picker-hint">Pick a workflow to start:</p>
          {workflows.length === 0 ? (
            <p className="ng-chat-picker-hint">No workflows yet.</p>
          ) : (
            <ul>
              {workflows.map((w) => (
                <li key={w.id}>
                  <button onClick={() => handlePickWorkflow(w.name)}>
                    {w.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {mode === "chat" && (
        <>
          <div className="ng-chat-transcript">
            {transcript.map((entry, i) => (
              <div key={i} className={`ng-chat-msg ng-chat-msg-${entry.role}`}>
                {entry.content}
              </div>
            ))}
            {starting && !pendingInput && (
              <div className="ng-chat-pending">Starting the flow…</div>
            )}
            {pendingInput && (
              <div className="ng-chat-pending">
                {pendingInput.resumed
                  ? "This run was already waiting on you from before — pick up where you left off."
                  : "Waiting for your reply…"}
              </div>
            )}
          </div>
          <form onSubmit={handleSubmit} className="ng-chat-input">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={
                pendingInput
                  ? "Your reply…"
                  : "No question pending — pick a flow to start a new chat"
              }
              disabled={!pendingInput}
              autoFocus
            />
            <button type="submit" disabled={!pendingInput}>
              Send
            </button>
          </form>
        </>
      )}
    </div>
  );
}
