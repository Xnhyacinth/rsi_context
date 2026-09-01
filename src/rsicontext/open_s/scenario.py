"""Frozen visible open-S scenario. Evaluator-owned; policies cannot import this."""

from __future__ import annotations

from pathlib import Path

from rsicontext.experiment.rsi_run import policy_tree_sha256

OPEN_S_VISIBLE_CELL_ID = "helmet-rag-popqa-k1000-to-8k"
OPEN_S_VISIBLE_ITEM_OFFSET = 88
OPEN_S_VISIBLE_MAX_ITEMS = 8
OPEN_S_VISIBLE_MIN_GOLD_RANK = 200
OPEN_S_VISIBLE_ROUNDS = 5
OPEN_S_VISIBLE_READER_OUTPUT_TOKENS = 64
OPEN_S_VISIBLE_READER_TIMEOUT_SECONDS = 600.0
OPEN_S_TEMPLATE_RESERVE_TOKENS = 16384
RESTRICTED_DEFAULT_PACK_TOKENS = 8192


def reader_window_pack_budget(
    *,
    max_model_len: int,
    max_output_tokens: int,
    template_reserve_tokens: int = OPEN_S_TEMPLATE_RESERVE_TOKENS,
) -> int:
    """Pack budget that fills the frozen reader window, not a historical 8K cap.

    Full-as-fits, retrieve-then-pack, truncation, and reorder all share this
    envelope. Items longer than the window still require selection. The reserve
    covers the reader system prompt, Question/Evidence wrappers, per-span ids,
    and Qwen-axis vs reader-reported prompt_tokens slack. A 2048-token reserve
    overflowed hy3 at pack 128960.
    """

    for name, value in (
        ("max_model_len", max_model_len),
        ("max_output_tokens", max_output_tokens),
        ("template_reserve_tokens", template_reserve_tokens),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    usable = max_model_len - max_output_tokens - template_reserve_tokens
    if usable < 1:
        raise ValueError("reader window leaves no pack budget")
    return usable


def resolve_pack_budget_tokens(
    *,
    pack_tokens: int | None,
    policy_track: str,
    max_model_len: int,
    max_output_tokens: int,
) -> int:
    """Choose the pack envelope for a public visible launch."""

    if pack_tokens is not None:
        if not isinstance(pack_tokens, int) or isinstance(pack_tokens, bool) or pack_tokens < 1:
            raise ValueError("pack-tokens must be a positive integer when set")
        return pack_tokens
    if policy_track == "open-s":
        return reader_window_pack_budget(
            max_model_len=max_model_len,
            max_output_tokens=max_output_tokens,
        )
    if policy_track != "restricted":
        raise ValueError(f"unsupported policy track: {policy_track}")
    return RESTRICTED_DEFAULT_PACK_TOKENS


def reject_unchanged_open_s_tree(parent_sha256: str, policy_directory: str | Path) -> None:
    """Invalid an open-S turn that resubmits the parent policy bytes."""

    if policy_tree_sha256(Path(policy_directory)) == parent_sha256:
        raise ValueError(
            "open-S researcher must change the policy tree; identical parent copies are invalid"
        )
