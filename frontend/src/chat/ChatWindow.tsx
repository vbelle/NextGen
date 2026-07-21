import { useState, FormEvent } from "react";
import { useChatSocket } from "./useChatSocket";

export function ChatWindow() {
  const { transcript, pendingInput, connected, startWorkflow, provideInput } =
    useChatSocket();
  const [draft, setDraft] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    if (pendingInput) {
      provideInput(text);
    } else {
      // A bare word is treated as "start this workflow by name" — the whole
      // point of Constitution II: chat is the only way to run a workflow.
      startWorkflow(text);
    }
  }

  return (
    <div className="ng-chat">
      <div className="ng-chat-status">
        {connected ? "connected" : "connecting…"}
      </div>
      <div className="ng-chat-transcript">
        {transcript.map((entry, i) => (
          <div key={i} className={`ng-chat-msg ng-chat-msg-${entry.role}`}>
            {entry.content}
          </div>
        ))}
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
            pendingInput ? "Your reply…" : "Type a workflow name to run it…"
          }
          autoFocus
        />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
