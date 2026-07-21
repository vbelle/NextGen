import { useEffect, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { api } from "../../api/client";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;

export interface ApiNodeData {
  name: string;
  config: {
    method: (typeof METHODS)[number];
    url: string;
    headers: Record<string, string>;
    body?: string;
    credential_id?: string | null;
    timeout_seconds?: number;
  };
  onConfigChange: (config: ApiNodeData["config"]) => void;
  [key: string]: unknown;
}

export function ApiNode(props: NodeProps) {
  const data = props.data as unknown as ApiNodeData;
  const [credentials, setCredentials] = useState<
    { id: string; name: string }[]
  >([]);

  useEffect(() => {
    api
      .listCredentials()
      .then(setCredentials)
      .catch(() => setCredentials([]));
  }, []);

  const headersText = Object.entries(data.config.headers ?? {})
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");

  function parseHeaders(text: string): Record<string, string> {
    const headers: Record<string, string> = {};
    for (const line of text.split("\n")) {
      const idx = line.indexOf(":");
      if (idx === -1) continue;
      const key = line.slice(0, idx).trim();
      const value = line.slice(idx + 1).trim();
      if (key) headers[key] = value;
    }
    return headers;
  }

  return (
    <div className="ng-node ng-node-api">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">API — {data.name}</div>
      <select
        value={data.config.method}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            method: e.target.value as ApiNodeData["config"]["method"],
          })
        }
      >
        {METHODS.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <input
        value={data.config.url}
        placeholder="https://... — supports {{variables}}"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, url: e.target.value })
        }
      />
      <textarea
        value={headersText}
        placeholder={"Header: value\n(one per line)"}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            headers: parseHeaders(e.target.value),
          })
        }
        rows={2}
      />
      <textarea
        value={data.config.body ?? ""}
        placeholder="Request body — supports {{variables}}"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, body: e.target.value })
        }
        rows={2}
      />
      <select
        value={data.config.credential_id ?? ""}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            credential_id: e.target.value || null,
          })
        }
      >
        <option value="">No credential</option>
        {credentials.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>
      <div className="ng-node-ports">
        <span className="ng-port-label">success</span>
        <span className="ng-port-label">failure</span>
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
