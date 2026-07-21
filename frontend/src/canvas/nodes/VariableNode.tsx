import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface VariableNodeData {
  name: string;
  config: { name: string };
  onConfigChange: (config: { name: string }) => void;
  [key: string]: unknown;
}

export function VariableNode(props: NodeProps) {
  const data = props.data as unknown as VariableNodeData;
  return (
    <div className="ng-node ng-node-variable">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Variable — {data.name}</div>
      <input
        value={data.config.name}
        placeholder="unique name, e.g. username"
        onChange={(e) => data.onConfigChange({ name: e.target.value })}
      />
      <p style={{ fontSize: 11, color: "#666", margin: "4px 0 0" }}>
        Saves whatever this node receives ({"{{previous}}"}) — readable later
        anywhere as {"{{"}
        {data.config.name || "name"}
        {"}}"}.
      </p>
      <Handle type="source" position={Position.Bottom} id="default" />
    </div>
  );
}
