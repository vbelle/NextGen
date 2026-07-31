import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface LoopNodeData {
  name: string;
  config: { collection_ref: string; body_start_node_id: string };
  onConfigChange: (config: LoopNodeData["config"]) => void;
  [key: string]: unknown;
}

export function LoopNode(props: NodeProps) {
  const data = props.data as unknown as LoopNodeData;
  return (
    <div className="ng-node ng-node-loop">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Loop — {data.name}</div>
      <input
        value={data.config.collection_ref}
        placeholder="{{previous}} or {{variable}} — must resolve to a list"
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            collection_ref: e.target.value,
          })
        }
      />
      <input
        value={data.config.body_start_node_id}
        placeholder="ID of the first body node"
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            body_start_node_id: e.target.value,
          })
        }
      />
      <div className="ng-node-hint">
        {"{{previous}}"} = the node connected above · {"{{name}}"} = a Variable
        node's value. Wire "body" to the first body node; wire the body's last
        node back to this Loop's id. Wire "done" onward once every item is
        processed.
      </div>
      <div className="ng-node-ports">
        <span className="ng-port-label">done</span>
        <span className="ng-port-label">body</span>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="done"
        style={{ left: "30%" }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="body"
        style={{ left: "70%" }}
      />
    </div>
  );
}
