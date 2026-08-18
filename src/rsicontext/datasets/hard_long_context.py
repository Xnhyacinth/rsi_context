"""Deterministic hard long-context tasks with evaluator-only difficulty controls."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from rsicontext.eval import EvaluationItem
from rsicontext.experiment import Split
from rsicontext.policy import Artifact, CompressedNote, DocumentChunk

NOMINAL_HARD_CONTEXT_TOKENS = 32_768
SUPPORTED_HARD_CONTEXT_TOKENS = frozenset((8_192, 32_768, 131_072, 262_144))
HARD_TARGET_TOKEN_TOLERANCE_FRACTION = 0.02
ABSTENTION_SENTINEL = "INSUFFICIENT"
MINIMUM_CALIBRATION_ITEMS_PER_PROFILE = 8
_TARGET_TOKENS_PER_CHUNK = 512
_COMPOSITIONAL_SPECIAL_SLOTS = 10
_COMPOSITIONAL_SATELLITE_PAIRS = 8
_DENSE_NODE_COUNT = 6
_DENSE_GOLD_CHUNKS = 13
_DENSE_SATELLITE_COUNT = 12
_FORBIDDEN_COMPOSITIONAL_CUES = (
    "retired",
    "not live",
    "inactive",
    "withdrawn",
    "superseded",
)

_FILLER_WORDS = (
    "acorn",
    "bamboo",
    "canyon",
    "drizzle",
    "ember",
    "fabric",
    "granite",
    "harbor",
    "ivory",
    "juniper",
    "kernel",
    "lantern",
    "meadow",
    "nectar",
    "orchard",
    "pebble",
    "quartz",
    "ribbon",
    "saffron",
    "timber",
    "utensil",
    "velvet",
    "willow",
    "yarrow",
    "zephyr",
    "basket",
    "copper",
    "dawn",
    "elm",
    "frost",
    "ginger",
    "hollow",
    "inkwell",
    "jasmine",
    "kettle",
    "linen",
    "mosaic",
    "nickel",
    "oyster",
    "pollen",
    "raven",
    "spruce",
    "tulip",
    "umber",
    "vessel",
    "walnut",
    "xenon",
    "zinnia",
    "anchor",
    "birch",
    "clover",
    "dune",
    "easel",
    "flint",
    "goblet",
    "heather",
    "islet",
    "jigsaw",
    "kiwi",
    "lilac",
    "mantle",
    "noodle",
    "opal",
    "plume",
)


class HardTaskProfile(StrEnum):
    """Evaluator-side labels for distinct evidence-reasoning topologies."""

    COMPOSITIONAL_MULTI_HOP = "compositional_multihop"
    DENSE_GLOBAL_COMPARISON = "dense_global_comparison"
    TEMPORAL_STATE_RESOLUTION = "temporal_state_resolution"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidencePosition(StrEnum):
    """Evaluator-side control for where required evidence occurs in the artifact."""

    HEAD = "head"
    MIDDLE = "middle"
    TAIL = "tail"
    DISTRIBUTED = "distributed"


@dataclass(frozen=True, slots=True)
class _Family:
    name: str
    archive: str
    record: str
    credential: str
    property_name: str
    grammar: str


_FAMILY_NAMES = {
    Split.VISIBLE: ("calyx", "dorado", "fennel", "ibex"),
    Split.GATE: ("jacinth", "kumquat", "lotus", "marten"),
    Split.SEALED: ("narwhal", "onyx", "papyrus", "quince"),
}
_PROFILE_TERMS = {
    HardTaskProfile.COMPOSITIONAL_MULTI_HOP: ("folio", "writ", "cipher"),
    HardTaskProfile.DENSE_GLOBAL_COMPARISON: ("slip", "crest", "unit"),
    HardTaskProfile.TEMPORAL_STATE_RESOLUTION: ("entry", "sigil", "status"),
    HardTaskProfile.INSUFFICIENT_EVIDENCE: ("notice", "signet", "state"),
}
_FAMILIES = {
    (split, profile): _Family(
        name=(
            f"{_FAMILY_NAMES[split][profile_index]}-"
            f"{('ledger', 'card', 'dispatch')[tuple(Split).index(split)]}-v3"
        ),
        archive=_FAMILY_NAMES[split][profile_index],
        record=terms[0],
        credential=terms[1],
        property_name=terms[2],
        grammar=("ledger", "card", "dispatch")[tuple(Split).index(split)],
    )
    for split in Split
    for profile_index, profile in enumerate(HardTaskProfile)
    for terms in (_PROFILE_TERMS[profile],)
}


@dataclass(frozen=True, slots=True)
class HardPrivateItem:
    """Evaluator metadata; only visible instances may cross the researcher boundary."""

    split: Split
    task_profile: HardTaskProfile
    template_family: str
    evidence_position: EvidencePosition
    requested_target_tokens: int
    source_target_tokens: int
    semantic_word_count: int
    minimum_evidence_chunks: int
    requires_abstention: bool
    evaluation_item: EvaluationItem


@dataclass(frozen=True, slots=True)
class HardLongContextDataset:
    """One split generated from one split-private seed inside its owning boundary."""

    split: Split
    _evaluator_items: tuple[HardPrivateItem, ...]
    requested_target_tokens: int
    target_token_tolerance: int
    fingerprint: str
    tokenizer_id: str

    def __post_init__(self) -> None:
        if not self._evaluator_items:
            raise ValueError("hard long-context split must contain items")
        if any(item.split is not self.split for item in self._evaluator_items):
            raise ValueError("hard dataset cannot mix visibility splits")

    def visible_items(self) -> tuple[HardPrivateItem, ...]:
        if self.split is not Split.VISIBLE:
            raise ValueError("only a visible split may cross the researcher boundary")
        return self._evaluator_items

    def evaluator_items(self) -> tuple[HardPrivateItem, ...]:
        return self._evaluator_items

    @property
    def source_token_counts(self) -> tuple[int, ...]:
        return tuple(
            sum(chunk.token_count for chunk in item.evaluation_item.artifact.chunks)
            for item in self._evaluator_items
        )

    @property
    def semantic_word_counts(self) -> tuple[int, ...]:
        return tuple(item.semantic_word_count for item in self._evaluator_items)


def _digest(seed: str, split: Split, profile: HardTaskProfile, index: int) -> bytes:
    payload = f"hard-v3\x00{seed}\x00{split.value}\x00{profile.value}\x00{index}"
    return hashlib.sha256(payload.encode()).digest()


def _opaque(prefix: str, digest: bytes, discriminator: str) -> str:
    value = hashlib.sha256(digest + b"\x00" + discriminator.encode()).hexdigest()[:12]
    return f"{prefix}-{value}"


def _count_tokens(token_counter: Callable[[str], int], text: str) -> int:
    count = token_counter(text)
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("target tokenizer counts must be positive integers")
    return count


def _hard_dataset_fingerprint(
    items: tuple[HardPrivateItem, ...],
    *,
    requested_tokens: int,
    tokenizer_id: str,
) -> str:
    """Bind every policy- or evaluator-relevant item field into the split identity."""

    canonical = {
        "fingerprint_schema_version": 3,
        "items": [
            {
                "answer": item.evaluation_item.answer,
                "artifact_document_id": item.evaluation_item.artifact.document_id,
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "end": chunk.end,
                        "start": chunk.start,
                        "text_sha256": hashlib.sha256(chunk.text.encode()).hexdigest(),
                        "token_count": chunk.token_count,
                    }
                    for chunk in item.evaluation_item.artifact.chunks
                ],
                "family": item.template_family,
                "gold": sorted(item.evaluation_item.gold_chunk_ids),
                "item_id": item.evaluation_item.item_id,
                "notes": [
                    {
                        "note_id": note.note_id,
                        "source_chunk_ids": list(note.source_chunk_ids),
                        "text_sha256": hashlib.sha256(note.text.encode()).hexdigest(),
                        "token_count": note.token_count,
                    }
                    for note in item.evaluation_item.artifact.notes
                ],
                "position": item.evidence_position.value,
                "profile": item.task_profile.value,
                "query": item.evaluation_item.query,
                "split": item.split.value,
            }
            for item in items
        ],
        "requested_target_tokens": requested_tokens,
        "source_target_tokens": [item.source_target_tokens for item in items],
        "semantic_word_counts": [item.semantic_word_count for item in items],
        "tokenizer_id": tokenizer_id,
    }
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _styled_sentence(split: Split, sentence: str, digest: bytes, chunk_index: int) -> str:
    serial = hashlib.sha256(digest + chunk_index.to_bytes(4, "big")).hexdigest()[:8]
    if split is Split.VISIBLE:
        return f"Ledger {serial} states: {sentence}"
    if split is Split.GATE:
        return f"CARD[{serial}] :: {sentence} :: close"
    return f"Dispatch {serial} reports that {sentence}"


def _padded_text(
    sentence: str,
    digest: bytes,
    chunk_index: int,
    *,
    split: Split,
    token_counter: Callable[[str], int],
) -> tuple[str, int]:
    styled = _styled_sentence(split, sentence, digest, chunk_index)
    if _count_tokens(token_counter, styled) > _TARGET_TOKENS_PER_CHUNK:
        raise ValueError("hard task statement exceeds its target-token chunk budget")
    offset = (digest[chunk_index % len(digest)] + 19 * chunk_index) % len(_FILLER_WORDS)

    def candidate(filler_count: int) -> str:
        filler = " ".join(
            _FILLER_WORDS[(offset + 23 * word_index) % len(_FILLER_WORDS)]
            for word_index in range(filler_count)
        )
        return styled if not filler else f"{styled} {filler}"

    low = 0
    high = _TARGET_TOKENS_PER_CHUNK * 2
    while _count_tokens(token_counter, candidate(high)) <= _TARGET_TOKENS_PER_CHUNK:
        high *= 2
        if high > _TARGET_TOKENS_PER_CHUNK * 64:
            raise ValueError("target tokenizer does not increase with generated filler")
    while low + 1 < high:
        middle = (low + high) // 2
        if _count_tokens(token_counter, candidate(middle)) <= _TARGET_TOKENS_PER_CHUNK:
            low = middle
        else:
            high = middle
    text = candidate(low)
    return text, _count_tokens(token_counter, text)


def _third_bounds(chunk_count: int) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    return (
        (0, chunk_count // 3),
        (chunk_count // 3, (2 * chunk_count) // 3),
        ((2 * chunk_count) // 3, chunk_count),
    )


def _abc_thirds(position: EvidencePosition) -> tuple[int, int, int]:
    if position is EvidencePosition.HEAD:
        return 0, 1, 2
    if position is EvidencePosition.MIDDLE:
        return 1, 0, 2
    if position is EvidencePosition.TAIL:
        return 2, 0, 1
    return 0, 1, 2


def _claim_index(
    occupied: set[int],
    lo: int,
    hi: int,
    *,
    prefer: int | None = None,
) -> int:
    free = [index for index in range(lo, hi) if index not in occupied]
    if not free:
        raise AssertionError("compositional placement exhausted a band")
    if prefer is not None and prefer in free:
        chosen = prefer
    else:
        center = (lo + hi) // 2
        chosen = min(free, key=lambda index: (abs(index - center), index))
    occupied.add(chosen)
    return chosen


def _claim_unoccupied(
    occupied: set[int],
    chunk_count: int,
    *,
    avoid_adjacent: frozenset[int] = frozenset(),
    prefer_high: bool = False,
) -> int:
    free = [index for index in range(chunk_count) if index not in occupied]
    if not free:
        raise AssertionError("compositional placement exhausted the artifact")
    preferred = [
        index for index in free if all(abs(index - neighbor) != 1 for neighbor in avoid_adjacent)
    ]
    pool = preferred or free
    chosen = pool[-1] if prefer_high else pool[0]
    occupied.add(chosen)
    return chosen


def _compositional_binding(split: Split, junction: str, folio: str, seal: str) -> str:
    if split is Split.VISIBLE:
        return f"Binding {junction} forwards to folio {folio} with seal {seal}."
    if split is Split.GATE:
        return f"origin={junction}; verified_by={seal}; successor={folio}"
    return f"the endorsed continuation from {junction} arrived at folio {folio} under {seal}."


def _compositional_payload(split: Split, family: _Family, folio: str, terminal: str) -> str:
    if split is Split.VISIBLE:
        return (
            f"The {family.archive} {family.record} bound onto folio {folio} lists {terminal} "
            f"as {family.property_name}."
        )
    if split is Split.GATE:
        return f"folio={folio}; field={family.property_name}; value={terminal}; status=bound"
    return f"reviewer notes that folio {folio} listed {terminal} as the {family.property_name}."


def _compositional_seed(
    split: Split,
    subject: str,
    cycle: int,
    junctions: tuple[str, str, str],
    pairs: tuple[str, ...],
) -> str:
    junction_list = ", ".join(junctions)
    pair_clause = f"; collateral pairs are {', '.join(pairs)}" if pairs else ""
    if split is Split.VISIBLE:
        return (
            f"The active route for {subject} at cycle {cycle} names junctions "
            f"{junction_list}{pair_clause}."
        )
    if split is Split.GATE:
        pair_field = f"; pairs={','.join(pairs)}" if pairs else ""
        return f"epoch={cycle}; bearer={subject}; junctions={junction_list}{pair_field}"
    return (
        f"the current dispatch moved {subject} through junctions {junction_list} "
        f"during season {cycle}{pair_clause}."
    )


def _compositional_rule(split: Split, cycle: int, authority: str) -> str:
    if split is Split.VISIBLE:
        return (
            f"The live continuation is the junction whose seal equals registrar "
            f"{authority} for cycle {cycle}."
        )
    if split is Split.GATE:
        return f"rule=seal_match; epoch={cycle}; registrar={authority}"
    return (
        f"the current rule keeps the junction whose seal matches registrar "
        f"{authority} in season {cycle}."
    )


def _compositional_registrar(split: Split, cycle: int, authority: str) -> str:
    if split is Split.VISIBLE:
        return f"The cycle {cycle} registrar is {authority}."
    if split is Split.GATE:
        return f"epoch={cycle}; registrar={authority}; role=cycle_registrar"
    return f"season {cycle} names registrar {authority}."


def _compositional_satellite(split: Split, pair_id: str, leaf_id: str, variant: int) -> str:
    if split is Split.VISIBLE:
        if variant % 2 == 0:
            return f"The collateral ledger note pairs {pair_id} with {leaf_id}."
        return f"The paired satellite record binds {pair_id} onto {leaf_id}."
    if split is Split.GATE:
        return f"role=satellite; pair={pair_id}; leaf={leaf_id}; variant={variant % 2}"
    return f"a collateral dispatch paired {pair_id} with {leaf_id}."


def _dense_rule(split: Split, cycle: int, authority: str) -> str:
    if split is Split.VISIBLE:
        return (
            f"Qualification rule for cycle {cycle}: for each listed node accept exactly one "
            f"score bearing seal {authority}, reject every other cycle or seal, and choose the "
            "greatest accepted score."
        )
    if split is Split.GATE:
        return f"rule=max1; epoch={cycle}; required_seal={authority}; foreign_records=reject"
    return (
        f"the review board retained one figure bearing {authority} for each named node in "
        f"season {cycle}, discarded other seasons and reviewers, and chose the greatest."
    )


def _dense_binding(
    split: Split,
    node: str,
    dossier: str,
    cycle: int,
    *,
    pairs: tuple[str, ...],
    competing: str | None,
) -> str:
    pair_list = ", ".join(pairs)
    if split is Split.VISIBLE:
        pair_clause = f"; collateral notes {pair_list}" if pairs else ""
        competing_clause = f"; a parallel slip cites {competing}" if competing else ""
        return (
            f"Node {node} is recorded on dossier {dossier} for the qualification rule in "
            f"cycle {cycle}{pair_clause}{competing_clause}."
        )
    if split is Split.GATE:
        pair_field = f"; notes={pair_list}" if pairs else ""
        competing_field = f"; parallel={competing}" if competing else ""
        return (
            f"node={node}; dossier={dossier}; epoch={cycle}; role=qualification_binding"
            f"{pair_field}{competing_field}"
        )
    pair_clause = f" with notes {pair_list}" if pairs else ""
    competing_clause = f"; a parallel slip cites {competing}" if competing else ""
    return (
        f"the board filed {node} on dossier {dossier} for season {cycle}"
        f"{pair_clause}{competing_clause}."
    )


def _dense_score(split: Split, dossier: str, score: int, authority: str) -> str:
    if split is Split.VISIBLE:
        return f"Dossier {dossier} records score {score} under seal {authority}."
    if split is Split.GATE:
        return f"dossier={dossier}; score={score}; seal={authority}; status=retained"
    return f"dossier {dossier} kept figure {score} under {authority}."


def _dense_roster(split: Split, node: str) -> str:
    if split is Split.VISIBLE:
        return f"Node {node} is listed on a collateral roster without a retained figure."
    if split is Split.GATE:
        return f"node={node}; role=collateral_roster; figure=absent"
    return f"a collateral roster listed {node} without a retained figure."


def _dense_split_grammar_decoys(
    split: Split, cycle: int, authority: str, digest: bytes
) -> tuple[str, str]:
    decoy_authority = _opaque("au", digest, "decoy-authority-grammar")
    if split is Split.VISIBLE:
        return (
            (
                f"A near-match accepted score 96 was filed, but its actual cycle is {cycle + 1}, "
                f"not qualification cycle {cycle}; seal {authority}."
            ),
            (
                f"A record claims accepted score 88 in cycle {cycle}, but bears foreign seal "
                f"{decoy_authority}."
            ),
        )
    if split is Split.GATE:
        return (
            (
                f"epoch={cycle + 1}; requested_epoch={cycle}; score=96; seal={authority}; "
                "status=rejected_epoch"
            ),
            f"epoch={cycle}; score=88; seal={decoy_authority}; status=rejected_seal",
        )
    return (
        (
            f"a prior-season reviewer {authority} recorded 96, but the entry belonged to "
            f"season {cycle + 1} rather than {cycle}."
        ),
        (
            f"an unrecognized reviewer {decoy_authority} proposed 88 during season {cycle}; "
            "the board discarded it."
        ),
    )


def _evidence_indices(
    *, chunk_count: int, evidence_count: int, position: EvidencePosition
) -> tuple[int, ...]:
    if evidence_count > chunk_count:
        raise AssertionError("evidence count exceeds artifact chunk count")
    if position is EvidencePosition.HEAD:
        start = 0
    elif position is EvidencePosition.MIDDLE:
        start = (chunk_count - evidence_count) // 2
    elif position is EvidencePosition.TAIL:
        start = chunk_count - evidence_count
    else:
        if evidence_count == 1:
            return (chunk_count // 2,)
        return tuple(
            round(index * (chunk_count - 1) / (evidence_count - 1))
            for index in range(evidence_count)
        )
    return tuple(range(start, start + evidence_count))


def _chunks(
    *,
    document_id: str,
    sentences: tuple[str, ...],
    evidence_indices: tuple[int, ...],
    digest: bytes,
    split: Split,
    token_counter: Callable[[str], int],
) -> tuple[tuple[DocumentChunk, ...], frozenset[str]]:
    chunks: list[DocumentChunk] = []
    gold_ids: set[str] = set()
    cursor = 0
    for index, sentence in enumerate(sentences):
        text, token_count = _padded_text(
            sentence,
            digest,
            index,
            split=split,
            token_counter=token_counter,
        )
        chunk_id = f"ck-{hashlib.sha256(f'{document_id}:{index}'.encode()).hexdigest()[:16]}"
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                start=cursor,
                end=cursor + len(text),
                text=text,
                token_count=token_count,
            )
        )
        if index in evidence_indices:
            gold_ids.add(chunk_id)
        cursor += len(text) + 1
    return tuple(chunks), frozenset(gold_ids)


def _distractors(
    *,
    split: Split,
    family: _Family,
    digest: bytes,
    chunk_count: int,
    cycle: int,
) -> list[str]:
    sentences = []
    for index in range(chunk_count):
        subject = _opaque("nd", digest, f"d-subject-{index}")
        value = _opaque("vl", digest, f"d-value-{index}")
        issuer = _opaque("au", digest, f"d-issuer-{index}")
        if split is Split.VISIBLE:
            sentence = (
                f"The {family.archive} {family.record} for {subject} in cycle "
                f"{cycle + index % 7} lists {value} as its {family.property_name} under "
                f"{family.credential} {issuer}."
            )
        elif split is Split.GATE:
            sentence = (
                f"epoch={cycle + index % 5}; bearer={subject}; field={family.property_name}; "
                f"value={value}; seal={issuer}; status=provisional"
            )
        else:
            sentence = (
                f"reviewer {issuer} recalled {value} for {subject}, but the dispatch concerns "
                f"season {cycle + index % 9} and leaves the {family.property_name} unconfirmed."
            )
        sentences.append(sentence)
    return sentences


def _make_private_item(
    *,
    split: Split,
    profile: HardTaskProfile,
    family: _Family,
    position: EvidencePosition,
    requested_tokens: int,
    digest: bytes,
    query: str,
    answer: str,
    sentences: list[str],
    evidence_indices: tuple[int, ...],
    token_counter: Callable[[str], int],
    requires_abstention: bool = False,
    note_indices: tuple[int, ...] = (),
) -> HardPrivateItem:
    document_id = f"hx-{digest.hex()[:20]}"
    chunks, gold_ids = _chunks(
        document_id=document_id,
        sentences=tuple(sentences),
        evidence_indices=evidence_indices,
        digest=digest,
        split=split,
        token_counter=token_counter,
    )
    source_target_tokens = sum(chunk.token_count for chunk in chunks)
    semantic_word_count = sum(len(chunk.text.split()) for chunk in chunks)
    tolerance = math.ceil(requested_tokens * HARD_TARGET_TOKEN_TOLERANCE_FRACTION)
    if abs(source_target_tokens - requested_tokens) > tolerance:
        raise ValueError("generated source is outside the target-token tolerance")
    notes = tuple(
        CompressedNote(
            note_id=(
                "nt-"
                + hashlib.sha256(f"{document_id}:{chunks[index].chunk_id}".encode()).hexdigest()[
                    :16
                ]
            ),
            source_chunk_ids=(chunks[index].chunk_id,),
            text=sentences[index],
            token_count=_count_tokens(token_counter, sentences[index]),
        )
        for index in note_indices
    )
    if any(answer in note.text for note in notes):
        raise AssertionError("extractive notes must not contain the item answer")
    return HardPrivateItem(
        split=split,
        task_profile=profile,
        template_family=family.name,
        evidence_position=position,
        requested_target_tokens=requested_tokens,
        source_target_tokens=source_target_tokens,
        semantic_word_count=semantic_word_count,
        minimum_evidence_chunks=len(evidence_indices),
        requires_abstention=requires_abstention,
        evaluation_item=EvaluationItem(
            item_id=document_id,
            query=query,
            answer=answer,
            artifact=Artifact(document_id=document_id, chunks=chunks, notes=notes),
            gold_chunk_ids=gold_ids,
        ),
    )


def _compositional_item(
    *,
    seed: str,
    split: Split,
    index: int,
    family: _Family,
    requested_tokens: int,
    token_counter: Callable[[str], int],
) -> HardPrivateItem:
    profile = HardTaskProfile.COMPOSITIONAL_MULTI_HOP
    digest = _digest(seed, split, profile, index)
    position = tuple(EvidencePosition)[index % len(EvidencePosition)]
    chunk_count = requested_tokens // _TARGET_TOKENS_PER_CHUNK
    if chunk_count < _COMPOSITIONAL_SPECIAL_SLOTS:
        raise AssertionError("compositional artifacts need at least ten specialized chunks")
    cycle = 100 + digest[0]
    subject = _opaque("nd", digest, "subject")
    junctions = (
        _opaque("jx", digest, "live-0"),
        _opaque("jx", digest, "live-1"),
        _opaque("jx", digest, "live-2"),
    )
    folio = _opaque("fx", digest, "folio")
    answer = _opaque("vl", digest, "answer")
    authority = _opaque("au", digest, "authority")
    competing_folios = tuple(_opaque("fx", digest, f"competing-folio-{path}") for path in range(2))
    competing_terminals = tuple(
        _opaque("vl", digest, f"competing-terminal-{path}") for path in range(2)
    )
    competing_seals = tuple(_opaque("au", digest, f"competing-seal-{path}") for path in range(2))
    pair_count = min(
        _COMPOSITIONAL_SATELLITE_PAIRS,
        (chunk_count - _COMPOSITIONAL_SPECIAL_SLOTS) // 2,
    )
    pair_ids = tuple(_opaque("px", digest, f"pair-{pair}") for pair in range(pair_count))
    leaf_ids = tuple(_opaque("lx", digest, f"leaf-{pair}") for pair in range(pair_count))
    sentences = _distractors(
        split=split,
        family=family,
        digest=digest,
        chunk_count=chunk_count,
        cycle=cycle,
    )
    occupied: set[int] = set()
    thirds = _third_bounds(chunk_count)
    a_third, b_third, c_third = _abc_thirds(position)
    a_index = _claim_index(occupied, *thirds[a_third])
    b_index = _claim_index(occupied, *thirds[b_third])
    c_index = _claim_index(occupied, *thirds[c_third])
    competing_b = tuple(_claim_index(occupied, *thirds[b_third]) for _ in range(2))
    competing_c = tuple(_claim_index(occupied, *thirds[c_third]) for _ in range(2))
    path_indices = frozenset((a_index, b_index, c_index))
    r_index = _claim_unoccupied(occupied, chunk_count, avoid_adjacent=path_indices)
    m_index = _claim_unoccupied(occupied, chunk_count, avoid_adjacent=path_indices)
    decoy_index = _claim_unoccupied(occupied, chunk_count, avoid_adjacent=frozenset({c_index}))
    satellite_indices = tuple(_claim_unoccupied(occupied, chunk_count) for _ in range(pair_count))
    partner_indices = tuple(
        _claim_unoccupied(
            occupied,
            chunk_count,
            prefer_high=position is EvidencePosition.TAIL,
        )
        for _ in range(pair_count)
    )
    sentences[a_index] = _compositional_seed(split, subject, cycle, junctions, pair_ids)
    sentences[b_index] = _compositional_binding(split, junctions[0], folio, authority)
    sentences[c_index] = _compositional_payload(split, family, folio, answer)
    sentences[r_index] = _compositional_rule(split, cycle, authority)
    sentences[m_index] = _compositional_registrar(split, cycle, authority)
    for path, (binding_index, payload_index) in enumerate(
        zip(competing_b, competing_c, strict=True)
    ):
        sentences[binding_index] = _compositional_binding(
            split, junctions[path + 1], competing_folios[path], competing_seals[path]
        )
        sentences[payload_index] = _compositional_payload(
            split, family, competing_folios[path], competing_terminals[path]
        )
    competing_text = " ".join(sentences[index] for index in (*competing_b, *competing_c)).casefold()
    if any(cue in competing_text for cue in _FORBIDDEN_COMPOSITIONAL_CUES):
        raise AssertionError("competing compositional path contains a local status cue")
    for pair, (satellite_index, partner_index) in enumerate(
        zip(satellite_indices, partner_indices, strict=True)
    ):
        sentences[satellite_index] = _compositional_satellite(
            split, pair_ids[pair], leaf_ids[pair], variant=pair
        )
        sentences[partner_index] = _compositional_satellite(
            split, leaf_ids[pair], _opaque("qx", digest, f"dead-{pair}"), variant=pair + 1
        )
    unrelated_subject = _opaque("nd", digest, "unrelated-subject")
    quoted_terminal = _opaque("vl", digest, "decoy-quoted-terminal")
    if split is Split.VISIBLE:
        sentences[decoy_index] = (
            f"An unrelated audit quotes terminal-shaped value {quoted_terminal} for "
            f"{unrelated_subject}, not for {subject}."
        )
        query = (
            f"Trace the active route for {subject} in cycle {cycle}. "
            "Apply the cycle registrar's seal-match rule. "
            "Return only the exact terminal identifier."
        )
    elif split is Split.GATE:
        sentences[decoy_index] = (
            f"scope=mismatch; quoted_terminal={quoted_terminal}; bearer={unrelated_subject}; "
            f"excluded_bearer={subject}"
        )
        query = (
            f"Trace valid successor fields from bearer {subject} at epoch {cycle}; apply "
            "rule=seal_match; emit only the terminal identifier."
        )
    else:
        sentences[decoy_index] = (
            f"a separate review quoted {quoted_terminal} for {unrelated_subject}; its subject "
            f"was not {subject}."
        )
        query = (
            f"Which terminal identifier is delivered by the current dispatch that starts "
            f"with {subject} in season {cycle}? Apply the registrar seal-match rule and "
            "reply with only that terminal identifier."
        )
    evidence_indices = tuple(sorted((a_index, b_index, c_index, r_index, m_index)))
    return _make_private_item(
        split=split,
        profile=profile,
        family=family,
        position=position,
        requested_tokens=requested_tokens,
        digest=digest,
        query=query,
        answer=answer,
        sentences=sentences,
        evidence_indices=evidence_indices,
        token_counter=token_counter,
    )


def _dense_item(
    *,
    seed: str,
    split: Split,
    index: int,
    family: _Family,
    requested_tokens: int,
    token_counter: Callable[[str], int],
) -> HardPrivateItem:
    profile = HardTaskProfile.DENSE_GLOBAL_COMPARISON
    digest = _digest(seed, split, profile, index)
    position = tuple(EvidencePosition)[index % len(EvidencePosition)]
    chunk_count = requested_tokens // _TARGET_TOKENS_PER_CHUNK
    if chunk_count < _DENSE_GOLD_CHUNKS + 1:
        raise AssertionError("dense artifacts need gold chunks plus a split-grammar decoy")
    evidence_indices = _evidence_indices(
        chunk_count=chunk_count, evidence_count=_DENSE_GOLD_CHUNKS, position=position
    )
    if len(set(evidence_indices)) != _DENSE_GOLD_CHUNKS:
        raise AssertionError("dense gold indices collided")
    leftover_n = chunk_count - _DENSE_GOLD_CHUNKS
    ngram_slots = 2 if leftover_n >= 8 else 1
    remain = leftover_n - ngram_slots
    winner_rosters = min(2, remain)
    remain -= winner_rosters
    competing_n = min(_DENSE_NODE_COUNT, remain)
    remain -= competing_n
    other_rosters = min(2 * (_DENSE_NODE_COUNT - 1), remain)
    remain -= other_rosters
    satellite_n = min(_DENSE_SATELLITE_COUNT, remain)
    satellite_n -= satellite_n % 2
    if satellite_n != _DENSE_SATELLITE_COUNT:
        satellite_n = 0
    cycle = 300 + digest[0]
    nodes = tuple(
        _opaque("nd", digest, f"node-{candidate}") for candidate in range(_DENSE_NODE_COUNT)
    )
    winner_index = digest[1] % len(nodes)
    answer = nodes[winner_index]
    ranked_scores = (91, 74, 68, 62, 55, 49)
    candidate_scores = [
        ranked_scores[(candidate - winner_index) % len(ranked_scores)]
        for candidate in range(len(nodes))
    ]
    gold_dossiers = tuple(
        _opaque("ds", digest, f"dossier-{candidate}") for candidate in range(_DENSE_NODE_COUNT)
    )
    competing_dossiers = tuple(
        _opaque("ds", digest, f"competing-{candidate}") for candidate in range(competing_n)
    )
    pair_ids = tuple(_opaque("px", digest, f"pair-{pair}") for pair in range(satellite_n))
    leaf_ids = tuple(_opaque("lx", digest, f"leaf-{pair}") for pair in range(satellite_n))
    sentences = _distractors(
        split=split,
        family=family,
        digest=digest,
        chunk_count=chunk_count,
        cycle=cycle,
    )
    authority = _opaque("au", digest, "authority")
    sentences[evidence_indices[0]] = _dense_rule(split, cycle, authority)
    for offset, (node, dossier, score) in enumerate(
        zip(nodes, gold_dossiers, candidate_scores, strict=True)
    ):
        pairs = (
            pair_ids[2 * offset : 2 * offset + 2] if satellite_n == _DENSE_SATELLITE_COUNT else ()
        )
        competing = competing_dossiers[offset] if offset < competing_n else None
        sentences[evidence_indices[1 + offset]] = _dense_binding(
            split, node, dossier, cycle, pairs=pairs, competing=competing
        )
        sentences[evidence_indices[1 + _DENSE_NODE_COUNT + offset]] = _dense_score(
            split, dossier, score, authority
        )
    leftover = [
        chunk_index for chunk_index in range(chunk_count) if chunk_index not in evidence_indices
    ]
    cursor = 0
    wrong_cycle, wrong_seal = _dense_split_grammar_decoys(split, cycle, authority, digest)
    if ngram_slots == 1:
        sentences[leftover[cursor]] = f"{wrong_cycle} {wrong_seal}"
        cursor += 1
    else:
        sentences[leftover[cursor]] = wrong_cycle
        sentences[leftover[cursor + 1]] = wrong_seal
        cursor += 2
    for _ in range(winner_rosters):
        sentences[leftover[cursor]] = _dense_roster(split, answer)
        cursor += 1
    for competing_offset, competing_dossier in enumerate(competing_dossiers):
        competing_authority = _opaque("au", digest, f"competing-seal-{competing_offset}")
        sentences[leftover[cursor]] = _dense_score(
            split,
            competing_dossier,
            96 + competing_offset,
            competing_authority,
        )
        cursor += 1
    other_nodes = [node for node in nodes if node != answer]
    for roster_number in range(other_rosters):
        sentences[leftover[cursor]] = _dense_roster(
            split, other_nodes[roster_number % len(other_nodes)]
        )
        cursor += 1
    for pair, pair_id in enumerate(pair_ids):
        sentences[leftover[cursor]] = _compositional_satellite(
            split, pair_id, leaf_ids[pair], variant=pair
        )
        cursor += 1
    node_list = ", ".join(nodes)
    if split is Split.VISIBLE:
        query = (
            f"For nodes {node_list}, apply the qualification rule to find one accepted score "
            f"for each in cycle {cycle}, then choose the greatest accepted score. Return only "
            "the exact node ID."
        )
    elif split is Split.GATE:
        query = (
            f"candidates=[{node_list}]; epoch={cycle}; operation=max_valid_score; output=node_id"
        )
    else:
        query = (
            f"Which of {node_list} received the greatest retained score in season {cycle}? "
            "Respond with only that exact node ID."
        )
    return _make_private_item(
        split=split,
        profile=profile,
        family=family,
        position=position,
        requested_tokens=requested_tokens,
        digest=digest,
        query=query,
        answer=answer,
        sentences=sentences,
        evidence_indices=evidence_indices,
        token_counter=token_counter,
        note_indices=evidence_indices[1 + _DENSE_NODE_COUNT :],
    )


def _temporal_item(
    *,
    seed: str,
    split: Split,
    index: int,
    family: _Family,
    requested_tokens: int,
    token_counter: Callable[[str], int],
) -> HardPrivateItem:
    profile = HardTaskProfile.TEMPORAL_STATE_RESOLUTION
    digest = _digest(seed, split, profile, index)
    position = tuple(EvidencePosition)[index % len(EvidencePosition)]
    chunk_count = requested_tokens // _TARGET_TOKENS_PER_CHUNK
    evidence_indices = _evidence_indices(
        chunk_count=chunk_count, evidence_count=5, position=position
    )
    subject = _opaque("nd", digest, "subject")
    authority = _opaque("au", digest, "authority")
    other_authority = _opaque("au", digest, "other-authority")
    answer = _opaque("vl", digest, "answer")
    alternatives = [_opaque("vl", digest, f"alternative-{number}") for number in range(3)]
    cutoff = 20 + digest[0] % 20
    sentences = _distractors(
        split=split,
        family=family,
        digest=digest,
        chunk_count=chunk_count,
        cycle=cutoff,
    )
    sentences[evidence_indices[0]] = (
        f"The {family.archive} rule selects the highest revision not later than epoch {cutoff} "
        f"that bears {family.credential} {authority}; later or differently signed entries do "
        "not apply."
    )
    sentences[evidence_indices[1]] = (
        f"Revision {cutoff - 9} for {subject} records {alternatives[0]} as {family.property_name} "
        f"under {family.credential} {authority}."
    )
    sentences[evidence_indices[2]] = (
        f"Revision {cutoff - 2} for {subject} records {answer} as {family.property_name} under "
        f"{family.credential} {authority}."
    )
    sentences[evidence_indices[3]] = (
        f"Revision {cutoff - 1} for {subject} records {alternatives[1]} as {family.property_name} "
        f"under {family.credential} {other_authority}."
    )
    sentences[evidence_indices[4]] = (
        f"Revision {cutoff + 4} for {subject} records {alternatives[2]} as {family.property_name} "
        f"under {family.credential} {authority}."
    )
    return _make_private_item(
        split=split,
        profile=profile,
        family=family,
        position=position,
        requested_tokens=requested_tokens,
        digest=digest,
        query=(
            f"Under the {family.archive} revision rule, what {family.property_name} applies to "
            f"{subject} at epoch {cutoff}?"
        ),
        answer=answer,
        sentences=sentences,
        evidence_indices=evidence_indices,
        token_counter=token_counter,
    )


def _insufficient_item(
    *,
    seed: str,
    split: Split,
    index: int,
    family: _Family,
    requested_tokens: int,
    token_counter: Callable[[str], int],
) -> HardPrivateItem:
    profile = HardTaskProfile.INSUFFICIENT_EVIDENCE
    digest = _digest(seed, split, profile, index)
    position = tuple(EvidencePosition)[index % len(EvidencePosition)]
    chunk_count = requested_tokens // _TARGET_TOKENS_PER_CHUNK
    evidence_indices = _evidence_indices(
        chunk_count=chunk_count, evidence_count=3, position=position
    )
    subject = _opaque("nd", digest, "subject")
    authority = _opaque("au", digest, "authority")
    candidate = _opaque("vl", digest, "candidate")
    cycle = 500 + digest[0]
    sentences = _distractors(
        split=split,
        family=family,
        digest=digest,
        chunk_count=chunk_count,
        cycle=cycle,
    )
    sentences[evidence_indices[0]] = (
        f"The {family.archive} index for {subject} in cycle {cycle} contains exactly two notices "
        f"bearing {family.credential} {authority}; three matching notices are required to "
        f"establish a {family.property_name}."
    )
    for notice_number, chunk_index in enumerate(evidence_indices[1:], start=1):
        sentences[chunk_index] = (
            f"Qualified {family.record} {notice_number} for {subject} in cycle {cycle} proposes "
            f"{candidate} as {family.property_name} under {family.credential} {authority}."
        )
    return _make_private_item(
        split=split,
        profile=profile,
        family=family,
        position=position,
        requested_tokens=requested_tokens,
        digest=digest,
        query=(
            f"What {family.property_name}, if any, is established for {subject} in the "
            f"{family.archive} during cycle {cycle}? Do not guess when the rule is unmet."
        ),
        answer=ABSTENTION_SENTINEL,
        sentences=sentences,
        evidence_indices=evidence_indices,
        token_counter=token_counter,
        requires_abstention=True,
    )


_BUILDERS = {
    HardTaskProfile.COMPOSITIONAL_MULTI_HOP: _compositional_item,
    HardTaskProfile.DENSE_GLOBAL_COMPARISON: _dense_item,
    HardTaskProfile.TEMPORAL_STATE_RESOLUTION: _temporal_item,
    HardTaskProfile.INSUFFICIENT_EVIDENCE: _insufficient_item,
}


def generate_hard_long_context_dataset(
    *,
    seed: str,
    items_per_profile: int,
    requested_tokens: int = NOMINAL_HARD_CONTEXT_TOKENS,
    token_counter: Callable[[str], int],
    tokenizer_id: str,
) -> HardLongContextDataset:
    """Build the public visible qualification split at a target-token length.

    This convenience API never derives gate or sealed data from the visible seed.
    """

    return generate_hard_long_context_split(
        split=Split.VISIBLE,
        evaluator_seed=seed,
        items_per_profile=items_per_profile,
        requested_tokens=requested_tokens,
        token_counter=token_counter,
        tokenizer_id=tokenizer_id,
    )


def generate_hard_long_context_split(
    *,
    split: Split,
    evaluator_seed: str,
    items_per_profile: int,
    requested_tokens: int = NOMINAL_HARD_CONTEXT_TOKENS,
    token_counter: Callable[[str], int],
    tokenizer_id: str,
) -> HardLongContextDataset:
    """Build exactly one split; hidden seeds must remain evaluator-only.

    The seed, topology labels, positions, answers, and gold provenance are evaluator
    state. Artifact text contains no literal ``ANSWER`` or private-control markers.
    """

    if not isinstance(split, Split):
        raise TypeError("split must use the Split enum")
    if not isinstance(evaluator_seed, str):
        raise TypeError("hard dataset seed must be a string")
    if not evaluator_seed:
        raise ValueError("hard dataset seed must be non-empty")
    if split is not Split.VISIBLE and len(evaluator_seed.encode()) < 32:
        raise ValueError("hidden split requires a high-entropy evaluator secret seed")
    if isinstance(items_per_profile, bool) or not isinstance(items_per_profile, int):
        raise TypeError("items_per_profile must be an integer")
    if items_per_profile < 1:
        raise ValueError("items_per_profile must be positive")
    if isinstance(requested_tokens, bool) or not isinstance(requested_tokens, int):
        raise TypeError("requested_tokens must be an integer")
    if requested_tokens not in SUPPORTED_HARD_CONTEXT_TOKENS:
        supported = ", ".join(str(value) for value in sorted(SUPPORTED_HARD_CONTEXT_TOKENS))
        raise ValueError(f"requested_tokens must be one of: {supported}")
    if not callable(token_counter):
        raise TypeError("token_counter must be callable")
    if not isinstance(tokenizer_id, str) or not tokenizer_id:
        raise ValueError("tokenizer_id must be non-empty")

    items: list[HardPrivateItem] = []
    for profile in HardTaskProfile:
        family = _FAMILIES[(split, profile)]
        builder = _BUILDERS[profile]
        for index in range(items_per_profile):
            items.append(
                builder(
                    seed=evaluator_seed,
                    split=split,
                    index=index,
                    family=family,
                    requested_tokens=requested_tokens,
                    token_counter=token_counter,
                )
            )

    frozen_items = tuple(items)
    fingerprint = _hard_dataset_fingerprint(
        frozen_items,
        requested_tokens=requested_tokens,
        tokenizer_id=tokenizer_id,
    )
    return HardLongContextDataset(
        split=split,
        _evaluator_items=frozen_items,
        requested_target_tokens=requested_tokens,
        target_token_tolerance=math.ceil(requested_tokens * HARD_TARGET_TOKEN_TOLERANCE_FRACTION),
        fingerprint=fingerprint,
        tokenizer_id=tokenizer_id,
    )
