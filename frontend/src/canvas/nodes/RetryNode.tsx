import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface RetryNodeData {
  name: string;
  config: { max_attempts: number };
  onConfigChange: (config: { max_attempts: number }) => void;
  [key: string]: unknown;
}

export function RetryNode(props: NodeProps) {
  const data = props.data as unknown as RetryNodeData;
  return (
    <div className="ng-node ng-node-retry">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Retry — {data.name}</div>
      <input
        type="number"
        min={1}
        value={data.config.max_attempts}
        placeholder="max attempts"
        onChange={(e) =>
          data.onConfigChange({ max_attempts: Number(e.target.value) || 1 })
        }
      />
      <p style={{ fontSize: 11, color: "#666", margin: "4px 0 0" }}>
        Wire "retry" back to the node that failed into this one; wire "give-up"
        onward once attempts are exhausted.
      </p>
      <div className="ng-node-ports">
        <span className="ng-port-label">give-up</span>
        <span className="ng-port-label">retry</span>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="give-up"
        style={{ left: "30%" }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="retry"
        style={{ left: "70%" }}
      />
    </div>
  );
}
