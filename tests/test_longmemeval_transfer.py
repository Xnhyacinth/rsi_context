from __future__ import annotations

from rsicontext.analysis.longmemeval_qualification import (
    DETERMINISTIC_EVALUATORS,
    WEAK_EVALUATORS,
)
from rsicontext.datasets.longmemeval_transfer import (
    compare_offline_pack,
    last_k_pack,
    random_trajectory_pack,
    summarize_offline_pack_rates,
)
from rsicontext.policy import Artifact, Budget, DocumentChunk


def _artifact() -> Artifact:
    chunks = tuple(
        DocumentChunk(
            chunk_id=f"ck-{index}",
            document_id="lme",
            start=index * 10,
            end=index * 10 + 7,
            text=f"state {index} secret-answer" if index == 3 else f"state {index} filler",
            token_count=4,
        )
        for index in range(6)
    )
    return Artifact("lme", chunks)


def test_offline_longmemeval_packs_are_budgeted_and_do_not_claim_official_scores() -> None:
    artifact = _artifact()
    budget = Budget(max_tokens=12, max_chunks=3)
    last = last_k_pack(artifact, budget, k=3)
    random_pack = random_trajectory_pack(artifact, budget, seed=3, chunk_count=3)
    comparison = compare_offline_pack(
        policy_name="last-k",
        question_id="q1",
        pack=last,
        answer="secret-answer",
        eval_function="norm_phrase_set_match",
    )

    assert last.token_count <= 12
    assert len(last.spans) <= 3
    assert comparison.answer_string_present is True
    assert random_pack.token_count <= 12
    assert comparison.policy_name == "last-k"
    rates = summarize_offline_pack_rates(
        (comparison,),
        deterministic_evaluators=DETERMINISTIC_EVALUATORS,
        weak_evaluators=WEAK_EVALUATORS,
    )
    assert rates["deterministic"]["last-k"]["item_count"] == 1
    assert rates["weak"] == {}
    assert rates["deterministic"]["last-k"]["rate"] == 1.0
    parameterized = compare_offline_pack(
        policy_name="last-k",
        question_id="q2",
        pack=last,
        answer="secret-answer",
        eval_function="norm_phrase_set_match|lower=true",
    )
    parameterized_rates = summarize_offline_pack_rates(
        (parameterized,),
        deterministic_evaluators=DETERMINISTIC_EVALUATORS,
        weak_evaluators=WEAK_EVALUATORS,
    )
    assert parameterized_rates["deterministic"]["last-k"]["item_count"] == 1
