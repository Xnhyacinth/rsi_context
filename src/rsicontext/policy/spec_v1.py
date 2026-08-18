"""Evaluator-owned finite policy grammar shared by matched controllers."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import platform
import unicodedata
from collections import Counter, defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias

from .types import Artifact, Budget, ContextPack, DocumentChunk

ConfigScalar: TypeAlias = str | int


class SelectorV1(Enum):
    """Permitted evaluator-owned seed rankings."""

    HEAD = "head"
    TAIL = "tail"
    HEAD_TAIL = "head_tail"
    QUERY_BM25 = "query_bm25"


class GraphHopsV1(Enum):
    """Maximum rare-identifier expansion depth after query seeding."""

    ZERO = 0
    ONE = 1
    TWO = 2


class AllocatorV1(Enum):
    """Fixed whole-chunk allocation objectives."""

    RANK = "rank"
    RARE_COVERAGE = "rare_coverage"
    MMR = "mmr"


class PositionReserveV1(Enum):
    """Fixed source-position reservations applied before allocation."""

    NONE = "none"
    HEAD = "head"
    TAIL = "tail"
    EDGES = "edges"


class OrderV1(Enum):
    """Permitted reader-context orderings."""

    SOURCE = "source"
    RELEVANCE = "relevance"
    EDGE_INTERLEAVE = "edge_interleave"


@dataclass(frozen=True, slots=True)
class PolicySpecV1:
    """An immutable value in the restricted V1 policy grammar."""

    selector: SelectorV1
    graph_hops: GraphHopsV1
    allocator: AllocatorV1
    position_reserve: PositionReserveV1
    order: OrderV1

    def __post_init__(self) -> None:
        fields = (
            (self.selector, SelectorV1, "selector"),
            (self.graph_hops, GraphHopsV1, "graph_hops"),
            (self.allocator, AllocatorV1, "allocator"),
            (self.position_reserve, PositionReserveV1, "position_reserve"),
            (self.order, OrderV1, "order"),
        )
        for value, expected, name in fields:
            if not isinstance(value, expected):
                raise TypeError(f"{name} must be a {expected.__name__} value")
        if self.selector is not SelectorV1.QUERY_BM25 and (
            self.graph_hops is not GraphHopsV1.ZERO
            or self.allocator is not AllocatorV1.RANK
            or self.position_reserve is not PositionReserveV1.NONE
            or self.order is not OrderV1.SOURCE
        ):
            raise ValueError(
                "positional selectors require zero-hop rank allocation in source order"
            )
        if (
            self.position_reserve is not PositionReserveV1.NONE
            and self.order is OrderV1.EDGE_INTERLEAVE
        ):
            raise ValueError("edge-interleave order cannot duplicate an edge position reserve")

    @property
    def canonical_key(self) -> str:
        return ":".join(
            (
                "v1",
                self.selector.value,
                str(self.graph_hops.value),
                self.allocator.value,
                self.position_reserve.value,
                self.order.value,
            )
        )

    def to_config(self) -> Mapping[str, ConfigScalar]:
        return MappingProxyType(
            {
                "version": 1,
                "selector": self.selector.value,
                "graph_hops": self.graph_hops.value,
                "allocator": self.allocator.value,
                "position_reserve": self.position_reserve.value,
                "order": self.order.value,
            }
        )

    @classmethod
    def from_canonical_key(cls, key: object) -> PolicySpecV1:
        if not isinstance(key, str):
            raise TypeError("canonical policy key must be a string")
        try:
            return _POLICY_SPEC_BY_KEY[key]
        except KeyError as error:
            raise ValueError("unknown canonical policy key") from error


def _positional_spec(selector: SelectorV1) -> PolicySpecV1:
    return PolicySpecV1(
        selector,
        GraphHopsV1.ZERO,
        AllocatorV1.RANK,
        PositionReserveV1.NONE,
        OrderV1.SOURCE,
    )


def _query_spec(
    hops: GraphHopsV1,
    allocator: AllocatorV1,
    order: OrderV1,
    reserve: PositionReserveV1 = PositionReserveV1.NONE,
) -> PolicySpecV1:
    return PolicySpecV1(SelectorV1.QUERY_BM25, hops, allocator, reserve, order)


def _canonical_specs() -> tuple[PolicySpecV1, ...]:
    specs = [
        _positional_spec(SelectorV1.HEAD),
        _positional_spec(SelectorV1.TAIL),
        _positional_spec(SelectorV1.HEAD_TAIL),
    ]
    specs.extend(
        _query_spec(hops, allocator, OrderV1.RELEVANCE)
        for hops in GraphHopsV1
        for allocator in AllocatorV1
    )
    specs.extend(
        _query_spec(hops, allocator, order)
        for hops in (GraphHopsV1.ZERO,)
        for allocator in AllocatorV1
        for order in (OrderV1.SOURCE, OrderV1.EDGE_INTERLEAVE)
    )
    specs.extend(
        _query_spec(hops, AllocatorV1.RANK, order)
        for hops in (GraphHopsV1.ONE, GraphHopsV1.TWO)
        for order in (OrderV1.SOURCE, OrderV1.EDGE_INTERLEAVE)
    )
    specs.extend(
        _query_spec(
            GraphHopsV1.ZERO,
            AllocatorV1.RANK,
            order,
            reserve,
        )
        for reserve in (
            PositionReserveV1.HEAD,
            PositionReserveV1.TAIL,
            PositionReserveV1.EDGES,
        )
        for order in (OrderV1.SOURCE, OrderV1.RELEVANCE)
    )
    specs.extend(
        _query_spec(GraphHopsV1.ZERO, allocator, order, PositionReserveV1.EDGES)
        for allocator in (AllocatorV1.RARE_COVERAGE, AllocatorV1.MMR)
        for order in (OrderV1.SOURCE, OrderV1.RELEVANCE)
    )
    return tuple(specs)


CANONICAL_POLICY_SPECS_V1 = _canonical_specs()
_POLICY_SPEC_BY_KEY: Mapping[str, PolicySpecV1] = MappingProxyType(
    {spec.canonical_key: spec for spec in CANONICAL_POLICY_SPECS_V1}
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


def _bm25_scores(tokenized: tuple[tuple[str, ...], ...], query: str) -> tuple[float, ...]:
    query_terms = frozenset(_tokens(query))
    document_count = len(tokenized)
    if not document_count or not query_terms:
        return (0.0,) * document_count
    average_length = sum(len(tokens) for tokens in tokenized) / document_count
    document_frequencies = Counter(token for tokens in tokenized for token in frozenset(tokens))
    k1 = 1.2
    b = 0.75
    scores: list[float] = []
    for tokens in tokenized:
        counts = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = counts[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1
                + (document_count - document_frequencies[term] + 0.5)
                / (document_frequencies[term] + 0.5)
            )
            normalization = 1 - b + b * len(tokens) / average_length
            score += inverse_frequency * (frequency * (k1 + 1) / (frequency + k1 * normalization))
        scores.append(score)
    return tuple(scores)


@dataclass(frozen=True, slots=True)
class _Candidate:
    source_index: int
    relevance: float
    graph_distance: int | None
    rare_ids: frozenset[str]
    terms: frozenset[str]


def _ranked_candidates(
    chunks: tuple[DocumentChunk, ...], query: str, graph_hops: GraphHopsV1
) -> tuple[_Candidate, ...]:
    tokenized = tuple(_tokens(chunk.text) for chunk in chunks)
    scores = _bm25_scores(tokenized, query)
    document_frequency = Counter(token for tokens in tokenized for token in frozenset(tokens))
    rare_by_index = tuple(
        frozenset(
            token
            for token in tokens
            if _is_opaque_identifier(token) and document_frequency[token] <= 2
        )
        for tokens in tokenized
    )
    owners: dict[str, list[int]] = defaultdict(list)
    for index, identifiers in enumerate(rare_by_index):
        for identifier in identifiers:
            owners[identifier].append(index)
    adjacency: list[set[int]] = [set() for _ in chunks]
    for indices in owners.values():
        if len(indices) == 2:
            left, right = indices
            adjacency[left].add(right)
            adjacency[right].add(left)

    query_terms = frozenset(_tokens(query))
    maximum_seed_frequency = max(2, math.isqrt(len(chunks)))
    seed_terms = frozenset(
        token
        for token in query_terms
        if _is_opaque_identifier(token) and 0 < document_frequency[token] <= maximum_seed_frequency
    )
    seed_indices = {
        max(
            (index for index, terms in enumerate(tokenized) if seed_term in terms),
            key=lambda index: (scores[index], -index),
        )
        for seed_term in seed_terms
    }
    distances: dict[int, int] = {}
    frontier: deque[int] = deque()
    for index in sorted(seed_indices):
        distances[index] = 0
        frontier.append(index)
    while frontier:
        current = frontier.popleft()
        distance = distances[current]
        if distance >= graph_hops.value:
            continue
        for neighbor in sorted(adjacency[current]):
            if neighbor not in distances:
                distances[neighbor] = distance + 1
                frontier.append(neighbor)

    def rank_key(index: int) -> tuple[float | int, ...]:
        if index in distances:
            return (0, distances[index], -scores[index], index)
        return (1, -scores[index], index)

    return tuple(
        _Candidate(
            source_index=index,
            relevance=scores[index],
            graph_distance=distances.get(index),
            rare_ids=rare_by_index[index],
            terms=frozenset(tokenized[index]),
        )
        for index in sorted(range(len(chunks)), key=rank_key)
    )


def _edge_interleave(indices: Sequence[int]) -> tuple[int, ...]:
    front: list[int] = []
    back: list[int] = []
    for position, index in enumerate(indices):
        if position % 2 == 0:
            front.append(index)
        else:
            back.insert(0, index)
    return tuple((*front, *back))


def _source_head_tail(length: int) -> tuple[int, ...]:
    indices: list[int] = []
    left = 0
    right = length - 1
    while left <= right:
        indices.append(left)
        if left != right:
            indices.append(right)
        left += 1
        right -= 1
    return tuple(indices)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _mmr_score(
    candidate: _Candidate,
    selected_terms: tuple[frozenset[str], ...],
    rank: Mapping[int, int],
) -> tuple[float, int]:
    novelty = 1.0 - max(
        (_jaccard(candidate.terms, terms) for terms in selected_terms),
        default=0.0,
    )
    rank_relevance = 1.0 / (rank[candidate.source_index] + 1)
    return (0.55 * rank_relevance + 0.45 * novelty, -candidate.source_index)


def _allocate(
    chunks: tuple[DocumentChunk, ...],
    candidates: tuple[_Candidate, ...],
    spec: PolicySpecV1,
    budget: Budget,
) -> tuple[int, ...]:
    selected: list[int] = []
    remaining = budget.max_tokens

    def add(index: int) -> bool:
        nonlocal remaining
        if index in selected:
            return False
        if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
            return False
        if chunks[index].token_count > remaining:
            return False
        selected.append(index)
        remaining -= chunks[index].token_count
        return True

    if chunks:
        if spec.position_reserve in (PositionReserveV1.HEAD, PositionReserveV1.EDGES):
            add(0)
        if spec.position_reserve in (PositionReserveV1.TAIL, PositionReserveV1.EDGES):
            add(len(chunks) - 1)
    if not candidates:
        return tuple(selected)

    rank = {candidate.source_index: index for index, candidate in enumerate(candidates)}
    by_index = {candidate.source_index: candidate for candidate in candidates}
    add(candidates[0].source_index)
    remaining_candidates = [
        candidate for candidate in candidates if candidate.source_index not in selected
    ]
    if spec.allocator is AllocatorV1.RANK:
        for candidate in remaining_candidates:
            add(candidate.source_index)
        return tuple(selected)

    while remaining_candidates:
        if spec.allocator is AllocatorV1.RARE_COVERAGE:
            covered = frozenset().union(
                *(by_index[index].rare_ids for index in selected if index in by_index)
            )
            chosen = max(
                remaining_candidates,
                key=lambda candidate: (
                    int(candidate.graph_distance is not None),
                    len(candidate.rare_ids - covered),
                    -rank[candidate.source_index],
                ),
            )
        else:
            selected_terms = tuple(by_index[index].terms for index in selected if index in by_index)
            chosen = max(
                (
                    (_mmr_score(candidate, selected_terms, rank), candidate)
                    for candidate in remaining_candidates
                ),
                key=lambda scored: scored[0],
            )[1]
        remaining_candidates.remove(chosen)
        add(chosen.source_index)
        if budget.max_chunks is not None and len(selected) >= budget.max_chunks:
            break
        if remaining == 0:
            break
    return tuple(selected)


def _positional_candidates(
    chunks: tuple[DocumentChunk, ...], selector: SelectorV1
) -> tuple[_Candidate, ...]:
    if selector is SelectorV1.HEAD:
        indices = tuple(range(len(chunks)))
    elif selector is SelectorV1.TAIL:
        indices = tuple(reversed(range(len(chunks))))
    else:
        indices = _source_head_tail(len(chunks))
    return tuple(_Candidate(index, 0.0, None, frozenset(), frozenset()) for index in indices)


@dataclass(frozen=True, slots=True)
class PolicySpecV1Policy:
    """The sole evaluator-owned interpreter output for V1 specs."""

    spec: PolicySpecV1

    def assemble(self, artifact: Artifact, query: str, budget: Budget) -> ContextPack:
        if self.spec.selector is SelectorV1.QUERY_BM25:
            candidates = _ranked_candidates(artifact.chunks, query, self.spec.graph_hops)
        else:
            candidates = _positional_candidates(artifact.chunks, self.spec.selector)
        selected_indices = _allocate(artifact.chunks, candidates, self.spec, budget)
        relevance_rank = {
            candidate.source_index: index for index, candidate in enumerate(candidates)
        }
        if self.spec.order is OrderV1.SOURCE:
            ordered_indices = tuple(sorted(selected_indices))
        else:
            relevance_order = tuple(
                sorted(selected_indices, key=lambda index: relevance_rank[index])
            )
            ordered_indices = (
                _edge_interleave(relevance_order)
                if self.spec.order is OrderV1.EDGE_INTERLEAVE
                else relevance_order
            )
        spans = tuple(artifact.chunks[index] for index in selected_indices)
        pack = ContextPack(
            spans=spans,
            ordering=tuple(artifact.chunks[index].chunk_id for index in ordered_indices),
            token_count=sum(chunk.token_count for chunk in spans),
        )
        pack.validate(artifact, budget)
        return pack


@dataclass(frozen=True, slots=True)
class PolicySpecV1Interpreter:
    """Materialize only curated canonical specs."""

    def materialize(self, spec: PolicySpecV1) -> PolicySpecV1Policy:
        if not isinstance(spec, PolicySpecV1):
            raise TypeError("spec must be a PolicySpecV1 value")
        if _POLICY_SPEC_BY_KEY.get(spec.canonical_key) != spec:
            raise ValueError("spec is not in the canonical V1 policy list")
        return PolicySpecV1Policy(spec)


@dataclass(frozen=True, slots=True)
class PolicyCalibrationCaseV1:
    """Evaluator-owned input used only to collapse behavior-equivalent configs."""

    artifact: Artifact
    query: str
    budget: Budget

    def __post_init__(self) -> None:
        if not isinstance(self.artifact, Artifact):
            raise TypeError("artifact must be an Artifact")
        if not isinstance(self.query, str):
            raise TypeError("query must be a string")
        if not isinstance(self.budget, Budget):
            raise TypeError("budget must be a Budget")


@dataclass(frozen=True, slots=True)
class PolicyBehaviorClassV1:
    """One observed context-pack behavior and its equivalent canonical specs."""

    class_id: str
    profile_id: str
    specs: tuple[PolicySpecV1, ...]


def canonical_behavior_classes_v1(
    cases: Sequence[PolicyCalibrationCaseV1],
    *,
    profile_id: str,
) -> tuple[PolicyBehaviorClassV1, ...]:
    """Group canonical specs by exact spans, ordering, and abstention behavior."""

    frozen_cases = tuple(cases)
    if not frozen_cases:
        raise ValueError("behavior calibration requires at least one case")
    if not isinstance(profile_id, str) or not profile_id:
        raise ValueError("profile_id must be a non-empty string")
    if any(not isinstance(case, PolicyCalibrationCaseV1) for case in frozen_cases):
        raise TypeError("cases must contain PolicyCalibrationCaseV1 values")
    interpreter = PolicySpecV1Interpreter()
    grouped: dict[str, list[PolicySpecV1]] = {}
    for spec in CANONICAL_POLICY_SPECS_V1:
        policy = interpreter.materialize(spec)
        behavior = []
        for case in frozen_cases:
            pack = policy.assemble(case.artifact, case.query, case.budget)
            behavior.append(
                {
                    "spans": [span.chunk_id for span in pack.spans],
                    "ordering": list(pack.ordering),
                    "abstain": pack.abstain,
                }
            )
        class_id = _hash({"behavior": behavior, "profile_id": profile_id})
        grouped.setdefault(class_id, []).append(spec)
    return tuple(
        PolicyBehaviorClassV1(class_id, profile_id, tuple(specs))
        for class_id, specs in grouped.items()
    )


def behavior_class_search_space_v1(
    classes: Sequence[PolicyBehaviorClassV1],
) -> Mapping[str, tuple[str, ...]]:
    """Build a per-profile, without-replacement matched-search axis."""

    frozen_classes = tuple(classes)
    if not frozen_classes:
        raise ValueError("behavior class search requires at least one class")
    if any(not isinstance(item, PolicyBehaviorClassV1) for item in frozen_classes):
        raise TypeError("classes must contain PolicyBehaviorClassV1 values")
    if len({item.profile_id for item in frozen_classes}) != 1:
        raise ValueError("behavior class search cannot mix task profiles")
    class_ids = tuple(item.class_id for item in frozen_classes)
    if len(class_ids) != len(set(class_ids)):
        raise ValueError("behavior class ids must be unique")
    return MappingProxyType({"behavior_class": class_ids})


def _hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _source_hash(*values: Callable[..., object]) -> str:
    source = "\n".join(inspect.getsource(value) for value in values)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def policy_spec_v1_config_json() -> bytes:
    """Return canonical JSON bytes for the ordered, curated config list."""

    return json.dumps(
        [dict(spec.to_config()) for spec in CANONICAL_POLICY_SPECS_V1],
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _combined_digest_from_parts(
    spec_source: bytes,
    types_source: bytes,
    config_json: bytes,
    python_version: str,
    unicode_version: str,
) -> str:
    digest = hashlib.sha256()
    parts = (
        (b"spec_v1.py", spec_source),
        (b"types.py", types_source),
        (b"canonical_config.json", config_json),
        (b"python_version", python_version.encode("utf-8")),
        (b"unicode_version", unicode_version.encode("utf-8")),
    )
    for label, payload in parts:
        digest.update(len(label).to_bytes(4, "big"))
        digest.update(label)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def policy_spec_v1_combined_digest() -> str:
    """Bind exact policy sources, configs, Python, and Unicode runtime identity."""

    spec_path = Path(__file__)
    return _combined_digest_from_parts(
        spec_path.read_bytes(),
        spec_path.with_name("types.py").read_bytes(),
        policy_spec_v1_config_json(),
        platform.python_version(),
        unicodedata.unidata_version,
    )


_GRAMMAR_HASH = _hash(
    {
        "version": 1,
        "selector": [item.value for item in SelectorV1],
        "graph_hops": [item.value for item in GraphHopsV1],
        "allocator": [item.value for item in AllocatorV1],
        "position_reserve": [item.value for item in PositionReserveV1],
        "order": [item.value for item in OrderV1],
        "conditions": [
            "positional_is_zero_hop_rank_no_reserve_source_order",
            "edge_interleave_excludes_edge_reserve",
            "materializer_accepts_curated_config_list_only",
        ],
    }
)
_INTERPRETER_HASH = _source_hash(
    _tokens,
    _is_opaque_identifier,
    _bm25_scores,
    _ranked_candidates,
    _edge_interleave,
    _source_head_tail,
    _jaccard,
    _mmr_score,
    _allocate,
    _positional_candidates,
    PolicySpecV1Policy.assemble,
    PolicySpecV1Interpreter.materialize,
)
_CONFIG_LIST_HASH = hashlib.sha256(policy_spec_v1_config_json()).hexdigest()


def policy_spec_v1_hashes() -> Mapping[str, str]:
    """Return immutable identities suitable for evaluator run manifests."""

    return MappingProxyType(
        {
            "grammar": _GRAMMAR_HASH,
            "interpreter": _INTERPRETER_HASH,
            "config_list": _CONFIG_LIST_HASH,
            "combined": policy_spec_v1_combined_digest(),
        }
    )


__all__ = [
    "CANONICAL_POLICY_SPECS_V1",
    "AllocatorV1",
    "GraphHopsV1",
    "OrderV1",
    "PolicyBehaviorClassV1",
    "PolicyCalibrationCaseV1",
    "PolicySpecV1",
    "PolicySpecV1Interpreter",
    "PolicySpecV1Policy",
    "PositionReserveV1",
    "SelectorV1",
    "behavior_class_search_space_v1",
    "canonical_behavior_classes_v1",
    "policy_spec_v1_combined_digest",
    "policy_spec_v1_config_json",
    "policy_spec_v1_hashes",
]
