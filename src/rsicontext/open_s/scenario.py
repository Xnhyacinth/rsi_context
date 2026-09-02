"""Frozen visible open-S scenario. Evaluator-owned; policies cannot import this."""

from __future__ import annotations

from pathlib import Path

from rsicontext.campaign.loop import FEEDBACK_SCORE_COST, SEARCH_SELECTION_BLIND
from rsicontext.experiment.rsi_run import policy_tree_sha256

OPEN_S_VISIBLE_CELL_ID = "helmet-rag-popqa-k1000-to-8k"
OPEN_S_VISIBLE_ITEM_OFFSET = 104
OPEN_S_VISIBLE_MAX_ITEMS = 8
OPEN_S_VISIBLE_MIN_GOLD_RANK = 200
OPEN_S_VISIBLE_ROUNDS = 5
OPEN_S_VISIBLE_READER_OUTPUT_TOKENS = 64
OPEN_S_VISIBLE_READER_TIMEOUT_SECONDS = 600.0
OPEN_S_TEMPLATE_RESERVE_TOKENS = 16384
RESTRICTED_DEFAULT_PACK_TOKENS = 8192
PACK_ENVELOPE_READER_WINDOW = "reader-window"
PACK_ENVELOPE_SELECTION_BINDING = "selection-binding"
ALLOWED_PACK_ENVELOPES = frozenset({PACK_ENVELOPE_READER_WINDOW, PACK_ENVELOPE_SELECTION_BINDING})
OPEN_S_VISIBLE_PACK_ENVELOPE = PACK_ENVELOPE_SELECTION_BINDING
OPEN_S_VISIBLE_SEARCH_MODE = SEARCH_SELECTION_BLIND
OPEN_S_VISIBLE_FEEDBACK_SCHEMA = FEEDBACK_SCORE_COST


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
    pack_envelope: str | None = None,
) -> int:
    """Choose the pack envelope for a public visible launch."""

    if policy_track not in {"open-s", "restricted"}:
        raise ValueError(f"unsupported policy track: {policy_track}")
    if pack_tokens is not None:
        if not isinstance(pack_tokens, int) or isinstance(pack_tokens, bool) or pack_tokens < 1:
            raise ValueError("pack-tokens must be a positive integer when set")
        return pack_tokens
    envelope = pack_envelope
    if envelope is None:
        envelope = (
            PACK_ENVELOPE_READER_WINDOW
            if policy_track == "open-s"
            else PACK_ENVELOPE_SELECTION_BINDING
        )
    if envelope not in ALLOWED_PACK_ENVELOPES:
        raise ValueError(f"unsupported pack envelope: {envelope}")
    if envelope == PACK_ENVELOPE_SELECTION_BINDING:
        return RESTRICTED_DEFAULT_PACK_TOKENS
    if policy_track != "open-s" and pack_envelope is not None:
        raise ValueError("reader-window pack envelope is an open-S launch option")
    return reader_window_pack_budget(
        max_model_len=max_model_len,
        max_output_tokens=max_output_tokens,
    )


def reject_unchanged_open_s_tree(parent_sha256: str, policy_directory: str | Path) -> None:
    """Invalid an open-S turn that resubmits the parent policy bytes."""

    if policy_tree_sha256(Path(policy_directory)) == parent_sha256:
        raise ValueError(
            "open-S researcher must change the policy tree; identical parent copies are invalid"
        )
