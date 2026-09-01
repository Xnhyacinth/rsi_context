"""Open folder-strategy system S: harness evolution under a frozen reader."""

from rsicontext.open_s.contract import (
    OPEN_S_TRACK_ID,
    REQUIRED_SEED_FILES,
    OpenSSeedError,
    materialize_isolated_seed,
    repository_open_s_seed,
    seed_tree_digest,
    validate_open_s_seed,
)
from rsicontext.open_s.prompt import open_s_researcher_prompt
from rsicontext.open_s.scenario import (
    OPEN_S_VISIBLE_CELL_ID,
    OPEN_S_VISIBLE_ITEM_OFFSET,
    OPEN_S_VISIBLE_MAX_ITEMS,
    OPEN_S_VISIBLE_MIN_GOLD_RANK,
    OPEN_S_VISIBLE_READER_OUTPUT_TOKENS,
    OPEN_S_VISIBLE_READER_TIMEOUT_SECONDS,
    OPEN_S_VISIBLE_ROUNDS,
    reader_window_pack_budget,
    reject_unchanged_open_s_tree,
    resolve_pack_budget_tokens,
)

__all__ = [
    "OPEN_S_TRACK_ID",
    "OPEN_S_VISIBLE_CELL_ID",
    "OPEN_S_VISIBLE_ITEM_OFFSET",
    "OPEN_S_VISIBLE_MAX_ITEMS",
    "OPEN_S_VISIBLE_MIN_GOLD_RANK",
    "OPEN_S_VISIBLE_READER_OUTPUT_TOKENS",
    "OPEN_S_VISIBLE_READER_TIMEOUT_SECONDS",
    "OPEN_S_VISIBLE_ROUNDS",
    "REQUIRED_SEED_FILES",
    "OpenSSeedError",
    "materialize_isolated_seed",
    "open_s_researcher_prompt",
    "reader_window_pack_budget",
    "reject_unchanged_open_s_tree",
    "repository_open_s_seed",
    "resolve_pack_budget_tokens",
    "seed_tree_digest",
    "validate_open_s_seed",
]
