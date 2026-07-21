import { useEffect, useRef, useState, useCallback } from "react";
import {
  connectChat,
  sendChatMessage,
  type ChatServerMessage,
} from "../api/client";

export interface ChatTranscriptEntry {
  role: "user" | "system";
  content: string;
  runId: string | null;
}

export interface PendingInput {
  runId: string;
  prompt: string;
  /** True when this prompt arrived as part of reconnect replay (FR-011) —
   * i.e. it was already waiting before this connection opened, rather than
   * being reached live during this session. Lets the UI say "this was
   * already paused" instead of implying the question just now appeared. */
  resumed: boolean;
}

const SESSION_STORAGE_KEY = "nextgen_chat_session_id";

export function useChatSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const [transcript, setTranscript] = useState<ChatTranscriptEntry[]>([]);
  const [pendingInput, setPendingInput] = useState<PendingInput | null>(null);
  const [connected, setConnected] = useState(false);
  // The server always sends "history" first on connect, then — only if a run
  // tied to this session is already paused — an "input_request" as the very
  // next message, before any live interaction. That ordering is what lets us
  // tell "resumed from a previous session" apart from "just paused live".
  const justConnectedRef = useRef(true);

  useEffect(() => {
    const sessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
    const ws = connectChat(sessionId, (msg: ChatServerMessage) => {
      switch (msg.type) {
        case "history": {
          justConnectedRef.current = true;
          sessionStorage.setItem(SESSION_STORAGE_KEY, msg.payload.session_id);
          setTranscript(
            msg.payload.messages.map((m) => ({
              role: m.role as "user" | "system",
              content: m.content,
              runId: m.run_id,
            })),
          );
          break;
        }
        case "status":
          justConnectedRef.current = false;
          break; // "working…" indicator could hook in here later
        case "input_request": {
          const resumed = justConnectedRef.current;
          justConnectedRef.current = false;
          setPendingInput({
            runId: msg.payload.run_id,
            prompt: msg.payload.prompt,
            resumed,
          });
          setTranscript((t) => [
            ...t,
            {
              role: "system",
              content: msg.payload.prompt,
              runId: msg.payload.run_id,
            },
          ]);
          break;
        }
        case "response":
          justConnectedRef.current = false;
          setPendingInput(null);
          setTranscript((t) => [
            ...t,
            {
              role: "system",
              content: String(msg.payload.content),
              runId: msg.payload.run_id,
            },
          ]);
          break;
        case "run_failed":
          justConnectedRef.current = false;
          setPendingInput(null);
          setTranscript((t) => [
            ...t,
            {
              role: "system",
              content: `⚠ ${msg.payload.message}`,
              runId: msg.payload.run_id,
            },
          ]);
          break;
        case "workflow_not_found":
          justConnectedRef.current = false;
          setTranscript((t) => [
            ...t,
            {
              role: "system",
              content: `No workflow named "${msg.payload.name}".`,
              runId: null,
            },
          ]);
          break;
      }
    });
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  const startWorkflow = useCallback((name: string) => {
    if (!wsRef.current) return;
    setTranscript((t) => [
      ...t,
      { role: "user", content: `start ${name}`, runId: null },
    ]);
    sendChatMessage(wsRef.current, {
      type: "start_workflow",
      payload: { name },
    });
  }, []);

  const provideInput = useCallback(
    (value: string) => {
      if (!wsRef.current || !pendingInput) return;
      setTranscript((t) => [
        ...t,
        { role: "user", content: value, runId: pendingInput.runId },
      ]);
      sendChatMessage(wsRef.current, {
        type: "provide_input",
        payload: { run_id: pendingInput.runId, value },
      });
      setPendingInput(null);
    },
    [pendingInput],
  );

  return { transcript, pendingInput, connected, startWorkflow, provideInput };
}
