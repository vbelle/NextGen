"""Default LLM provider — local Ollama. LLM calls are serialized process-wide
(FR-026, research.md §6) so multiple concurrent runs never overload one shared
Ollama instance."""

from __future__ import annotations

import asyncio
import os

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_ollama import ChatOllama

from app.logging import get_logger

logger = get_logger(__name__)

# One semaphore per process, shared by every OllamaProvider instance/run — and
# also imported by app/vectorstore.py, since embeddings calls hit the same
# shared Ollama instance and FR-026's concern applies to those too.
OLLAMA_SEMAPHORE = asyncio.Semaphore(1)

# Safety bound on the function-calling loop (User Story 11, FR-016) — not
# spec'd explicitly, but an unbounded "model keeps requesting tools" loop
# would be the same class of runaway behavior the Retry node's max_attempts
# exists to prevent, so the same instinct applies here.
MAX_TOOL_ROUNDS = 5


class OllamaProvider:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    async def generate(self, *, model: str, prompt: str, tools: list | None = None) -> str:
        logger.info(
            "OllamaProvider.generate: model=%s, base_url=%s, prompt_len=%d, tools_count=%d",
            model,
            self.base_url,
            len(prompt),
            len(tools) if tools else 0,
        )
        try:
            # stream=False prevents httpx chunked-stream stalls when local Ollama buffers tokens
            chat = ChatOllama(model=model, base_url=self.base_url, stream=False)
            if tools:
                chat = chat.bind_tools(tools)

            messages = [HumanMessage(content=prompt)]
            logger.info(
                "OllamaProvider: Sending initial prompt to ChatOllama (awaiting response)..."
            )
            async with OLLAMA_SEMAPHORE:
                response = await chat.ainvoke(messages)
            logger.info(
                "OllamaProvider: Initial response received from ChatOllama (has_tool_calls=%s)",
                bool(getattr(response, "tool_calls", None)),
            )

            rounds = 0
            while tools and getattr(response, "tool_calls", None):
                rounds += 1
                tool_calls = response.tool_calls
                logger.info(
                    "[OLLAMA TOOL LOOP] Round %d/%d: Model requested tool calls: %s",
                    rounds,
                    MAX_TOOL_ROUNDS,
                    tool_calls,
                )
                if rounds > MAX_TOOL_ROUNDS:
                    msg = (
                        f"Model requested more than {MAX_TOOL_ROUNDS} tool-calling rounds "
                        "in a single generation — aborting to avoid a runaway loop"
                    )
                    logger.error("OllamaProvider.generate: %s", msg)
                    raise RuntimeError(msg)
                messages.append(response)
                for call in response.tool_calls:
                    tool = next((t for t in tools if t.name == call["name"]), None)
                    if tool is None:
                        tool_result = f"Error: no tool named '{call['name']}' is available"
                        logger.warning(
                            "[OLLAMA TOOL CALL ERROR] Tool '%s' requested but not bound",
                            call["name"],
                        )
                    else:
                        logger.info(
                            "[OLLAMA TOOL INVOKING] Tool '%s' with args: %s",
                            call["name"],
                            call["args"],
                        )
                        try:
                            tool_result = await tool.ainvoke(call["args"])
                            logger.info(
                                "[OLLAMA TOOL RESULT SUCCESS] Tool '%s' returned: %s",
                                call["name"],
                                repr(str(tool_result)[:150]),
                            )
                        except Exception as exc:
                            logger.error(
                                "[OLLAMA TOOL RESULT FAILURE] Tool '%s' raised exception: %s",
                                call["name"],
                                exc,
                                exc_info=True,
                            )
                            raise
                    messages.append(ToolMessage(content=str(tool_result), tool_call_id=call["id"]))
                async with OLLAMA_SEMAPHORE:
                    logger.info(
                        "[OLLAMA TOOL RE-INVOKE] Sending tool execution results back to model..."
                    )
                    response = await chat.ainvoke(messages)

            content_str = str(response.content)
            logger.info("OllamaProvider.generate success: response_len=%d", len(content_str))
            return content_str
        except Exception as exc:
            logger.error(
                "OllamaProvider.generate failed for model '%s': %s", model, exc, exc_info=True
            )
            raise
