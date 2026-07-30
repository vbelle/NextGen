import { useEffect, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  api,
  type WorkflowSummary,
  type WorkflowVersionSummary,
} from "../../api/client";

export interface SubworkflowNodeData {
  name: string;
  config: { workflow_id: string; pinned_version_id: string };
  onConfigChange: (config: SubworkflowNodeData["config"]) => void;
  [key: string]: unknown;
}

export function SubworkflowNode(props: NodeProps) {
  const data = props.data as unknown as SubworkflowNodeData;
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [versions, setVersions] = useState<WorkflowVersionSummary[]>([]);

  useEffect(() => {
    api
      .listWorkflows()
      .then(setWorkflows)
      .catch(() => setWorkflows([]));
  }, []);

  useEffect(() => {
    if (!data.config.workflow_id) {
      setVersions([]);
      return;
    }
    api
      .listVersions(data.config.workflow_id)
      .then(setVersions)
      .catch(() => setVersions([]));
  }, [data.config.workflow_id]);

  return (
    <div className="ng-node ng-node-subworkflow">
      <Handle type="target" position={Position.Top} />
      <div className="ng-node-title">Sub-workflow — {data.name}</div>
      <select
        value={data.config.workflow_id}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            workflow_id: e.target.value,
            pinned_version_id: "",
          })
        }
      >
        <option value="">Select a workflow…</option>
        {workflows.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </select>
      <select
        value={data.config.pinned_version_id}
        onChange={(e) =>
          data.onConfigChange({
            ...data.config,
            pinned_version_id: e.target.value,
          })
        }
        disabled={!data.config.workflow_id}
      >
        <option value="">Select a version to pin…</option>
        {versions.map((v) => (
          <option key={v.id} value={v.id}>
            v{v.version_number}
          </option>
        ))}
      </select>
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
