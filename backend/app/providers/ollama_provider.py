"""Default LLM provider — local Ollama. LLM calls are serialized process-wide
(FR-026, research.md §6) so multiple concurrent runs never overload one shared
Ollama instance."""

from __future__ import annotations

import asyncio
import os

from langchain_ollama import ChatOllama

# One semaphore per process, shared by every OllamaProvider instance/run.
_OLLAMA_SEMAPHORE = asyncio.Semaphore(1)


class OllamaProvider:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    async def generate(self, *, model: str, prompt: str, tools: list | None = None) -> str:
        chat = ChatOllama(model=model, base_url=self.base_url)
        if tools:
            chat = chat.bind_tools(tools)
        async with _OLLAMA_SEMAPHORE:
            result = await chat.ainvoke(prompt)
        return result.content
