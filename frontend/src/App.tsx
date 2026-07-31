import { useEffect, useState } from "react";
import { Login } from "./auth/Login";
import { WorkflowList } from "./workflows/WorkflowList";
import { Canvas } from "./canvas/Canvas";
import { ChatSidecar } from "./chat/ChatSidecar";
import { LogsSidecar } from "./chat/LogsSidecar";
import { CredentialManager } from "./credentials/CredentialManager";
import { api, ApiError, type WorkflowDetail } from "./api/client";

type View = { name: "list" } | { name: "builder"; workflowId?: string };

export function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [view, setView] = useState<View>({ name: "list" });
  const [workflowDetail, setWorkflowDetail] = useState<
    WorkflowDetail | undefined
  >(undefined);
  const [chatOpen, setChatOpen] = useState(false);
  const [logsOpen, setLogsOpen] = useState(false);
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
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
        <button onClick={() => setLogsOpen((v) => !v)}>
          {logsOpen ? "Close logs" : "Logs"}
        </button>
        <button onClick={() => setCredentialsOpen(true)}>Credentials</button>
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
            onSaved={(savedWorkflowId) => {
              // Only re-point the view (which reloads workflowDetail and,
              // via Canvas's `key`, remounts the builder) when the id
              // actually changed — i.e. this was a brand-new workflow's
              // first save. Resaving an already-open workflow shouldn't
              // reload/remount anything, so the "Saved" toast and version
              // history refresh Canvas already handles locally aren't cut
              // short.
              if (
                view.name === "builder" &&
                view.workflowId !== savedWorkflowId
              ) {
                setView({ name: "builder", workflowId: savedWorkflowId });
              }
            }}
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
        onRunIdChange={setActiveRunId}
      />
      <LogsSidecar
        open={logsOpen}
        onClose={() => setLogsOpen(false)}
        runId={activeRunId}
        pushLeft={chatOpen}
      />
      <CredentialManager
        open={credentialsOpen}
        onClose={() => setCredentialsOpen(false)}
      />
    </div>
  );
}
