"""Open-S H0 composition. Researcher may rewrite this file and sibling modules."""

from memory import record_working_set
from retrieval import map_shards, merge_ranked, retrieve_by_query
from skills import route_skill

from rsicontext.policy import Artifact, Budget, ContextPack
from rsicontext.policy.open_s import pack_spans


class Policy:
    """Default folder strategy: retrieve, identity-shard merge, route, then pack."""

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        skill = route_skill(query)
        ranked = artifact.chunks if skill == "head" else retrieve_by_query(artifact.chunks, query)
        ranked = merge_ranked(map_shards(ranked, shard_count=1))
        record_working_set(query, ranked)
        return pack_spans(ranked, artifact, budget)
