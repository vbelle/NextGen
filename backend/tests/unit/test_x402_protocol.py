"""Unit tests for x402 Protocol Implementation."""

import json
import pytest

from app.graph.nodes import x402_paywall_node
from app.x402 import create_x402_challenge, verify_x402_proof


def test_create_and_verify_x402_challenge():
    challenge = create_x402_challenge(amount_wei=5000, pay_to="0xTestRecipient")
    assert challenge.status == 402
    assert challenge.price_sats_or_wei == 5000
    assert challenge.pay_to_address == "0xTestRecipient"

    valid_proof = json.dumps({
        "challenge_token": challenge.challenge_token,
        "payment_signature": "0x1234567890abcdef1234567890abcdef",
        "payer_address": "0xPayerAddress"
    })

    assert verify_x402_proof(valid_proof, 5000) is True
    assert verify_x402_proof("", 5000) is False


@pytest.mark.asyncio
async def test_x402_paywall_node_execution():
    state_without_payment = {"variables": {}, "node_outputs": {}}
    result_402 = await x402_paywall_node.execute("paywall-1", {"price_wei": 2000}, state_without_payment)

    assert result_402["last_output_port"]["paywall-1"] == "payment_required"
    assert result_402["node_outputs"]["paywall-1"]["status"] == 402

    challenge = create_x402_challenge(amount_wei=2000)
    valid_proof = json.dumps({
        "challenge_token": challenge.challenge_token,
        "payment_signature": "0x1234567890abcdef1234567890abcdef",
        "payer_address": "0xPayerAddress"
    })

    state_with_payment = {"variables": {"x402_payment_proof": valid_proof}, "node_outputs": {}}
    result_authorized = await x402_paywall_node.execute("paywall-1", {"price_wei": 2000}, state_with_payment)

    assert result_authorized["last_output_port"]["paywall-1"] == "success"
    assert result_authorized["node_outputs"]["paywall-1"]["paid"] is True
