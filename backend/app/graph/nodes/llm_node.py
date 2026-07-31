"""LLM node: calls a model through the provider-agnostic layer (Constitution V),
dual success/failure output (FR-017), configurable execution timeout (FR-018).

User Story 11 (FR-016): an LLM node can be wired to one or more Tool nodes
(see app/graph/nodes/tool_node.py) via ordinary canvas edges. The compiler
resolves those edges into `bound_tools` on this node's config at compile time
(app/graph/compiler.py) — this module never sees graph_json directly, only
its own already-resolved config, same as every other node type. Each bound
tool is wrapped into a LangChain StructuredTool here (not in
app/providers/ollama_provider.py) specifically so the wrapper closure can
carry `run_id` and write its own NodeExecution audit row per invocation
(Constitution VII) — the provider stays a thin, audit-agnostic LLM wrapper,
consistent with Constitution V."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.db import get_engine
from app.graph.schema import register_node_type
from app.graph.state import GraphState
from app.graph.templating import render_template
from app.graph.tool_registry import get_tool_implementation
from app.logging import get_logger
from app.providers.ollama_provider import OllamaProvider
from app.runtime.audit import record_node_execution

logger = get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60


class BoundTool(BaseModel):
    node_id: str
    function_name: str
    description: str
    implementation_ref: str


class LlmConfig(BaseModel):
    provider: str = "ollama"
    model: str
    prompt: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    bound_tools: list[BoundTool] = Field(default_factory=list)


def _get_provider(name: str):
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unknown LLM provider '{name}' (Constitution V: add a class, not a rewrite)")


def _make_tool(binding: BoundTool, run_id: str | None) -> StructuredTool:
    impl = get_tool_implementation(binding.implementation_ref)

    def _run(**kwargs):
        started_at = datetime.now(timezone.utc)  # noqa: UP017
        logger.info("[TOOL ENTRY] node_id='%s' func='%s' impl_ref='%s' args=%s", binding.node_id, binding.function_name, binding.implementation_ref, kwargs)
        try:
            result = impl.func(**kwargs)
            logger.info("[TOOL EXIT SUCCESS] node_id='%s' func='%s' output_preview=%s", binding.node_id, binding.function_name, repr(str(result)[:150]))
        except Exception as exc:
            logger.error("[TOOL EXIT FAILURE] node_id='%s' func='%s' error=%s", binding.node_id, binding.function_name, exc, exc_info=True)
            raise

        if run_id:
            with Session(get_engine()) as session:
                record_node_execution(
                    session,
                    run_id=run_id,
                    node_id=binding.node_id,
                    node_type="tool",
                    output_port="default",
                    input_data=kwargs,
                    output_data=result,
                    started_at=started_at,
                )
        return result

    return StructuredTool.from_function(
        func=_run,
        name=binding.function_name,
        description=binding.description,
        args_schema=impl.args_schema,
    )


async def execute(node_id: str, config: dict, state: GraphState) -> dict:
    logger.info("Executing LLM node '%s'", node_id)
    cfg = LlmConfig(**config)
    try:
        rendered_prompt = render_template(cfg.prompt, state)
        provider = _get_provider(cfg.provider)
        run_id = state.get("run_id")
        tools = [_make_tool(binding, run_id) for binding in cfg.bound_tools] or None
        logger.info("Calling provider '%s' with model '%s' (tools=%s)", cfg.provider, cfg.model, len(tools) if tools else 0)
        output = await asyncio.wait_for(
            provider.generate(model=cfg.model, prompt=rendered_prompt, tools=tools),
            timeout=cfg.timeout_seconds,
        )
        logger.info("LLM node '%s' completed successfully", node_id)
        return {
            "node_outputs": {node_id: output, "__latest__": output},
            "last_output_port": {node_id: "success"},
        }
    # Any failure (timeout, unresolved variable reference, provider error, bad
    # tool binding) routes to this node's failure output rather than crashing
    # the run.
    except Exception as exc:  # noqa: BLE001
        logger.error("LLM node '%s' failed: %s", node_id, exc, exc_info=True)
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            error_msg = f"LLM execution timed out after {cfg.timeout_seconds} seconds"
        else:
            error_msg = str(exc) if str(exc).strip() else f"{type(exc).__name__}: Execution failed"
        error = {"error": error_msg}
        return {
            "node_outputs": {node_id: error, "__latest__": error},
            "last_output_port": {node_id: "failure"},
        }



register_node_type("llm", LlmConfig, execute)
