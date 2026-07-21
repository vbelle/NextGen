"""Provider-agnostic model layer (Constitution V). Adding a new provider means
adding a class here, never touching workflow schemas or node configs."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ModelProvider(ABC):
    @abstractmethod
    async def generate(self, *, model: str, prompt: str, tools: list | None = None) -> str:
        """Returns the model's text response. `tools` is reserved for the Tool node
        (User Story 11) — accepted here now so the interface doesn't need to change
        when that story lands."""
        raise NotImplementedError
