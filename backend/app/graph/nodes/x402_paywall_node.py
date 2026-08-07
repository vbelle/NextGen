"""x402 Paywall Node implementation: Enforces HTTP 402 micro-payment authorization inside visual graphs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.x402 import create_x402_challenge, verify_x402_proof


class X402PaywallConfig(BaseModel):
    price_wei: int = Field(default=1000, description="Required microtransaction price in wei/sats")
    pay_to_address: str = Field(default="0xNextGenX402PaymentAddressHub", description="Payment recipient address")


async def execute(node_id: str, config: dict[str, Any], state: GraphState) -> dict[str, Any]:
    cfg = X402PaywallConfig(**config)
    proof_header = state.get("variables", {}).get("x402_payment_proof") or state.get("node_outputs", {}).get("__x402_proof__")

    if not proof_header or not verify_x402_proof(str(proof_header), cfg.price_wei):
        challenge = create_x402_challenge(cfg.price_wei, cfg.pay_to_address)
        return {
            "node_outputs": {
                node_id: challenge.model_dump(),
                "__latest__": challenge.model_dump(),
            },
            "last_output_port": {node_id: "payment_required"},
        }

    return {
        "node_outputs": {
            node_id: {"paid": True, "status": "authorized"},
            "__latest__": "x402 Payment Authorized",
        },
        "last_output_port": {node_id: "success"},
    }


register_node_type("x402_paywall", X402PaywallConfig, execute)
