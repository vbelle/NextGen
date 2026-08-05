import { Handle, Position } from "@xyflow/react";

interface Props {
  id: string;
  data: {
    name?: string;
    config?: {
      destination?: "slack" | "email" | "file";
      content?: string;
      slack_webhook_url?: string;
      email_recipient?: string;
      email_subject?: string;
      file_format?: "markdown" | "html";
    };
    onConfigChange?: (config: Record<string, unknown>) => void;
  };
}

export function ExportNode({ data }: Props) {
  const cfg = data.config ?? {};
  const destination = cfg.destination ?? "file";
  const content = cfg.content ?? "{{previous}}";
  const slackWebhookUrl = cfg.slack_webhook_url ?? "";
  const emailRecipient = cfg.email_recipient ?? "";
  const emailSubject = cfg.email_subject ?? "NextGen Workflow Report";
  const fileFormat = cfg.file_format ?? "markdown";

  function update(patch: Record<string, unknown>) {
    data.onConfigChange?.({ ...cfg, ...patch });
  }

  return (
    <div className="ng-node">
      <Handle type="target" position={Position.Top} id="default" />
      <div className="ng-node-title">Export Node</div>

      <label style={{ fontSize: "10px", color: "#666" }}>Destination</label>
      <select
        value={destination}
        onChange={(e) => update({ destination: e.target.value })}
      >
        <option value="file">📁 File Export</option>
        <option value="slack">💬 Slack Webhook</option>
        <option value="email">✉️ Email Report</option>
      </select>

      <label style={{ fontSize: "10px", color: "#666", marginTop: "4px" }}>Content Template</label>
      <input
        type="text"
        placeholder="{{previous}}"
        value={content}
        onChange={(e) => update({ content: e.target.value })}
      />

      {destination === "slack" && (
        <>
          <label style={{ fontSize: "10px", color: "#666", marginTop: "4px" }}>Webhook URL</label>
          <input
            type="text"
            placeholder="https://hooks.slack.com/..."
            value={slackWebhookUrl}
            onChange={(e) => update({ slack_webhook_url: e.target.value })}
          />
        </>
      )}

      {destination === "email" && (
        <>
          <label style={{ fontSize: "10px", color: "#666", marginTop: "4px" }}>Recipient Email</label>
          <input
            type="text"
            placeholder="user@example.com"
            value={emailRecipient}
            onChange={(e) => update({ email_recipient: e.target.value })}
          />
          <input
            type="text"
            placeholder="Subject line"
            value={emailSubject}
            onChange={(e) => update({ email_subject: e.target.value })}
            style={{ marginTop: "2px" }}
          />
        </>
      )}

      {destination === "file" && (
        <>
          <label style={{ fontSize: "10px", color: "#666", marginTop: "4px" }}>Format</label>
          <select
            value={fileFormat}
            onChange={(e) => update({ file_format: e.target.value })}
          >
            <option value="markdown">Markdown (.md)</option>
            <option value="html">HTML (.html)</option>
          </select>
        </>
      )}

      <div className="ng-node-ports">
        <span style={{ color: "#2a7a2a" }}>● success</span>
        <span style={{ color: "crimson" }}>● failure</span>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="success"
        style={{ left: "30%" }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="failure"
        style={{ left: "70%" }}
      />
    </div>
  );
}
