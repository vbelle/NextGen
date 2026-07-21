"""API node: makes an HTTP call, 2xx routes to success, everything else (non-2xx,
timeout, connection error, unresolved {{variable}}) routes to failure — FR-014,
FR-017, FR-018. See contracts/graph-schema.md.

Credential resolution (research.md §9): if `credential_id` is set, the decrypted
value is added as `Authorization: Bearer <value>` — unless the node's own `headers`
config already sets an `Authorization` header, in which case the explicit header
wins. This wasn't pinned down in the spec/contract beyond "credential resolution via
app/crypto.py", so Bearer-auth-by-default is a judgment call: it's the most common
case for the kind of external services a small team wires up, and it stays
overridable for anything that needs a different scheme (e.g. an API key header)."""

from __future__ import annotations

import httpx
from pydantic import BaseModel
from sqlmodel import Session

from app.crypto import decrypt
from app.db import get_engine
from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import render_template
from app.models.credential import Credential

DEFAULT_TIMEOUT_SECONDS = 60
_VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


class ApiConfig(BaseModel):
    method: str = "GET"
    url: str
    headers: dict[str, str] = {}
    body: str | None = None
    credential_id: str | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


def _resolve_credential(credential_id: str) -> str:
    with Session(get_engine()) as session:
        credential = session.get(Credential, credential_id)
        if credential is None:
            raise ValueError(f"Credential '{credential_id}' not found")
        return decrypt(credential.encrypted_value)


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = ApiConfig(**config)
    try:
        method = cfg.method.upper()
        if method not in _VALID_METHODS:
            raise ValueError(f"Unsupported HTTP method '{cfg.method}'")

        url = render_template(cfg.url, state)
        body = render_template(cfg.body, state) if cfg.body is not None else None
        headers = {key: render_template(value, state) for key, value in cfg.headers.items()}

        if cfg.credential_id and not any(k.lower() == "authorization" for k in headers):
            token = _resolve_credential(cfg.credential_id)
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            response = await client.request(method, url, headers=headers, content=body)

        try:
            parsed_body = response.json()
        except ValueError:
            parsed_body = response.text

        output = {"status_code": response.status_code, "body": parsed_body}

        if 200 <= response.status_code < 300:
            return {
                "node_outputs": {node_id: output, "__latest__": output},
                "last_output_port": {node_id: "success"},
            }
        return {
            "node_outputs": {node_id: output, "__latest__": output},
            "last_output_port": {node_id: "failure"},
        }
    except Exception as exc:  # noqa: BLE001 — any failure (timeout, connection error, unresolved
        # variable, bad credential, unsupported method) routes to failure output,
        # matching llm_node.py's broad-catch convention for DUAL_OUTPUT_TYPES.
        error = {"error": str(exc)}
        return {
            "node_outputs": {node_id: error, "__latest__": error},
            "last_output_port": {node_id: "failure"},
        }


register_node_type("api", ApiConfig, execute)
