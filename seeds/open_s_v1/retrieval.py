"""Local retrieval operators. H0 re-exports the frozen library; rewrite freely.

Frozen helper: retrieve_by_query(chunks, query). It ranks by overlap and has no top_k.
"""

from rsicontext.policy.open_s import map_shards, merge_ranked, retrieve_by_query

__all__ = ("map_shards", "merge_ranked", "retrieve_by_query")
