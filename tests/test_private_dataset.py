from __future__ import annotations

from rsicontext.datasets.private_counterfactual import generate_counterfactual_dataset
from rsicontext.experiment import Split


def test_private_generator_is_deterministic_and_family_disjoint() -> None:
    counts = {Split.VISIBLE: 4, Split.GATE: 2, Split.SEALED: 3}
    first = generate_counterfactual_dataset(seed="secret-a", counts=counts)
    second = generate_counterfactual_dataset(seed="secret-a", counts=counts)
    changed = generate_counterfactual_dataset(seed="secret-b", counts=counts)

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint != changed.fingerprint
    families = {
        split: {item.template_family for item in first.evaluator_items(split)} for split in Split
    }
    assert families[Split.VISIBLE].isdisjoint(families[Split.GATE])
    assert families[Split.VISIBLE].isdisjoint(families[Split.SEALED])
    assert families[Split.GATE].isdisjoint(families[Split.SEALED])


def test_researcher_export_contains_only_visible_items() -> None:
    dataset = generate_counterfactual_dataset(
        seed="secret", counts={Split.VISIBLE: 1, Split.GATE: 1, Split.SEALED: 1}
    )

    visible = dataset.visible_items()

    assert len(visible) == 1
    assert all(item.split is Split.VISIBLE for item in visible)
    assert not hasattr(dataset, "items")


def test_generated_items_have_two_hop_gold_and_counterfactual_answers() -> None:
    dataset = generate_counterfactual_dataset(
        seed="secret", counts={Split.VISIBLE: 5, Split.GATE: 0, Split.SEALED: 0}
    )

    for private_item in dataset.visible_items():
        item = private_item.evaluation_item
        assert len(item.gold_chunk_ids) == 2
        assert all("ANSWER:" not in chunk.text for chunk in item.artifact.chunks)
        color_chunks = [
            chunk
            for chunk in item.artifact.chunks
            if any(
                color in chunk.text.casefold()
                for color in ("amber", "violet", "silver", "cerulean", "ochre", "magenta", "teal")
            )
        ]
        assert len(color_chunks) >= 4
        assert sum(item.answer in chunk.text.casefold() for chunk in item.artifact.chunks) == 1
        assert private_item.entity.casefold() in item.query.casefold()


def test_policy_facing_ids_and_text_do_not_reveal_split_names() -> None:
    dataset = generate_counterfactual_dataset(
        seed="secret", counts={Split.VISIBLE: 1, Split.GATE: 1, Split.SEALED: 1}
    )

    for split in Split:
        private_item = dataset.evaluator_items(split)[0]
        item = private_item.evaluation_item
        policy_input = " ".join(
            [
                item.item_id,
                item.query,
                item.artifact.document_id,
                *(chunk.chunk_id for chunk in item.artifact.chunks),
                *(chunk.text for chunk in item.artifact.chunks),
            ]
        ).casefold()
        assert all(candidate.value not in policy_input for candidate in Split)


def test_split_families_use_distinct_task_templates() -> None:
    dataset = generate_counterfactual_dataset(
        seed="secret", counts={Split.VISIBLE: 1, Split.GATE: 1, Split.SEALED: 1}
    )
    markers = {
        Split.VISIBLE: "registry",
        Split.GATE: "dossier",
        Split.SEALED: "vault index",
    }

    for split, marker in markers.items():
        chunks = dataset.evaluator_items(split)[0].evaluation_item.artifact.chunks
        assert any(marker in chunk.text.casefold() for chunk in chunks)
        assert all(
            other_marker not in " ".join(chunk.text.casefold() for chunk in chunks)
            for other_split, other_marker in markers.items()
            if other_split is not split
        )
