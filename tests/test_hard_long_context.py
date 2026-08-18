from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict, deque
from dataclasses import replace
from itertools import pairwise

import pytest

from rsicontext.datasets.hard_long_context import (
    ABSTENTION_SENTINEL,
    HARD_TARGET_TOKEN_TOLERANCE_FRACTION,
    MINIMUM_CALIBRATION_ITEMS_PER_PROFILE,
    NOMINAL_HARD_CONTEXT_TOKENS,
    SUPPORTED_HARD_CONTEXT_TOKENS,
    EvidencePosition,
    HardLongContextDataset,
    HardTaskProfile,
    _hard_dataset_fingerprint,
    generate_hard_long_context_dataset,
    generate_hard_long_context_split,
)
from rsicontext.eval import EvaluationItem
from rsicontext.experiment import Split
from rsicontext.policy import (
    Budget,
    GraphHopsV1,
    PolicySpecV1,
    PolicySpecV1Interpreter,
    PositionReserveV1,
    SelectorV1,
)
from rsicontext.policy.baselines import LexicalPolicy, TruncationPolicy
from rsicontext.policy.spec_v1 import AllocatorV1, OrderV1


def _word_tokens(text: str) -> int:
    return len(text.split())


def _byte_tokens(text: str) -> int:
    return len(text.encode("utf-8"))


def _visible_dataset(
    *, seed: str, items_per_profile: int, requested_tokens: int
) -> HardLongContextDataset:
    return generate_hard_long_context_dataset(
        seed=seed,
        items_per_profile=items_per_profile,
        requested_tokens=requested_tokens,
        token_counter=_word_tokens,
        tokenizer_id="test-word-v1",
    )


def test_hard_panel_is_deterministic_balanced_and_split_disjoint() -> None:
    first = _visible_dataset(seed="hard-a", items_per_profile=2, requested_tokens=8192)
    repeated = _visible_dataset(seed="hard-a", items_per_profile=2, requested_tokens=8192)
    changed = _visible_dataset(seed="hard-b", items_per_profile=2, requested_tokens=8192)

    assert first.fingerprint == repeated.fingerprint
    assert first.fingerprint != changed.fingerprint
    assert first.requested_target_tokens == 8192
    assert first.tokenizer_id == "test-word-v1"
    assert len(first.visible_items()) == 2 * len(HardTaskProfile)
    datasets = {
        Split.VISIBLE: first,
        Split.GATE: generate_hard_long_context_split(
            split=Split.GATE,
            evaluator_seed="gate-secret-0123456789abcdef-0001",
            items_per_profile=2,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        ),
        Split.SEALED: generate_hard_long_context_split(
            split=Split.SEALED,
            evaluator_seed="sealed-secret-0123456789abcdef-01",
            items_per_profile=2,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        ),
    }
    for split, dataset in datasets.items():
        items = dataset.evaluator_items()
        assert dataset.split is split
        assert {item.task_profile for item in items} == set(HardTaskProfile)
        assert all(
            sum(item.task_profile is profile for item in items) == 2 for profile in HardTaskProfile
        )

    families = {
        split: {item.template_family for item in dataset.evaluator_items()}
        for split, dataset in datasets.items()
    }
    assert families[Split.VISIBLE].isdisjoint(families[Split.GATE])
    assert families[Split.VISIBLE].isdisjoint(families[Split.SEALED])
    assert families[Split.GATE].isdisjoint(families[Split.SEALED])

    prefixes = {
        Split.VISIBLE: "Ledger ",
        Split.GATE: "CARD[",
        Split.SEALED: "Dispatch ",
    }
    for split, dataset in datasets.items():
        chunks = [
            chunk.text
            for item in dataset.evaluator_items()
            for chunk in item.evaluation_item.artifact.chunks
        ]
        assert all(text.startswith(prefixes[split]) for text in chunks)
        assert all(
            not text.startswith(prefix)
            for other_split, prefix in prefixes.items()
            if other_split is not split
            for text in chunks
        )


def test_compositional_nongold_chunks_do_not_name_the_answer() -> None:
    dataset = _visible_dataset(seed="decoy-noleak", items_per_profile=2, requested_tokens=8192)
    for private in dataset.visible_items():
        if private.task_profile is not HardTaskProfile.COMPOSITIONAL_MULTI_HOP:
            continue
        item = private.evaluation_item
        for chunk in item.artifact.chunks:
            if chunk.chunk_id in item.gold_chunk_ids:
                continue
            assert item.answer not in chunk.text


def test_primary_decoy_body_grammars_are_split_specific_beyond_wrappers() -> None:
    datasets = {
        Split.VISIBLE: _visible_dataset(
            seed="body-grammar-visible", items_per_profile=1, requested_tokens=8192
        ),
        Split.GATE: generate_hard_long_context_split(
            split=Split.GATE,
            evaluator_seed="body-grammar-gate-secret-0123456789abcdef",
            items_per_profile=1,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        ),
        Split.SEALED: generate_hard_long_context_split(
            split=Split.SEALED,
            evaluator_seed="body-grammar-sealed-secret-0123456789abcd",
            items_per_profile=1,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        ),
    }
    characteristic_ngrams: dict[HardTaskProfile, dict[Split, tuple[str, ...]]] = {
        HardTaskProfile.COMPOSITIONAL_MULTI_HOP: {
            Split.VISIBLE: ("collateral ledger note", "paired satellite record", "unrelated audit"),
            Split.GATE: ("role=satellite", "scope=mismatch", "quoted_terminal="),
            Split.SEALED: ("collateral dispatch paired", "separate review"),
        },
        HardTaskProfile.DENSE_GLOBAL_COMPARISON: {
            Split.VISIBLE: ("near-match accepted score", "claims accepted score"),
            Split.GATE: ("status=rejected_epoch", "status=rejected_seal"),
            Split.SEALED: ("prior-season reviewer", "unrecognized reviewer"),
        },
    }

    for profile, split_ngrams in characteristic_ngrams.items():
        all_ngrams = set().union(*map(set, split_ngrams.values()))
        for split, dataset in datasets.items():
            private_item = next(
                item for item in dataset.evaluator_items() if item.task_profile is profile
            )
            item = private_item.evaluation_item
            nongold = " ".join(
                chunk.text.casefold()
                for chunk in item.artifact.chunks
                if chunk.chunk_id not in item.gold_chunk_ids
            )
            own = set(split_ngrams[split])
            assert all(ngram in nongold for ngram in own)
            assert all(ngram not in nongold for ngram in all_ngrams - own)
            assert len(item.gold_chunk_ids) == (
                5 if profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP else 13
            )
            assert item.answer.startswith(("vl-", "nd-"))

    assert not hasattr(datasets[Split.GATE], "seed")
    assert not hasattr(datasets[Split.SEALED], "seed")


def test_dataset_fingerprint_binds_query_and_chunk_token_counts() -> None:
    dataset = _visible_dataset(
        seed="fingerprint-binding", items_per_profile=1, requested_tokens=8192
    )
    items = dataset.visible_items()
    original = items[0]
    evaluation = original.evaluation_item
    query_changed = replace(
        original,
        evaluation_item=replace(evaluation, query=f"{evaluation.query} changed"),
    )
    first_chunk = evaluation.artifact.chunks[0]
    token_changed = replace(
        original,
        evaluation_item=replace(
            evaluation,
            artifact=replace(
                evaluation.artifact,
                chunks=(
                    replace(first_chunk, token_count=first_chunk.token_count + 1),
                    *evaluation.artifact.chunks[1:],
                ),
            ),
        ),
    )

    def fingerprint(replacement: object) -> str:
        changed = (replacement, *items[1:])
        return _hard_dataset_fingerprint(
            changed,  # type: ignore[arg-type]
            requested_tokens=dataset.requested_target_tokens,
            tokenizer_id=dataset.tokenizer_id,
        )

    assert fingerprint(query_changed) != dataset.fingerprint
    assert fingerprint(token_changed) != dataset.fingerprint


def test_requested_target_length_is_native_and_semantic_words_are_separate() -> None:
    dataset = _visible_dataset(
        seed="length", items_per_profile=1, requested_tokens=NOMINAL_HARD_CONTEXT_TOKENS
    )

    for private_item in dataset.evaluator_items():
        item = private_item.evaluation_item
        chunks = item.artifact.chunks
        assert private_item.requested_target_tokens == NOMINAL_HARD_CONTEXT_TOKENS
        assert private_item.source_target_tokens == NOMINAL_HARD_CONTEXT_TOKENS
        assert private_item.semantic_word_count == NOMINAL_HARD_CONTEXT_TOKENS
        assert len(chunks) == NOMINAL_HARD_CONTEXT_TOKENS // 512
        assert sum(chunk.token_count for chunk in chunks) == NOMINAL_HARD_CONTEXT_TOKENS
        assert all(chunk.token_count == len(chunk.text.split()) == 512 for chunk in chunks)
        assert all(left.end < right.start for left, right in pairwise(chunks))
        assert item.gold_chunk_ids <= item.artifact.chunk_ids

    assert frozenset((8192, 32768, 131072, 262144)) == SUPPORTED_HARD_CONTEXT_TOKENS
    with pytest.raises(ValueError, match="requested_tokens"):
        _visible_dataset(seed="length", items_per_profile=1, requested_tokens=16384)


def test_generator_calibrates_text_before_emitting_target_token_counts() -> None:
    dataset = generate_hard_long_context_dataset(
        seed="native-tokenize",
        items_per_profile=1,
        requested_tokens=8192,
        token_counter=_byte_tokens,
        tokenizer_id="unit-byte-tokenizer@sha256:abc",
    )

    tolerance = dataset.target_token_tolerance
    assert tolerance == 164
    assert HARD_TARGET_TOKEN_TOLERANCE_FRACTION == 0.02
    assert dataset.tokenizer_id == "unit-byte-tokenizer@sha256:abc"
    assert all(abs(count - 8192) <= tolerance for count in dataset.source_token_counts)
    assert all(
        words < count
        for words, count in zip(
            dataset.semantic_word_counts, dataset.source_token_counts, strict=True
        )
    )
    assert all(
        chunk.token_count == len(chunk.text.encode("utf-8"))
        for item in dataset.evaluator_items()
        for chunk in item.evaluation_item.artifact.chunks
    )

    with pytest.raises(ValueError, match="positive integer"):
        generate_hard_long_context_dataset(
            seed="broken-counter",
            items_per_profile=1,
            requested_tokens=8192,
            token_counter=lambda text: 0,
            tokenizer_id="broken",
        )


def test_profiles_have_distinct_nontrivial_evidence_topologies() -> None:
    dataset = _visible_dataset(seed="topologies", items_per_profile=1, requested_tokens=8192)
    by_profile = {item.task_profile: item for item in dataset.visible_items()}

    expected_evidence = {
        HardTaskProfile.COMPOSITIONAL_MULTI_HOP: 5,
        HardTaskProfile.DENSE_GLOBAL_COMPARISON: 13,
        HardTaskProfile.TEMPORAL_STATE_RESOLUTION: 5,
        HardTaskProfile.INSUFFICIENT_EVIDENCE: 3,
    }
    for profile, evidence_count in expected_evidence.items():
        private_item = by_profile[profile]
        item = private_item.evaluation_item
        assert len(item.gold_chunk_ids) == evidence_count
        assert private_item.minimum_evidence_chunks == evidence_count
        assert item.gold_chunk_ids
        if profile is not HardTaskProfile.DENSE_GLOBAL_COMPARISON:
            assert not item.answer or item.answer.casefold() not in item.query.casefold()

    compositional = by_profile[HardTaskProfile.COMPOSITIONAL_MULTI_HOP].evaluation_item
    dense = by_profile[HardTaskProfile.DENSE_GLOBAL_COMPARISON].evaluation_item
    temporal = by_profile[HardTaskProfile.TEMPORAL_STATE_RESOLUTION].evaluation_item
    abstention = by_profile[HardTaskProfile.INSUFFICIENT_EVIDENCE]
    assert (
        sum(
            compositional.answer.casefold() in chunk.text.casefold()
            for chunk in compositional.artifact.chunks
        )
        == 1
    )
    compositional_subject = next(
        token.strip(".,;:[]()") for token in compositional.query.split() if token.startswith("nd-")
    )
    assert (
        sum(
            compositional_subject.casefold() in chunk.text.casefold()
            for chunk in compositional.artifact.chunks
        )
        >= 2
    )
    assert (
        sum(chunk.text.casefold().count(dense.answer.casefold()) for chunk in dense.artifact.chunks)
        >= 3
    )
    assert (
        sum(
            temporal.answer.casefold() in chunk.text.casefold()
            for chunk in temporal.artifact.chunks
        )
        == 1
    )
    assert abstention.requires_abstention
    assert abstention.evaluation_item.answer == ABSTENTION_SENTINEL
    assert all(
        not item.requires_abstention
        for profile, item in by_profile.items()
        if profile is not HardTaskProfile.INSUFFICIENT_EVIDENCE
    )


def test_position_control_covers_head_middle_tail_and_distributed_evidence() -> None:
    dataset = _visible_dataset(seed="positions", items_per_profile=4, requested_tokens=32768)

    for profile in HardTaskProfile:
        items = [item for item in dataset.visible_items() if item.task_profile is profile]
        assert {item.evidence_position for item in items} == set(EvidencePosition)
        for private_item in items:
            chunks = private_item.evaluation_item.artifact.chunks
            gold_indices = [
                index
                for index, chunk in enumerate(chunks)
                if chunk.chunk_id in private_item.evaluation_item.gold_chunk_ids
            ]
            n_chunks = len(chunks)
            if profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP:
                subject = next(
                    token.strip(".,;:[]()")
                    for token in private_item.evaluation_item.query.split()
                    if token.startswith("nd-")
                )
                a_index = next(
                    index
                    for index, chunk in enumerate(chunks)
                    if chunk.chunk_id in private_item.evaluation_item.gold_chunk_ids
                    and subject in chunk.text
                )
                if private_item.evidence_position is EvidencePosition.HEAD:
                    assert a_index < n_chunks // 3
                elif private_item.evidence_position is EvidencePosition.MIDDLE:
                    assert n_chunks // 3 <= a_index < 2 * n_chunks // 3
                elif private_item.evidence_position is EvidencePosition.TAIL:
                    assert a_index >= 2 * n_chunks // 3
                else:
                    assert min(gold_indices) < n_chunks // 4
                    assert max(gold_indices) >= 3 * n_chunks // 4
                assert max(gold_indices) - min(gold_indices) >= (2 * (n_chunks - 1)) // 3
                continue
            if private_item.evidence_position is EvidencePosition.HEAD:
                assert max(gold_indices) < n_chunks // 3
            elif private_item.evidence_position is EvidencePosition.MIDDLE:
                assert min(gold_indices) >= n_chunks // 3
                assert max(gold_indices) < 2 * n_chunks // 3
            elif private_item.evidence_position is EvidencePosition.TAIL:
                assert min(gold_indices) >= 2 * n_chunks // 3
            else:
                assert min(gold_indices) < n_chunks // 4
                assert max(gold_indices) >= 3 * n_chunks // 4


def test_policy_content_has_opaque_ids_and_no_private_labels_or_literal_markers() -> None:
    datasets = (
        _visible_dataset(seed="opaque", items_per_profile=1, requested_tokens=8192),
        generate_hard_long_context_split(
            split=Split.GATE,
            evaluator_seed="gate-secret-opaque-0123456789abcdef",
            items_per_profile=1,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        ),
    )

    for dataset in datasets:
        for private_item in dataset.evaluator_items():
            item = private_item.evaluation_item
            policy_content = " ".join(
                (
                    item.item_id,
                    item.query,
                    item.artifact.document_id,
                    *(chunk.chunk_id for chunk in item.artifact.chunks),
                    *(chunk.text for chunk in item.artifact.chunks),
                )
            ).casefold()
            assert "answer:" not in policy_content
            assert "gold" not in policy_content
            assert "__rsicontext" not in policy_content
            assert ABSTENTION_SENTINEL.casefold() not in policy_content
            assert all(split_name.value not in policy_content for split_name in Split)
            assert all(profile.value not in policy_content for profile in HardTaskProfile)
            assert all(position.value not in policy_content for position in EvidencePosition)
            assert item.item_id.startswith("hx-")
            assert all(chunk.chunk_id.startswith("ck-") for chunk in item.artifact.chunks)


def test_simple_structural_baselines_do_not_saturate_the_panel() -> None:
    dataset = _visible_dataset(seed="baseline", items_per_profile=4, requested_tokens=32768)
    items = [private_item.evaluation_item for private_item in dataset.visible_items()]
    budget = Budget(max_tokens=8192)

    for policy in (LexicalPolicy(), TruncationPolicy("head"), TruncationPolicy("tail")):
        complete_evidence = [
            item.gold_chunk_ids
            <= {span.chunk_id for span in policy.assemble(item.artifact, item.query, budget).spans}
            for item in items
        ]
        assert not all(complete_evidence)

    compositional = [
        item.evaluation_item
        for item in dataset.visible_items()
        if item.task_profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP
    ]
    lexical_complete = [
        item.gold_chunk_ids
        <= {
            span.chunk_id
            for span in LexicalPolicy().assemble(item.artifact, item.query, budget).spans
        }
        for item in compositional
    ]
    assert sum(lexical_complete) <= len(compositional) // 2

    dense = [
        item.evaluation_item
        for item in dataset.visible_items()
        if item.task_profile is HardTaskProfile.DENSE_GLOBAL_COMPARISON
    ]
    dense_lexical_complete = [
        item.gold_chunk_ids
        <= {
            span.chunk_id
            for span in LexicalPolicy().assemble(item.artifact, item.query, budget).spans
        }
        for item in dense
    ]
    assert sum(dense_lexical_complete) <= len(dense) // 2


def _spec_v1(*, hops: GraphHopsV1, allocator: AllocatorV1) -> PolicySpecV1:
    return PolicySpecV1(
        SelectorV1.QUERY_BM25,
        hops,
        allocator,
        PositionReserveV1.NONE,
        OrderV1.RELEVANCE,
    )


def _selected_gold(item: EvaluationItem, spec: PolicySpecV1, budget: Budget) -> frozenset[str]:
    pack = PolicySpecV1Interpreter().materialize(spec).assemble(item.artifact, item.query, budget)
    return frozenset(item.gold_chunk_ids) & {span.chunk_id for span in pack.spans}


def test_compositional_two_hop_rank_does_not_cover_the_full_gold_chain() -> None:
    dataset = _visible_dataset(seed="baseline", items_per_profile=4, requested_tokens=32768)
    budget = Budget(max_tokens=8192)
    compositional = [
        item.evaluation_item
        for item in dataset.visible_items()
        if item.task_profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP
    ]
    two_hop_rank = _spec_v1(hops=GraphHopsV1.TWO, allocator=AllocatorV1.RANK)
    one_hop_rank = _spec_v1(hops=GraphHopsV1.ONE, allocator=AllocatorV1.RANK)
    zero_hop_rank = _spec_v1(hops=GraphHopsV1.ZERO, allocator=AllocatorV1.RANK)

    two_hop_complete = [
        item.gold_chunk_ids <= _selected_gold(item, two_hop_rank, budget) for item in compositional
    ]
    zero_hop_complete = [
        item.gold_chunk_ids <= _selected_gold(item, zero_hop_rank, budget) for item in compositional
    ]
    hop_depth_disagreements = [
        _selected_gold(item, one_hop_rank, budget) != _selected_gold(item, two_hop_rank, budget)
        for item in compositional
    ]

    assert all(len(item.gold_chunk_ids) == 5 for item in compositional)
    assert sum(two_hop_complete) <= len(compositional) // 2
    assert sum(zero_hop_complete) <= sum(two_hop_complete)
    assert sum(hop_depth_disagreements) >= max(1, len(compositional) // 5)


_OPAQUE_ID = re.compile(r"[a-z]{2}-[0-9a-f]{12}")
_FORBIDDEN_COMPOSITIONAL_CUES = (
    "retired",
    "not live",
    "inactive",
    "withdrawn",
    "superseded",
)


def _tokens(text: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def _is_opaque_identifier(token: str) -> bool:
    return (
        len(token) >= 3
        and token.isalnum()
        and any(char.isalpha() for char in token)
        and any(char.isdigit() for char in token)
    )


def _rare_id_graph(texts: tuple[str, ...]) -> list[set[int]]:
    tokenized = tuple(_tokens(text) for text in texts)
    document_frequency = Counter(token for tokens in tokenized for token in frozenset(tokens))
    owners: dict[str, list[int]] = defaultdict(list)
    for index, tokens in enumerate(tokenized):
        for token in frozenset(tokens):
            if _is_opaque_identifier(token) and document_frequency[token] <= 2:
                owners[token].append(index)
    adjacency: list[set[int]] = [set() for _ in texts]
    for indices in owners.values():
        if len(indices) == 2:
            left, right = indices
            adjacency[left].add(right)
            adjacency[right].add(left)
    return adjacency


def _distance_two_neighborhood(adjacency: list[set[int]], seed: int) -> set[int]:
    distances: dict[int, int] = {seed: 0}
    frontier = deque([seed])
    while frontier:
        current = frontier.popleft()
        if distances[current] >= 2:
            continue
        for neighbor in adjacency[current]:
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                frontier.append(neighbor)
    return set(distances)


def _statement_body(text: str) -> str:
    if " states: " in text:
        rest = text.split(" states: ", 1)[1]
        core = rest.split(". ", 1)[0] if ". " in rest else rest
        return _OPAQUE_ID.sub("<id>", core.casefold())
    if " :: " in text:
        parts = text.split(" :: ")
        core = parts[1] if len(parts) > 1 else text
        return _OPAQUE_ID.sub("<id>", core.casefold())
    if " reports that " in text:
        rest = text.split(" reports that ", 1)[1]
        core = rest.split(". ", 1)[0] if ". " in rest else rest
        return _OPAQUE_ID.sub("<id>", core.casefold())
    return _OPAQUE_ID.sub("<id>", text.casefold())


def _compositional_roles(
    private_item: object,
) -> tuple[int, int, int, frozenset[str]]:
    item = private_item.evaluation_item  # type: ignore[attr-defined]
    chunks = item.artifact.chunks
    subject = next(
        token.strip(".,;:[]()") for token in item.query.split() if token.startswith("nd-")
    )
    gold = item.gold_chunk_ids
    a_index = next(
        index
        for index, chunk in enumerate(chunks)
        if chunk.chunk_id in gold and subject in chunk.text
    )
    c_index = next(
        index
        for index, chunk in enumerate(chunks)
        if chunk.chunk_id in gold and item.answer in chunk.text
    )
    a_opaque = frozenset(
        token for token in _tokens(chunks[a_index].text) if _is_opaque_identifier(token)
    )
    b_index = next(
        index
        for index, chunk in enumerate(chunks)
        if chunk.chunk_id in gold
        and index not in {a_index, c_index}
        and a_opaque
        & frozenset(token for token in _tokens(chunk.text) if _is_opaque_identifier(token))
    )
    return a_index, b_index, c_index, gold


def test_compositional_repair_a_locks_document_topology_and_policy_probes() -> None:
    dataset = _visible_dataset(seed="baseline", items_per_profile=4, requested_tokens=32768)
    budget = Budget(max_tokens=8192)
    private_items = [
        item
        for item in dataset.visible_items()
        if item.task_profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP
    ]
    two_hop_rank = _spec_v1(hops=GraphHopsV1.TWO, allocator=AllocatorV1.RANK)
    one_hop_rank = _spec_v1(hops=GraphHopsV1.ONE, allocator=AllocatorV1.RANK)
    zero_hop_rank = _spec_v1(hops=GraphHopsV1.ZERO, allocator=AllocatorV1.RANK)
    two_hop_coverage = _spec_v1(hops=GraphHopsV1.TWO, allocator=AllocatorV1.RARE_COVERAGE)
    zero_hop_mmr = _spec_v1(hops=GraphHopsV1.ZERO, allocator=AllocatorV1.MMR)
    interpreter = PolicySpecV1Interpreter()
    answer_recall_two = []
    answer_recall_one = []
    answer_recall_zero = []
    answer_recall_mmr = []
    coverage_disagreements = 0

    assert MINIMUM_CALIBRATION_ITEMS_PER_PROFILE == 8
    for private_item in private_items:
        item = private_item.evaluation_item
        chunks = item.artifact.chunks
        a_index, b_index, c_index, gold = _compositional_roles(private_item)
        n_chunks = len(chunks)
        thirds = (
            range(0, n_chunks // 3),
            range(n_chunks // 3, 2 * n_chunks // 3),
            range(2 * n_chunks // 3, n_chunks),
        )
        a_third = next(band for band, indices in enumerate(thirds) if a_index in indices)
        b_third = next(band for band, indices in enumerate(thirds) if b_index in indices)
        c_third = next(band for band, indices in enumerate(thirds) if c_index in indices)
        query_ids = frozenset(_OPAQUE_ID.findall(item.query.casefold()))
        gold_b_stripped = _statement_body(chunks[b_index].text)
        gold_c_stripped = _statement_body(chunks[c_index].text)
        competing_b = [
            chunk
            for chunk in chunks
            if chunk.chunk_id not in gold and _statement_body(chunk.text) == gold_b_stripped
        ]
        competing_c = [
            chunk
            for chunk in chunks
            if chunk.chunk_id not in gold and _statement_body(chunk.text) == gold_c_stripped
        ]
        competing_text = " ".join(chunk.text for chunk in (*competing_b, *competing_c)).casefold()
        adjacency = _rare_id_graph(tuple(chunk.text for chunk in chunks))
        neighborhood = _distance_two_neighborhood(adjacency, a_index)
        rule_indices = [
            index
            for index, chunk in enumerate(chunks)
            if chunk.chunk_id in gold and index not in {a_index, b_index, c_index}
        ]
        selected_zero = interpreter.materialize(zero_hop_rank).assemble(
            item.artifact, item.query, budget
        )
        selected_one = interpreter.materialize(one_hop_rank).assemble(
            item.artifact, item.query, budget
        )
        selected_two = interpreter.materialize(two_hop_rank).assemble(
            item.artifact, item.query, budget
        )
        selected_coverage = interpreter.materialize(two_hop_coverage).assemble(
            item.artifact, item.query, budget
        )
        selected_mmr = interpreter.materialize(zero_hop_mmr).assemble(
            item.artifact, item.query, budget
        )
        packed_zero = {span.chunk_id for span in selected_zero.spans}
        packed_one = {span.chunk_id for span in selected_one.spans}
        packed_two = {span.chunk_id for span in selected_two.spans}
        packed_coverage = {span.chunk_id for span in selected_coverage.spans}
        packed_mmr = {span.chunk_id for span in selected_mmr.spans}

        assert len(gold) == 5
        assert len({a_third, b_third, c_third}) == 3
        assert item.answer not in item.query
        assert all(not identifier.startswith(("jx-", "fx-", "au-")) for identifier in query_ids)
        assert sum(item.answer in chunk.text for chunk in chunks) == 1
        assert all(cue not in competing_text for cue in _FORBIDDEN_COMPOSITIONAL_CUES)
        assert len(competing_b) >= 2
        assert len(competing_c) >= 2
        assert len(neighborhood) > 16
        competing_c_indices = {index for index, chunk in enumerate(chunks) if chunk in competing_c}
        assert len(competing_c_indices & neighborhood) >= 2
        for rule_index in rule_indices:
            assert rule_index not in adjacency[a_index]
        assert chunks[c_index].chunk_id not in packed_zero
        assert chunks[a_index].chunk_id in packed_zero
        assert chunks[c_index].chunk_id not in packed_one
        answer_recall_zero.append(chunks[c_index].chunk_id in packed_zero)
        answer_recall_one.append(chunks[c_index].chunk_id in packed_one)
        answer_recall_two.append(chunks[c_index].chunk_id in packed_two)
        answer_recall_mmr.append(chunks[c_index].chunk_id in packed_mmr)
        coverage_disagreements += packed_two != packed_coverage

    assert all(not packed for packed in answer_recall_zero)
    assert all(not packed for packed in answer_recall_one)
    assert 0 < sum(answer_recall_two) < len(answer_recall_two)
    assert coverage_disagreements / len(private_items) >= 0.20
    assert sum(answer_recall_mmr) < len(answer_recall_mmr)


def test_compositional_query_states_seal_match_and_forbids_non_terminal_ids() -> None:
    visible = _visible_dataset(seed="query-contract", items_per_profile=1, requested_tokens=8192)
    hidden = {
        Split.GATE: generate_hard_long_context_split(
            split=Split.GATE,
            evaluator_seed="gate-secret-query-contract-01234567",
            items_per_profile=1,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        ),
        Split.SEALED: generate_hard_long_context_split(
            split=Split.SEALED,
            evaluator_seed="sealed-secret-query-contract-01234567",
            items_per_profile=1,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        ),
    }
    queries = {
        Split.VISIBLE: next(
            item.evaluation_item.query
            for item in visible.visible_items()
            if item.task_profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP
        ),
        Split.GATE: next(
            item.evaluation_item.query
            for item in hidden[Split.GATE].evaluator_items()
            if item.task_profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP
        ),
        Split.SEALED: next(
            item.evaluation_item.query
            for item in hidden[Split.SEALED].evaluator_items()
            if item.task_profile is HardTaskProfile.COMPOSITIONAL_MULTI_HOP
        ),
    }
    for query in queries.values():
        folded = query.casefold()
        assert "registrar" in folded or "seal_match" in folded
        assert "terminal" in folded
        assert "vl-" not in folded
        assert "folio" not in folded
        ids = {token.strip(".,;:[]()") for token in query.split() if "-" in token}
        assert all(not token.startswith(("jx-", "fx-", "au-")) for token in ids)
    visible_query = queries[Split.VISIBLE].casefold()
    assert "seal-match" in visible_query
    assert "return only the exact terminal identifier" in visible_query
    assert "named by that rule" not in visible_query
    assert "registrar seal-match rule" in queries[Split.SEALED].casefold()


def test_dense_query_specifies_aggregation_and_exact_output_contract() -> None:
    dataset = _visible_dataset(seed="dense-floor", items_per_profile=1, requested_tokens=8192)
    dense = next(
        item.evaluation_item
        for item in dataset.visible_items()
        if item.task_profile is HardTaskProfile.DENSE_GLOBAL_COMPARISON
    )

    node_ids = {token.strip(".,;:[]()") for token in dense.query.split() if token.startswith("nd-")}
    assert len(node_ids) == 6
    assert "one accepted score for each" in dense.query.casefold()
    assert "greatest accepted score" in dense.query.casefold()
    assert "return only the exact node id" in dense.query.casefold()
    assert "ds-" not in dense.query.casefold()
    assert "dossier" not in dense.query.casefold()


def test_dense_emits_extractive_score_notes_without_answers() -> None:
    dataset = _visible_dataset(seed="dense-notes", items_per_profile=1, requested_tokens=8192)
    item = next(
        private.evaluation_item
        for private in dataset.visible_items()
        if private.task_profile is HardTaskProfile.DENSE_GLOBAL_COMPARISON
    )
    notes = item.artifact.notes
    gold = item.gold_chunk_ids
    sources = {source for note in notes for source in note.source_chunk_ids}

    assert len(notes) == 6
    assert sources <= gold
    assert all(item.answer not in note.text for note in notes)
    assert all("nd-" not in note.text for note in notes)
    assert all("ds-" in note.text for note in notes)
    assert all(note.token_count == _word_tokens(note.text) for note in notes)
    assert all(
        note.token_count < chunk.token_count
        for note in notes
        for chunk in item.artifact.chunks
        if chunk.chunk_id in note.source_chunk_ids
    )


_DOSSIER_ID = re.compile(r"ds-[0-9a-f]{12}")
_NODE_ID = re.compile(r"nd-[0-9a-f]{12}")


def _dense_roles(item: EvaluationItem) -> tuple[int, tuple[int, ...], tuple[int, ...]]:
    chunks = item.artifact.chunks
    gold = item.gold_chunk_ids
    rule_index = next(
        index
        for index, chunk in enumerate(chunks)
        if chunk.chunk_id in gold
        and _NODE_ID.search(chunk.text) is None
        and _DOSSIER_ID.search(chunk.text) is None
    )
    binding_indices = tuple(
        index
        for index, chunk in enumerate(chunks)
        if chunk.chunk_id in gold
        and _NODE_ID.search(chunk.text) is not None
        and _DOSSIER_ID.search(chunk.text) is not None
    )
    score_indices = tuple(
        index
        for index, chunk in enumerate(chunks)
        if chunk.chunk_id in gold
        and _NODE_ID.search(chunk.text) is None
        and _DOSSIER_ID.search(chunk.text) is not None
    )
    return rule_index, binding_indices, score_indices


def test_dense_repair_c_locks_dossier_split_and_policy_probes() -> None:
    dataset = _visible_dataset(seed="baseline", items_per_profile=4, requested_tokens=32768)
    budget = Budget(max_tokens=8192)
    private_items = [
        item
        for item in dataset.visible_items()
        if item.task_profile is HardTaskProfile.DENSE_GLOBAL_COMPARISON
    ]
    zero_hop_rank = _spec_v1(hops=GraphHopsV1.ZERO, allocator=AllocatorV1.RANK)
    one_hop_rank = _spec_v1(hops=GraphHopsV1.ONE, allocator=AllocatorV1.RANK)
    one_hop_coverage = _spec_v1(hops=GraphHopsV1.ONE, allocator=AllocatorV1.RARE_COVERAGE)
    interpreter = PolicySpecV1Interpreter()
    lexical_complete = []
    coverage_disagreements = 0

    for private_item in private_items:
        item = private_item.evaluation_item
        chunks = item.artifact.chunks
        rule_index, binding_indices, score_indices = _dense_roles(item)
        gold = item.gold_chunk_ids
        adjacency = _rare_id_graph(tuple(chunk.text for chunk in chunks))
        packed_zero = {
            span.chunk_id
            for span in interpreter.materialize(zero_hop_rank)
            .assemble(item.artifact, item.query, budget)
            .spans
        }
        packed_one = {
            span.chunk_id
            for span in interpreter.materialize(one_hop_rank)
            .assemble(item.artifact, item.query, budget)
            .spans
        }
        packed_coverage = {
            span.chunk_id
            for span in interpreter.materialize(one_hop_coverage)
            .assemble(item.artifact, item.query, budget)
            .spans
        }
        gold_dossiers = []
        for binding_index in binding_indices:
            dossiers = _DOSSIER_ID.findall(chunks[binding_index].text)
            gold_dossier = next(
                dossier
                for dossier in dossiers
                if any(dossier in chunks[score_index].text for score_index in score_indices)
            )
            gold_dossiers.append(gold_dossier)
            owners = [index for index, chunk in enumerate(chunks) if gold_dossier in chunk.text]
            assert owners == sorted(
                index
                for index in (*binding_indices, *score_indices)
                if gold_dossier in chunks[index].text
            )
            assert len(owners) == 2
            assert len(adjacency[binding_index]) >= 3
            assert any(
                gold_dossier in chunks[neighbor].text for neighbor in adjacency[binding_index]
            )
        lexical_complete.append(
            gold
            <= {
                span.chunk_id
                for span in LexicalPolicy().assemble(item.artifact, item.query, budget).spans
            }
        )
        coverage_disagreements += packed_one != packed_coverage

        assert len(gold) == 13
        assert len(binding_indices) == 6
        assert len(score_indices) == 6
        assert len(set(gold_dossiers)) == 6
        assert {rule_index, *binding_indices, *score_indices} == {
            index for index, chunk in enumerate(chunks) if chunk.chunk_id in gold
        }
        assert all(chunks[index].chunk_id in packed_zero for index in binding_indices)
        assert all(chunks[index].chunk_id not in packed_zero for index in score_indices)
        assert {chunks[index].chunk_id for index in binding_indices} & packed_one != set()
        assert {chunks[index].chunk_id for index in score_indices} & packed_one != (
            {chunks[index].chunk_id for index in score_indices} & packed_zero
        )
        assert gold - packed_zero
        assert gold - packed_one
        assert gold - packed_coverage

    assert sum(lexical_complete) <= len(private_items) // 2
    assert coverage_disagreements / len(private_items) >= 0.20


def test_researcher_export_stops_at_visible_boundary() -> None:
    dataset = _visible_dataset(seed="private", items_per_profile=1, requested_tokens=8192)

    assert len(dataset.visible_items()) == len(HardTaskProfile)
    assert all(item.split is Split.VISIBLE for item in dataset.visible_items())
    assert not hasattr(dataset, "items")

    gate = generate_hard_long_context_split(
        split=Split.GATE,
        evaluator_seed="gate-secret-private-0123456789abcdef",
        items_per_profile=1,
        requested_tokens=8192,
        token_counter=_word_tokens,
        tokenizer_id="test-word-v1",
    )
    with pytest.raises(ValueError, match="visible"):
        gate.visible_items()
    with pytest.raises(ValueError, match="evaluator secret"):
        generate_hard_long_context_split(
            split=Split.GATE,
            evaluator_seed="public-short-seed",
            items_per_profile=1,
            requested_tokens=8192,
            token_counter=_word_tokens,
            tokenizer_id="test-word-v1",
        )
