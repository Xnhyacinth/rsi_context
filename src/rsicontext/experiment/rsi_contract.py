"""Freeze versus evolve surfaces for long-context RSI.

8K is the LongLLMLingua-aligned control cell and the pack envelope, not the RSI
object. The researcher iterates ``H`` under a frozen reader and official scorer.
"""

from __future__ import annotations

from dataclasses import dataclass

CONTROL_SOURCE_TOKENS = 32_768
CONTROL_PACK_TOKENS = 8_192
ENVELOPE_MAX_PACK_TOKENS = CONTROL_PACK_TOKENS

FROZEN: tuple[str, ...] = (
    "reader_weights",
    "reader_revision",
    "decode_temperature",
    "decode_seed",
    "thinking",
    "prefix_cache",
    "serving_profile",
    "reader_system_prompt",
    "official_scorer",
    "labels",
    "gate_sealed_items",
    "metric_definitions",
)

EVOLVE: tuple[str, ...] = (
    "policy_python",
    "visible_diagnostics",
    "pack_tokens_within_envelope",
    "select_order_cover_abstain_notes_format",
    "accounted_reread_or_paging",
    "visible_candidate_submission",
)

LAYERS: tuple[str, ...] = ("control_cell", "rsi_main", "transfer")


@dataclass(frozen=True, slots=True)
class LayerSpec:
    """One pre-registered experiment layer."""

    name: str
    source_tokens: int
    pack_envelope_tokens: int
    official: bool
    matched_grammar: bool


CONTROL_CELL = LayerSpec(
    "control_cell",
    CONTROL_SOURCE_TOKENS,
    CONTROL_PACK_TOKENS,
    official=False,
    matched_grammar=True,
)
RSI_MAIN = LayerSpec(
    "rsi_main",
    CONTROL_SOURCE_TOKENS,
    ENVELOPE_MAX_PACK_TOKENS,
    official=False,
    matched_grammar=False,
)
TRANSFER = LayerSpec(
    "transfer",
    CONTROL_SOURCE_TOKENS,
    CONTROL_PACK_TOKENS,
    official=True,
    matched_grammar=False,
)


def researcher_path_allowed(path: str) -> bool:
    """Researcher-editable files live only under top-level ``policy/``."""

    return path == "policy" or path.startswith("policy/")


def pack_within_envelope(token_count: int, *, envelope: int = ENVELOPE_MAX_PACK_TOKENS) -> bool:
    if not isinstance(token_count, int) or isinstance(token_count, bool) or token_count < 0:
        raise ValueError("token_count must be a non-negative integer")
    if not isinstance(envelope, int) or isinstance(envelope, bool) or envelope <= 0:
        raise ValueError("envelope must be a positive integer")
    return token_count <= envelope
