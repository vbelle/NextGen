import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface InputNodeData {
  name: string;
  config: { prompt: string; required?: boolean };
  onConfigChange: (config: { prompt: string; required?: boolean }) => void;
  [key: string]: unknown;
}

export function InputNode(props: NodeProps) {
  const data = props.data as unknown as InputNodeData;
  return (
    <div className="ng-node ng-node-input">
      <div className="ng-node-title">Input — {data.name}</div>
      <textarea
        value={data.config.prompt}
        placeholder="Question shown in chat…"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, prompt: e.target.value })
        }
        rows={2}
      />
      <Handle type="source" position={Position.Bottom} id="default" />
    </div>
  );
}
