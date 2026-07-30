import { useEffect, useState } from "react";
import { Login } from "./auth/Login";
import { WorkflowList } from "./workflows/WorkflowList";
import { Canvas } from "./canvas/Canvas";
import { ChatSidecar } from "./chat/ChatSidecar";
import { api, ApiError, type WorkflowDetail } from "./api/client";

type View = { name: "list" } | { name: "builder"; workflowId?: string };

export function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [view, setView] = useState<View>({ name: "list" });
  const [workflowDetail, setWorkflowDetail] = useState<
    WorkflowDetail | undefined
  >(undefined);
  const [chatOpen, setChatOpen] = useState(false);
  const [autoStartWorkflow, setAutoStartWorkflow] = useState<string | null>(
    null,
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

  function reloadWorkflowDetail(workflowId: string) {
    api.getWorkflow(workflowId).then(setWorkflowDetail);
  }

  useEffect(() => {
    if (view.name === "builder" && view.workflowId) {
      reloadWorkflowDetail(view.workflowId);
    } else if (view.name === "builder") {
      setWorkflowDetail(undefined);
    }
  }, [view]);

  if (authenticated === null) return <p>Loading…</p>;
  if (!authenticated) return <Login onSuccess={() => setAuthenticated(true)} />;

  return (
    <div className="ng-app">
      <nav className="ng-nav">
        <strong>NextGen</strong>
        <button onClick={() => setView({ name: "list" })}>Workflows</button>
        <button onClick={() => setChatOpen((v) => !v)}>
          {chatOpen ? "Close chat" : "Chat"}
        </button>
      </nav>
      <main className="ng-main">
        {view.name === "list" && (
          <WorkflowList
            onOpenBuilder={(workflowId) =>
              setView({ name: "builder", workflowId })
            }
            onOpenChat={() => setChatOpen(true)}
            onRunWorkflow={(name) => {
              setAutoStartWorkflow(name);
              setChatOpen(true);
            }}
          />
        )}
        {view.name === "builder" && (
          <Canvas
            key={workflowDetail?.active_version_id ?? view.workflowId ?? "new"}
            workflowId={view.workflowId}
            initialGraph={workflowDetail?.graph_json ?? undefined}
            activeVersionId={workflowDetail?.active_version_id ?? null}
            onSaved={() => setView({ name: "list" })}
            onReverted={() =>
              view.workflowId && reloadWorkflowDetail(view.workflowId)
            }
          />
        )}
      </main>
      <ChatSidecar
        open={chatOpen}
        onClose={() => setChatOpen(false)}
        autoStartWorkflow={autoStartWorkflow}
        onAutoStartHandled={() => setAutoStartWorkflow(null)}
      />
    </div>
  );
}
