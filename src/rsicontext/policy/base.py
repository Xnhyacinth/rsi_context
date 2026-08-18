"""Public protocol for bounded context assembly."""

from typing import Protocol

from .types import Artifact, Budget, ContextPack


class ContextPolicy(Protocol):
    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        """Build reader context without producing a final answer."""
        ...
