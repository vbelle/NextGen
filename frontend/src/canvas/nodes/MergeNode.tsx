import { Handle, Position, type NodeProps } from "@xyflow/react";

export interface MergeNodeData {
  name: string;
  config: { strategy: string };
  onConfigChange: (config: MergeNodeData["config"]) => void;
  [key: string]: unknown;
}

// One target Handle, same as every other node — React Flow already lets
// multiple edges land on a single handle with no extra config, which is
// exactly what a Merge node needs: wire in as many parallel branches as you
// like. The compiler figures out which node_ids those are from the edges
// themselves at compile time (see app/graph/compiler.py's
// _resolve_merge_inputs) — nothing to configure here for that part.
export function MergeNode(props: NodeProps) {
  const data = props.data as unknown as MergeNodeData;
  return (
    <div className="ng-node ng-node-merge">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Merge — {data.name}</div>
      <select
        value={data.config.strategy}
        onChange={(e) =>
          data.onConfigChange({ ...data.config, strategy: e.target.value })
        }
      >
        <option value="combine-object">combine-object</option>
        <option value="concat-list">concat-list</option>
      </select>
      <div className="ng-node-hint">
        Waits for every wired-in branch to finish, then combines their outputs.
        combine-object merges dict outputs into one object (non-dict branches
        keyed by node id); concat-list flattens list outputs into one list
        (non-list branches appended as items).
      </div>
      <Handle type="source" position={Position.Bottom} id="default" />
    </div>
  );
}
