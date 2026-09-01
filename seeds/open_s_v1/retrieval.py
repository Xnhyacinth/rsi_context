"""Local retrieval operators. H0 re-exports the frozen library; rewrite freely."""

from rsicontext.policy.open_s import map_shards, merge_ranked, retrieve_by_query

__all__ = ("map_shards", "merge_ranked", "retrieve_by_query")
