from __future__ import annotations

import platform
import unicodedata
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from rsicontext.baselines.search import random_search
from rsicontext.datasets.hard_long_context import (
    HardTaskProfile,
    generate_hard_long_context_dataset,
)
from rsicontext.policy import Artifact, Budget, DocumentChunk
from rsicontext.policy.spec_v1 import (
    CANONICAL_POLICY_SPECS_V1,
    AllocatorV1,
    GraphHopsV1,
    OrderV1,
    PolicyCalibrationCaseV1,
    PolicySpecV1,
    PolicySpecV1Interpreter,
    PositionReserveV1,
    SelectorV1,
    _combined_digest_from_parts,
    behavior_class_search_space_v1,
    canonical_behavior_classes_v1,
    policy_spec_v1_combined_digest,
    policy_spec_v1_config_json,
    policy_spec_v1_hashes,
)


def _artifact(texts: tuple[str, ...], *, renamed: bool = False) -> Artifact:
    document_id = "renamed" if renamed else "original"
    return Artifact(
        document_id=document_id,
        chunks=tuple(
            DocumentChunk(
                chunk_id=f"{'renamed' if renamed else 'chunk'}-{index}",
                document_id=document_id,
                start=index * 100,
                end=index * 100 + len(text),
                text=text,
                token_count=1,
            )
            for index, text in enumerate(texts)
        ),
    )


def _query_spec(
    hops: GraphHopsV1,
    allocator: AllocatorV1 = AllocatorV1.RANK,
    order: OrderV1 = OrderV1.RELEVANCE,
    reserve: PositionReserveV1 = PositionReserveV1.NONE,
) -> PolicySpecV1:
    return PolicySpecV1(SelectorV1.QUERY_BM25, hops, allocator, reserve, order)


def _calibration_case(seed: int) -> PolicyCalibrationCaseV1:
    texts = [f"background passage group{index % 17}" for index in range(512)]
    query_index = 73 + seed * 29
    one_hop_index = 401 - seed * 31
    two_hop_index = 211 + seed * 23
    texts[0] = f"front reserve edge{seed}x"
    texts[-1] = f"tail reserve rim{seed}x"
    texts[query_index] = f"needle{seed} seed{seed}x link{seed}a1"
    texts[one_hop_index] = f"link{seed}a1 link{seed}b2 cluster{seed}c3"
    texts[two_hop_index] = f"link{seed}b2 cluster{seed}d4 cluster{seed}e5"
    texts[35 + seed] = f"cluster{seed}c3 cluster{seed}d4 island{seed}f6"
    texts[285 - seed] = f"island{seed}g7 island{seed}h8 island{seed}i9"
    return PolicyCalibrationCaseV1(
        artifact=_artifact(tuple(texts)),
        query=f"needle{seed}",
        budget=Budget(max_tokens=6, max_chunks=6),
    )


FROZEN_CALIBRATION_PANEL = tuple(_calibration_case(seed) for seed in range(4))


def _disposable_hard_primary_panel() -> tuple[PolicyCalibrationCaseV1, ...]:
    dataset = generate_hard_long_context_dataset(
        seed="policy-spec-v1-disposable-visible",
        items_per_profile=4,
        requested_tokens=32_768,
        token_counter=lambda text: len(text.split()),
        tokenizer_id="qualification-whitespace-v1",
    )
    return tuple(
        PolicyCalibrationCaseV1(
            artifact=item.evaluation_item.artifact,
            query=item.evaluation_item.query,
            budget=Budget(max_tokens=8_192),
        )
        for item in dataset.visible_items()
        if item.task_profile
        in (
            HardTaskProfile.COMPOSITIONAL_MULTI_HOP,
            HardTaskProfile.DENSE_GLOBAL_COMPARISON,
        )
    )


def test_canonical_space_is_finite_unique_and_has_no_fill_axis() -> None:
    keys = tuple(spec.canonical_key for spec in CANONICAL_POLICY_SPECS_V1)

    assert 20 <= len(keys) <= 36
    assert len(keys) == len(set(keys))
    assert tuple(PolicySpecV1.from_canonical_key(key) for key in keys) == (
        CANONICAL_POLICY_SPECS_V1
    )
    assert all("fill" not in spec.to_config() for spec in CANONICAL_POLICY_SPECS_V1)


def test_spec_is_immutable_and_rejects_invalid_conditional_combinations() -> None:
    spec = _query_spec(GraphHopsV1.ONE)

    with pytest.raises(FrozenInstanceError):
        spec.graph_hops = GraphHopsV1.TWO  # type: ignore[misc]
    with pytest.raises(TypeError, match="selector"):
        PolicySpecV1(
            "query_bm25",  # type: ignore[arg-type]
            GraphHopsV1.ONE,
            AllocatorV1.RANK,
            PositionReserveV1.NONE,
            OrderV1.RELEVANCE,
        )
    with pytest.raises(ValueError, match="positional"):
        PolicySpecV1(
            SelectorV1.HEAD,
            GraphHopsV1.ONE,
            AllocatorV1.RANK,
            PositionReserveV1.NONE,
            OrderV1.SOURCE,
        )
    with pytest.raises(ValueError, match="edge-interleave"):
        _query_spec(
            GraphHopsV1.ONE,
            order=OrderV1.EDGE_INTERLEAVE,
            reserve=PositionReserveV1.HEAD,
        )
    with pytest.raises(ValueError, match="canonical policy key"):
        PolicySpecV1.from_canonical_key("free-form-controller-config")


def test_nfkc_casefold_and_bijective_identifier_rename_equivariance() -> None:
    texts = (
        "opening",
        "The fullwidth marker is \uff2d\uff21\uff32\uff33 code7x.",
        "Linked evidence code7x.",
        "ending",
    )
    policy = PolicySpecV1Interpreter().materialize(_query_spec(GraphHopsV1.ONE))

    original = policy.assemble(_artifact(texts), "mars", Budget(max_tokens=2))
    renamed = policy.assemble(_artifact(texts, renamed=True), "\uff4d\uff41\uff52\uff53", Budget(2))

    assert original.ordered_text() == renamed.ordered_text()
    assert original.ordered_text()[0] == texts[1]


def test_two_hop_graph_recovers_query_absent_chain_evidence() -> None:
    texts = ["background material" for _ in range(12)]
    texts[8] = "question7x path1x"
    texts[3] = "path1x path2y intermediate"
    texts[10] = "path2y answer evidence"
    artifact = _artifact(tuple(texts))
    budget = Budget(max_tokens=3, max_chunks=3)
    interpreter = PolicySpecV1Interpreter()

    zero = interpreter.materialize(_query_spec(GraphHopsV1.ZERO)).assemble(
        artifact, "question7x", budget
    )
    two = interpreter.materialize(_query_spec(GraphHopsV1.TWO)).assemble(
        artifact, "question7x", budget
    )

    assert texts[10] not in zero.ordered_text()
    assert two.ordered_text() == (texts[8], texts[3], texts[10])


def test_positional_head_tail_selects_source_edges_then_orders_by_source() -> None:
    artifact = _artifact(tuple(f"passage {index}" for index in range(8)))
    spec = PolicySpecV1(
        SelectorV1.HEAD_TAIL,
        GraphHopsV1.ZERO,
        AllocatorV1.RANK,
        PositionReserveV1.NONE,
        OrderV1.SOURCE,
    )
    pack = (
        PolicySpecV1Interpreter()
        .materialize(spec)
        .assemble(artifact, "", Budget(max_tokens=4, max_chunks=4))
    )

    assert tuple(span.text for span in pack.spans) == (
        "passage 0",
        "passage 7",
        "passage 1",
        "passage 6",
    )
    assert pack.ordered_text() == (
        "passage 0",
        "passage 1",
        "passage 6",
        "passage 7",
    )


def test_rare_coverage_and_mmr_are_not_rank_aliases_on_dense_context() -> None:
    texts = (
        "needle shared1x repeated evidence",
        "needle shared1x repeated evidence",
        "shared1x bridge2y novel3z",
        "novel4w novel5v novel6u",
        "unrelated prose",
        "unrelated ending",
    )
    artifact = _artifact(texts)
    budget = Budget(max_tokens=3, max_chunks=3)
    interpreter = PolicySpecV1Interpreter()

    selections = {
        allocator: interpreter.materialize(_query_spec(GraphHopsV1.ONE, allocator))
        .assemble(artifact, "needle", budget)
        .ordering
        for allocator in AllocatorV1
    }

    assert selections[AllocatorV1.RANK] != selections[AllocatorV1.RARE_COVERAGE]
    assert selections[AllocatorV1.RANK] != selections[AllocatorV1.MMR]


def test_frozen_512_chunk_panel_has_at_least_twenty_behavior_classes() -> None:
    classes = canonical_behavior_classes_v1(
        FROZEN_CALIBRATION_PANEL, profile_id="synthetic_graph_calibration"
    )

    assert len(classes) >= 20
    assert len({item.class_id for item in classes}) == len(classes)
    assert sum(len(item.specs) for item in classes) == len(CANONICAL_POLICY_SPECS_V1)
    assert {item.profile_id for item in classes} == {"synthetic_graph_calibration"}


def test_each_disposable_hard_primary_profile_has_twenty_behavior_classes() -> None:
    panel = _disposable_hard_primary_panel()
    compositional = panel[:4]
    dense = panel[4:]
    compositional_classes = canonical_behavior_classes_v1(
        compositional, profile_id=HardTaskProfile.COMPOSITIONAL_MULTI_HOP.value
    )
    dense_classes = canonical_behavior_classes_v1(
        dense, profile_id=HardTaskProfile.DENSE_GLOBAL_COMPARISON.value
    )
    interpreter = PolicySpecV1Interpreter()

    assert len(panel) == 8
    assert len(compositional_classes) >= 20
    assert len(dense_classes) >= 20
    for case in compositional:
        selections = {
            interpreter.materialize(_query_spec(hops))
            .assemble(case.artifact, case.query, case.budget)
            .ordering
            for hops in GraphHopsV1
        }
        assert len(selections) == 3


def test_dense_controls_include_genuine_zero_hop_order_and_position_contrasts() -> None:
    specs = set(CANONICAL_POLICY_SPECS_V1)

    for allocator in AllocatorV1:
        for order in OrderV1:
            assert _query_spec(GraphHopsV1.ZERO, allocator, order) in specs
    for reserve in (
        PositionReserveV1.HEAD,
        PositionReserveV1.TAIL,
        PositionReserveV1.EDGES,
    ):
        for order in (OrderV1.SOURCE, OrderV1.RELEVANCE):
            assert _query_spec(GraphHopsV1.ZERO, order=order, reserve=reserve) in specs


def test_random_search_samples_behavior_class_ids_without_replacement() -> None:
    classes = canonical_behavior_classes_v1(
        FROZEN_CALIBRATION_PANEL, profile_id="synthetic_graph_calibration"
    )
    class_ids = tuple(item.class_id for item in classes)
    result = random_search(
        behavior_class_search_space_v1(classes),
        lambda config: float(class_ids.index(config["behavior_class"])),
        max_metric_calls=len(class_ids),
        seed=19,
    )

    observed = tuple(item.config["behavior_class"] for item in result.observations)
    assert len(observed) == len(set(observed)) == len(class_ids)


def test_behavior_class_search_space_rejects_cross_profile_mixing() -> None:
    first = canonical_behavior_classes_v1(FROZEN_CALIBRATION_PANEL, profile_id="profile_a")
    second = canonical_behavior_classes_v1(FROZEN_CALIBRATION_PANEL, profile_id="profile_b")

    assert {item.class_id for item in first}.isdisjoint(item.class_id for item in second)
    with pytest.raises(ValueError, match="mix task profiles"):
        behavior_class_search_space_v1((first[0], second[0]))


def test_combined_digest_binds_exact_sources_configs_and_runtime_versions() -> None:
    module_path = Path(__file__).parents[1] / "src/rsicontext/policy/spec_v1.py"
    types_path = module_path.with_name("types.py")
    spec_source = module_path.read_bytes()
    types_source = types_path.read_bytes()
    config_json = policy_spec_v1_config_json()
    original = _combined_digest_from_parts(
        spec_source,
        types_source,
        config_json,
        platform.python_version(),
        unicodedata.unidata_version,
    )
    mutated = _combined_digest_from_parts(
        spec_source + b"# mutation\n",
        types_source,
        config_json,
        platform.python_version(),
        unicodedata.unidata_version,
    )

    assert original == policy_spec_v1_combined_digest()
    assert original != mutated
    hashes = policy_spec_v1_hashes()
    assert tuple(hashes) == ("grammar", "interpreter", "config_list", "combined")
    assert hashes["combined"] == original
    assert all(len(value) == 64 for value in hashes.values())
