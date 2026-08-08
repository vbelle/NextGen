import { Handle, Position } from "@xyflow/react";

export function X402PaywallNode({
  data,
}: {
  data: {
    name?: string;
    config?: { price_wei?: number; pay_to_address?: string };
    onConfigChange?: (config: Record<string, unknown>) => void;
  };
}) {
  const price = data.config?.price_wei ?? 1000;
  const payTo = data.config?.pay_to_address ?? "0xNextGenX402PaymentAddressHub";

  return (
    <div className="ng-node ng-node-x402-paywall" style={{ border: "2px solid #eab308", background: "#fefce8", padding: "10px", borderRadius: "8px", minWidth: "180px" }}>
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: "bold", color: "#854d0e", marginBottom: "6px" }}>
        💳 x402 Paywall
      </div>
      <div style={{ fontSize: "11px", color: "#a16207" }}>
        <div><strong>Price:</strong> {price} wei/sats</div>
        <div style={{ textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", maxWidth: "160px" }}>
          <strong>Pay To:</strong> {payTo}
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", marginTop: "8px", color: "#854d0e" }}>
        <span>success</span>
        <span>payment_required</span>
      </div>
      <Handle type="source" position={Position.Bottom} id="success" style={{ left: "30%" }} />
      <Handle type="source" position={Position.Bottom} id="payment_required" style={{ left: "70%", background: "#ef4444" }} />
    </div>
  );
}
