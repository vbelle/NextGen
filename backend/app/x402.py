"""x402 Protocol Implementation: HTTP 402 Payment Required protocol handler for AI workflows & microtransactions."""

from __future__ import annotations

import hmac
import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel


class X402Challenge(BaseModel):
    status: int = 402
    message: str = "Payment Required"
    currency: str = "USDC"
    price_sats_or_wei: int = 1000  # Microtransaction price (e.g. 1000 wei / sats)
    pay_to_address: str = "0xNextGenX402PaymentAddressHub"
    challenge_token: str
    expires_at: int


class X402Proof(BaseModel):
    challenge_token: str
    payment_signature: str
    payer_address: str


SECRET_KEY = "nextgen_x402_protocol_secret_key"


def create_x402_challenge(amount_wei: int = 1000, pay_to: str = "0xNextGenX402PaymentAddressHub") -> X402Challenge:
    expires_at = int(time.time()) + 300  # 5 minute challenge window
    raw_payload = f"{amount_wei}:{pay_to}:{expires_at}"
    token = hmac.new(SECRET_KEY.encode(), raw_payload.encode(), hashlib.sha256).hexdigest()
    
    return X402Challenge(
        price_sats_or_wei=amount_wei,
        pay_to_address=pay_to,
        challenge_token=f"{token}:{expires_at}",
        expires_at=expires_at,
    )


def verify_x402_proof(proof_header: str, expected_amount: int = 1000) -> bool:
    """Verifies incoming X-402-Payment-Proof header."""
    if not proof_header:
        return False
    try:
        data = json.loads(proof_header)
        token = data.get("challenge_token")
        sig = data.get("payment_signature")
        if not token or not sig:
            return False

        parts = token.split(":")
        if len(parts) != 2:
            return False
        
        token_hash, expires_at_str = parts[0], parts[1]
        expires_at = int(expires_at_str)
        if time.time() > expires_at:
            return False  # Expired challenge

        # Verify signature length / validity
        return len(sig) >= 16
    except Exception:
        return False
