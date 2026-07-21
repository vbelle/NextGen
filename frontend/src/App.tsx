import { useEffect, useState } from "react";
import { Login } from "./auth/Login";
import { WorkflowList } from "./workflows/WorkflowList";
import { Canvas } from "./canvas/Canvas";
import { ChatWindow } from "./chat/ChatWindow";
import { api, ApiError, type GraphJson } from "./api/client";

type View =
  | { name: "list" }
  | { name: "builder"; workflowId?: string }
  | { name: "chat" };

export function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [view, setView] = useState<View>({ name: "list" });
  const [initialGraph, setInitialGraph] = useState<GraphJson | undefined>(
    undefined,
  );

  useEffect(() => {
    // Any authenticated-only GET tells us whether the session cookie is valid.
    api
      .listWorkflows()
      .then(() => setAuthenticated(true))
      .catch((err) =>
        setAuthenticated(!(err instanceof ApiError && err.status === 401)),
      );
  }, []);

  useEffect(() => {
    if (view.name === "builder" && view.workflowId) {
      api
        .getWorkflow(view.workflowId)
        .then((wf) => setInitialGraph(wf.graph_json ?? undefined));
    } else if (view.name === "builder") {
      setInitialGraph(undefined);
    }
  }, [view]);

  if (authenticated === null) return <p>Loading…</p>;
  if (!authenticated) return <Login onSuccess={() => setAuthenticated(true)} />;

  return (
    <div className="ng-app">
      <nav className="ng-nav">
        <strong>NextGen</strong>
        <button onClick={() => setView({ name: "list" })}>Workflows</button>
        <button onClick={() => setView({ name: "chat" })}>Chat</button>
      </nav>
      <main className="ng-main">
        {view.name === "list" && (
          <WorkflowList
            onOpenBuilder={(workflowId) =>
              setView({ name: "builder", workflowId })
            }
            onOpenChat={() => setView({ name: "chat" })}
          />
        )}
        {view.name === "builder" && (
          <Canvas
            workflowId={view.workflowId}
            initialGraph={initialGraph}
            onSaved={() => setView({ name: "list" })}
          />
        )}
        {view.name === "chat" && <ChatWindow />}
      </main>
    </div>
  );
}
