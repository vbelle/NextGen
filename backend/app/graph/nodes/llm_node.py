"""LLM node: calls a model through the provider-agnostic layer (Constitution V),
dual success/failure output (FR-017), configurable execution timeout (FR-018)."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import render_template
from app.providers.ollama_provider import OllamaProvider

DEFAULT_TIMEOUT_SECONDS = 60


class LlmConfig(BaseModel):
    provider: str = "ollama"
    model: str
    prompt: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


def _get_provider(name: str):
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unknown LLM provider '{name}' (Constitution V: add a class, not a rewrite)")


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    cfg = LlmConfig(**config)
    try:
        rendered_prompt = render_template(cfg.prompt, state)
        provider = _get_provider(cfg.provider)
        output = await asyncio.wait_for(
            provider.generate(model=cfg.model, prompt=rendered_prompt), timeout=cfg.timeout_seconds
        )
        return {
            "node_outputs": {node_id: output, "__latest__": output},
            "last_output_port": {node_id: "success"},
        }
    except (
        Exception
    ) as exc:  # noqa: BLE001 — any failure (timeout, unresolved variable, provider error) routes to failure output
        error = {"error": str(exc)}
        return {
            "node_outputs": {node_id: error, "__latest__": error},
            "last_output_port": {node_id: "failure"},
        }


register_node_type("llm", LlmConfig, execute)
