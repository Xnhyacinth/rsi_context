"""Benchmark-owned loop operators. Policies and researchers cannot choose these.

Borrowed from SLE (selection-blind vs normal, thin search-visible metrics) and
the study contract (fixed lineage, historical-best selection). This module does
not evolve the researcher, reader, or evaluator.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

LINEAGE_LAST_VALID: Final = "next-from-last-valid-attempt"
LINEAGE_FROM_SEED: Final = "next-from-seed"
SEARCH_NORMAL: Final = "normal"
SEARCH_SELECTION_BLIND: Final = "selection-blind"
FEEDBACK_VISIBLE_GOLD: Final = "visible-gold-plus-prior-outcome-v1"
FEEDBACK_SCORE_COST: Final = "visible-score-cost-v1"
FEEDBACK_SCORE_ONLY: Final = "visible-score-only-v1"

ALLOWED_LINEAGE_RULES: Final = frozenset({LINEAGE_LAST_VALID, LINEAGE_FROM_SEED})
ALLOWED_SEARCH_MODES: Final = frozenset({SEARCH_NORMAL, SEARCH_SELECTION_BLIND})
ALLOWED_FEEDBACK_SCHEMAS: Final = frozenset(
    {FEEDBACK_VISIBLE_GOLD, FEEDBACK_SCORE_COST, FEEDBACK_SCORE_ONLY}
)


class LoopContractError(ValueError):
    """Raised when a frozen loop field is inconsistent or unknown."""


def validate_loop_contract(
    *,
    lineage_rule: str,
    search_mode: str,
    feedback_schema: str,
) -> None:
    """Reject unknown loop fields and illegal combinations."""

    if lineage_rule not in ALLOWED_LINEAGE_RULES:
        raise LoopContractError(f"unsupported lineage_rule: {lineage_rule}")
    if search_mode not in ALLOWED_SEARCH_MODES:
        raise LoopContractError(f"unsupported search_mode: {search_mode}")
    if feedback_schema not in ALLOWED_FEEDBACK_SCHEMAS:
        raise LoopContractError(f"unsupported feedback_schema: {feedback_schema}")
    if search_mode == SEARCH_SELECTION_BLIND and lineage_rule != LINEAGE_FROM_SEED:
        raise LoopContractError("selection-blind requires next-from-seed lineage")


def next_research_parent_id(
    *,
    seed_artifact_id: str,
    last_attempt_artifact_id: str,
    lineage_rule: str,
) -> str:
    """Choose the next research parent. Historical-best is independent."""

    if lineage_rule not in ALLOWED_LINEAGE_RULES:
        raise LoopContractError(f"unsupported lineage_rule: {lineage_rule}")
    if lineage_rule == LINEAGE_FROM_SEED:
        return seed_artifact_id
    return last_attempt_artifact_id


def include_prior_candidate_outcomes(search_mode: str) -> bool:
    """Selection-blind proposals see only the frozen baseline, not later scores."""

    if search_mode not in ALLOWED_SEARCH_MODES:
        raise LoopContractError(f"unsupported search_mode: {search_mode}")
    return search_mode != SEARCH_SELECTION_BLIND


def prompt_score_view(
    *,
    search_mode: str,
    h0_score: float | None,
    previous_score: float | None,
    incumbent_score: float | None,
) -> tuple[float | None, float | None]:
    """Scores shown in the researcher prompt. Offline selection may still track peak."""

    if search_mode not in ALLOWED_SEARCH_MODES:
        raise LoopContractError(f"unsupported search_mode: {search_mode}")
    if search_mode == SEARCH_SELECTION_BLIND:
        return h0_score, h0_score
    return previous_score, incumbent_score


def search_visible_item_dict(
    item: Mapping[str, object],
    feedback_schema: str,
) -> dict[str, object]:
    """Project one visible item onto the frozen search-visible allowlist."""

    if feedback_schema not in ALLOWED_FEEDBACK_SCHEMAS:
        raise LoopContractError(f"unsupported feedback_schema: {feedback_schema}")
    if feedback_schema == FEEDBACK_VISIBLE_GOLD:
        return dict(item)
    if feedback_schema == FEEDBACK_SCORE_COST:
        return {
            "baseline_prediction": item["baseline_prediction"],
            "baseline_score": item["baseline_score"],
            "item_id": item["item_id"],
            "query": item["query"],
        }
    return {
        "baseline_score": item["baseline_score"],
        "item_id": item["item_id"],
    }


def loop_scope_text(*, lineage_rule: str, search_mode: str, feedback_schema: str) -> str:
    """One-line prompt description of the frozen loop. Not a method catalog."""

    validate_loop_contract(
        lineage_rule=lineage_rule,
        search_mode=search_mode,
        feedback_schema=feedback_schema,
    )
    if search_mode == SEARCH_SELECTION_BLIND:
        return (
            "Loop: selection-blind. Parent remains the seed. Later proposal scores are "
            "withheld from this prompt and do not change the next parent. Offline "
            "historical-best still selects after all slots."
        )
    if lineage_rule == LINEAGE_FROM_SEED:
        return (
            "Loop: next-from-seed. Each scored turn starts from the seed tree. Visible "
            f"feedback schema: {feedback_schema}."
        )
    return (
        "Loop: next-from-last-valid-attempt. Historical-best is independent. "
        f"Visible feedback schema: {feedback_schema}."
    )
