import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface CodeNodeData {
  name: string;
  config: { snippet: string; timeout_seconds?: number };
  onConfigChange: (config: CodeNodeData["config"]) => void;
  [key: string]: unknown;
}

export function CodeNode(props: NodeProps) {
  const data = props.data as unknown as CodeNodeData;
  return (
    <div className="ng-node ng-node-code">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Code — {data.name}</div>
      <textarea
        value={data.config.snippet}
        placeholder={
          "Python — sandboxed, no network/filesystem.\n" +
          "Use `previous` and `variables`, set `result = ...`"
        }
        onChange={(e) =>
          data.onConfigChange({ ...data.config, snippet: e.target.value })
        }
        rows={5}
        style={{ fontFamily: "monospace" }}
      />
      <input
        type="number"
        min={1}
        value={data.config.timeout_seconds ?? 60}
        placeholder="timeout (seconds)"
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            timeout_seconds: Number(e.target.value) || 60,
          })
        }
      />
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
