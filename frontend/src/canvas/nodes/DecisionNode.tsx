import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface DecisionNodeData {
  name: string;
  config: {
    left: string;
    operator: "equals" | "contains" | "gt" | "lt" | "truthy";
    right?: string;
  };
  onConfigChange: (config: DecisionNodeData["config"]) => void;
  [key: string]: unknown;
}

const OPERATORS: DecisionNodeData["config"]["operator"][] = [
  "equals",
  "contains",
  "gt",
  "lt",
  "truthy",
];

export function DecisionNode(props: NodeProps) {
  const data = props.data as unknown as DecisionNodeData;
  const needsRight = data.config.operator !== "truthy";

  return (
    <div className="ng-node ng-node-decision">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Decision — {data.name}</div>
      <input
        value={data.config.left}
        placeholder="{{previous}} or {{variable}}"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, left: e.target.value })
        }
      />
      <select
        value={data.config.operator}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            operator: e.target.value as DecisionNodeData["config"]["operator"],
          })
        }
      >
        {OPERATORS.map((op) => (
          <option key={op} value={op}>
            {op}
          </option>
        ))}
      </select>
      {needsRight && (
        <input
          value={data.config.right ?? ""}
          placeholder="value to compare against"
          onChange={(e) =>
            data.onConfigChange({ ...data.config, right: e.target.value })
          }
        />
      )}
      <div className="ng-node-ports">
        <span className="ng-port-label">false</span>
        <span className="ng-port-label">true</span>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        style={{ left: "30%" }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        style={{ left: "70%" }}
      />
    </div>
  );
}
