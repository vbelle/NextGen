import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface ResponseNodeData {
  name: string;
  config: { content: string };
  onConfigChange: (config: { content: string }) => void;
  [key: string]: unknown;
}

export function ResponseNode(props: NodeProps) {
  const data = props.data as unknown as ResponseNodeData;
  return (
    <div className="ng-node ng-node-response">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Response — {data.name}</div>
      <textarea
        value={data.config.content}
        placeholder="Shown to the chat user — use {{previous}} or {{variable}}"
        onChange={(e) => data.onConfigChange({ content: e.target.value })}
        rows={2}
      />
      {/* Terminal node type — no source handle (contracts/graph-schema.md) */}
    </div>
  );
}
