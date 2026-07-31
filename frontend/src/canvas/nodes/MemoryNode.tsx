import { useEffect, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { api } from "../../api/client";

export interface MemoryNodeData {
  name: string;
  config: { vector_store_ref: string; query: string; top_k: number };
  onConfigChange: (config: MemoryNodeData["config"]) => void;
  [key: string]: unknown;
}

export function MemoryNode(props: NodeProps) {
  const data = props.data as unknown as MemoryNodeData;
  const [stores, setStores] = useState<{ name: string }[]>([]);

  useEffect(() => {
    api
      .listVectorStores()
      .then(setStores)
      .catch(() => setStores([]));
  }, []);

  return (
    <div className="ng-node ng-node-memory">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Memory — {data.name}</div>
      <select
        value={data.config.vector_store_ref}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            vector_store_ref: e.target.value,
          })
        }
      >
        <option value="">Select a vector store…</option>
        {stores.map((s) => (
          <option key={s.name} value={s.name}>
            {s.name}
          </option>
        ))}
      </select>
      <textarea
        value={data.config.query}
        placeholder="Query — supports {{previous}} or {{variable}}"
        onChange={(e) =>
          data.onConfigChange({ ...data.config, query: e.target.value })
        }
        rows={2}
      />
      <div className="ng-node-hint">
        {"{{previous}}"} = the node connected above · {"{{name}}"} = a Variable
        node's value
      </div>
      <input
        type="number"
        min={1}
        value={data.config.top_k}
        placeholder="top_k"
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            top_k: Number(e.target.value) || 1,
          })
        }
      />
      <Handle type="source" position={Position.Bottom} id="default" />
    </div>
  );
}
