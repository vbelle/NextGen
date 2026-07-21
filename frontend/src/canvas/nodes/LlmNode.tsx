import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface LlmNodeData {
  name: string;
  config: {
    provider: string;
    model: string;
    prompt: string;
    timeout_seconds?: number;
  };
  onConfigChange: (config: LlmNodeData["config"]) => void;
  [key: string]: unknown;
}

export function LlmNode(props: NodeProps) {
  const data = props.data as unknown as LlmNodeData;
  return (
    <div className="ng-node ng-node-llm">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">LLM — {data.name}</div>
      <input
        value={data.config.model}
        placeholder="model, e.g. llama3.2"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, model: e.target.value })
        }
      />
      <textarea
        value={data.config.prompt}
        placeholder="Prompt — use {{previous}} or {{variable}}"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, prompt: e.target.value })
        }
        rows={3}
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
