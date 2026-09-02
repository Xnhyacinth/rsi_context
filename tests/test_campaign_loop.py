from __future__ import annotations

import pytest

from rsicontext.campaign.loop import (
    FEEDBACK_SCORE_COST,
    FEEDBACK_SCORE_ONLY,
    FEEDBACK_VISIBLE_GOLD,
    LINEAGE_FROM_SEED,
    LINEAGE_LAST_VALID,
    SEARCH_NORMAL,
    SEARCH_SELECTION_BLIND,
    LoopContractError,
    include_prior_candidate_outcomes,
    loop_scope_text,
    next_research_parent_id,
    prompt_score_view,
    search_visible_item_dict,
    validate_loop_contract,
)


def test_selection_blind_requires_seed_lineage() -> None:
    with pytest.raises(LoopContractError, match="selection-blind requires next-from-seed"):
        validate_loop_contract(
            lineage_rule=LINEAGE_LAST_VALID,
            search_mode=SEARCH_SELECTION_BLIND,
            feedback_schema=FEEDBACK_VISIBLE_GOLD,
        )
    validate_loop_contract(
        lineage_rule=LINEAGE_FROM_SEED,
        search_mode=SEARCH_SELECTION_BLIND,
        feedback_schema=FEEDBACK_SCORE_ONLY,
    )


def test_from_seed_parent_does_not_follow_the_last_attempt() -> None:
    seed = "s" * 64
    attempt = "c" * 64
    assert (
        next_research_parent_id(
            seed_artifact_id=seed,
            last_attempt_artifact_id=attempt,
            lineage_rule=LINEAGE_FROM_SEED,
        )
        == seed
    )
    assert (
        next_research_parent_id(
            seed_artifact_id=seed,
            last_attempt_artifact_id=attempt,
            lineage_rule=LINEAGE_LAST_VALID,
        )
        == attempt
    )


def test_selection_blind_withholds_later_scores_from_the_prompt() -> None:
    assert include_prior_candidate_outcomes(SEARCH_NORMAL) is True
    assert include_prior_candidate_outcomes(SEARCH_SELECTION_BLIND) is False
    previous, incumbent = prompt_score_view(
        search_mode=SEARCH_SELECTION_BLIND,
        h0_score=0.5,
        previous_score=0.625,
        incumbent_score=0.625,
    )
    assert previous == 0.5
    assert incumbent == 0.5
    previous, incumbent = prompt_score_view(
        search_mode=SEARCH_NORMAL,
        h0_score=0.5,
        previous_score=0.625,
        incumbent_score=0.625,
    )
    assert previous == 0.625
    assert incumbent == 0.625


def test_score_feedback_schemas_seal_gold_spans() -> None:
    item = {
        "baseline_prediction": "INSUFFICIENT",
        "baseline_score": 0.0,
        "gold_evidence": [{"chunk_id": "ck-1", "text": "secret gold"}],
        "item_id": "visible-1",
        "query": "Where?",
        "reference_answer": "Paris",
    }
    gold = search_visible_item_dict(item, FEEDBACK_VISIBLE_GOLD)
    assert gold["gold_evidence"] == item["gold_evidence"]
    cost = search_visible_item_dict(item, FEEDBACK_SCORE_COST)
    assert "gold_evidence" not in cost
    assert "reference_answer" not in cost
    assert cost["query"] == "Where?"
    only = search_visible_item_dict(item, FEEDBACK_SCORE_ONLY)
    assert only == {"baseline_score": 0.0, "item_id": "visible-1"}


def test_loop_scope_names_the_frozen_operator() -> None:
    text = loop_scope_text(
        lineage_rule=LINEAGE_FROM_SEED,
        search_mode=SEARCH_SELECTION_BLIND,
        feedback_schema=FEEDBACK_SCORE_ONLY,
    )
    assert "selection-blind" in text
    assert "method catalog" not in text
