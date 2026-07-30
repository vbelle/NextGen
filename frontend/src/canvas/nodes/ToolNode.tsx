import { useEffect, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { api } from "../../api/client";

export interface ToolNodeData {
  name: string;
  config: {
    function_name: string;
    description: string;
    implementation_ref: string;
  };
  onConfigChange: (config: ToolNodeData["config"]) => void;
  [key: string]: unknown;
}

// No target Handle — a Tool node is never an edge's target (it's invoked
// directly by an LLM node via function-calling, not traversed like other
// nodes; see backend/app/graph/nodes/tool_node.py). Connect its one output
// handle to the LLM node that should be able to call it.
export function ToolNode(props: NodeProps) {
  const data = props.data as unknown as ToolNodeData;
  const [refs, setRefs] = useState<{ implementation_ref: string }[]>([]);

  useEffect(() => {
    api
      .listToolImplementations()
      .then(setRefs)
      .catch(() => setRefs([]));
  }, []);

  return (
    <div className="ng-node ng-node-tool">
      <div className="ng-node-title">Tool — {data.name}</div>
      <input
        value={data.config.function_name}
        placeholder="function_name, e.g. add"
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            function_name: e.target.value,
          })
        }
      />
      <textarea
        value={data.config.description}
        placeholder="Description shown to the LLM for function-calling"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, description: e.target.value })
        }
        rows={2}
      />
      <select
        value={data.config.implementation_ref}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            implementation_ref: e.target.value,
          })
        }
      >
        <option value="">Select an implementation…</option>
        {refs.map((r) => (
          <option key={r.implementation_ref} value={r.implementation_ref}>
            {r.implementation_ref}
          </option>
        ))}
      </select>
      <Handle type="source" position={Position.Bottom} id="default" />
    </div>
  );
}
