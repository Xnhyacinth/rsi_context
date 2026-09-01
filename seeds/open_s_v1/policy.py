"""Open-S H0 composition: source-order full-as-fits. Researcher may rewrite this file."""

from memory import record_working_set

from rsicontext.policy import Artifact, Budget, ContextPack
from rsicontext.policy.open_s import pack_spans


class Policy:
    """Long-context baseline: keep source order and fill the frozen window."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        record_working_set(query, artifact.chunks)
        return pack_spans(artifact.chunks, artifact, budget)
