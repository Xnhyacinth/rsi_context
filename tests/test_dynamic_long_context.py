from __future__ import annotations

from itertools import pairwise

from rsicontext.datasets.dynamic_long_context import (
    DYNAMIC_CONTEXT_TOKENS,
    DynamicTaskProfile,
    generate_dynamic_long_context_dataset,
)
from rsicontext.experiment import Split
from rsicontext.policy import Budget
from rsicontext.policy.baselines import LexicalPolicy, TruncationPolicy


def test_dynamic_panel_is_deterministic_balanced_and_family_disjoint() -> None:
    first = generate_dynamic_long_context_dataset(seed="panel-a", items_per_profile=2)
    second = generate_dynamic_long_context_dataset(seed="panel-a", items_per_profile=2)
    changed = generate_dynamic_long_context_dataset(seed="panel-b", items_per_profile=2)

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != changed.fingerprint
    assert len(first.visible_items()) == 4
    for split in Split:
        items = first.evaluator_items(split)
        assert {item.task_profile for item in items} == set(DynamicTaskProfile)
        assert all(
            sum(item.task_profile is profile for item in items) == 2
            for profile in DynamicTaskProfile
        )

    families = {
        split: {item.template_family for item in first.evaluator_items(split)} for split in Split
    }
    assert families[Split.VISIBLE].isdisjoint(families[Split.GATE])
    assert families[Split.VISIBLE].isdisjoint(families[Split.SEALED])
    assert families[Split.GATE].isdisjoint(families[Split.SEALED])


def test_dynamic_items_are_exactly_32k_with_valid_gold_provenance() -> None:
    dataset = generate_dynamic_long_context_dataset(seed="panel", items_per_profile=1)

    for split in Split:
        for private_item in dataset.evaluator_items(split):
            item = private_item.evaluation_item
            chunks = item.artifact.chunks
            assert len(chunks) == 64
            assert sum(chunk.token_count for chunk in chunks) == DYNAMIC_CONTEXT_TOKENS
            assert all(chunk.token_count == len(chunk.text.split()) == 512 for chunk in chunks)
            assert all(left.end < right.start for left, right in pairwise(chunks))
            assert item.gold_chunk_ids <= item.artifact.chunk_ids
            assert item.gold_chunk_ids
            assert item.answer.casefold() not in item.query.casefold()


def test_profiles_require_sparse_bridging_or_dense_evidence_aggregation() -> None:
    dataset = generate_dynamic_long_context_dataset(seed="mechanisms", items_per_profile=3)
    visible = dataset.visible_items()
    sparse = [
        item.evaluation_item
        for item in visible
        if item.task_profile is DynamicTaskProfile.SPARSE_MULTI_HOP
    ]
    dense = [
        item.evaluation_item
        for item in visible
        if item.task_profile is DynamicTaskProfile.DENSE_COMPETING_VALUES
    ]

    assert all(len(item.gold_chunk_ids) == 2 for item in sparse)
    assert all(len(item.gold_chunk_ids) == 8 for item in dense)
    assert all(
        sum(item.answer.casefold() in chunk.text.casefold() for chunk in item.artifact.chunks) == 1
        for item in sparse
    )
    assert all(
        sum(item.answer.casefold() in chunk.text.casefold() for chunk in item.artifact.chunks) > 1
        for item in dense
    )

    budget = Budget(max_tokens=8192)
    for policy in (LexicalPolicy(), TruncationPolicy("head")):
        retained_gold = [
            item.gold_chunk_ids
            <= {span.chunk_id for span in policy.assemble(item.artifact, item.query, budget).spans}
            for item in (private_item.evaluation_item for private_item in visible)
        ]
        assert not all(retained_gold)


def test_policy_facing_content_has_opaque_ids_and_no_answer_marker_or_split_names() -> None:
    dataset = generate_dynamic_long_context_dataset(seed="opaque", items_per_profile=1)

    for split in Split:
        for private_item in dataset.evaluator_items(split):
            item = private_item.evaluation_item
            policy_input = " ".join(
                (
                    item.item_id,
                    item.query,
                    item.artifact.document_id,
                    *(chunk.chunk_id for chunk in item.artifact.chunks),
                    *(chunk.text for chunk in item.artifact.chunks),
                )
            ).casefold()
            assert "answer:" not in policy_input
            assert "gold" not in policy_input
            assert all(candidate.value not in policy_input for candidate in Split)
            assert all(profile.value not in policy_input for profile in DynamicTaskProfile)


def test_researcher_export_contains_only_visible_dynamic_items() -> None:
    dataset = generate_dynamic_long_context_dataset(seed="private", items_per_profile=1)

    assert len(dataset.visible_items()) == 2
    assert all(item.split is Split.VISIBLE for item in dataset.visible_items())
    assert not hasattr(dataset, "items")
