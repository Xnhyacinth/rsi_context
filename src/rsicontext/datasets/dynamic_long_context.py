"""Deterministic 32K tasks that exercise distinct context-policy mechanisms."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from rsicontext.eval import EvaluationItem
from rsicontext.experiment import Split
from rsicontext.policy import Artifact, DocumentChunk

DYNAMIC_CONTEXT_TOKENS = 32_768
_CHUNK_TOKENS = 512
_CHUNK_COUNT = DYNAMIC_CONTEXT_TOKENS // _CHUNK_TOKENS

_COLORS = ("amber", "violet", "silver", "cerulean", "ochre", "magenta", "teal")
_CODES = ("Kappa-17", "Lumen-42", "Orion-63", "Pavo-28", "Sable-51", "Tern-84")
_NAME_PARTS = ("Arden", "Briar", "Celyn", "Doran", "Eiren", "Fenna", "Galen", "Hollis")
_FILLER_WORDS = (
    "garden",
    "window",
    "river",
    "morning",
    "paper",
    "quiet",
    "stone",
    "wooden",
    "field",
    "candle",
    "forest",
    "basket",
    "summer",
    "cloud",
    "bridge",
    "kitchen",
    "meadow",
    "yellow",
    "circle",
    "pencil",
    "market",
    "winter",
    "island",
    "cotton",
    "harbor",
    "little",
    "orange",
    "valley",
    "button",
    "travel",
    "flower",
    "coffee",
    "village",
    "pocket",
    "marble",
    "evening",
    "shadow",
    "blanket",
    "planet",
    "bottle",
    "gentle",
    "corner",
    "mirror",
    "pillow",
    "ocean",
    "school",
    "rabbit",
    "thunder",
    "apple",
    "mountain",
    "ticket",
    "purple",
    "sudden",
    "drawer",
    "camera",
    "feather",
    "engine",
    "carpet",
    "music",
    "lemon",
    "castle",
    "warmth",
    "picture",
    "breeze",
)


class DynamicTaskProfile(StrEnum):
    """Mechanism labels retained by the evaluator, not embedded in policy inputs."""

    SPARSE_MULTI_HOP = "sparse_multihop"
    DENSE_COMPETING_VALUES = "dense_competing_values"


@dataclass(frozen=True, slots=True)
class _Family:
    name: str
    collection: str
    pointer: str
    value: str
    attribute: str
    credential: str


_FAMILIES = {
    (Split.VISIBLE, DynamicTaskProfile.SPARSE_MULTI_HOP): _Family(
        "atlas-relay-v1", "atlas", "relay", "token", "transit", "card"
    ),
    (Split.GATE, DynamicTaskProfile.SPARSE_MULTI_HOP): _Family(
        "almanac-casket-v1", "almanac", "casket", "symbol", "passage", "dispatch"
    ),
    (Split.SEALED, DynamicTaskProfile.SPARSE_MULTI_HOP): _Family(
        "chronicle-capsule-v1", "chronicle", "capsule", "glyph", "access", "route"
    ),
    (Split.VISIBLE, DynamicTaskProfile.DENSE_COMPETING_VALUES): _Family(
        "meridian-quorum-v1", "meridian", "report", "hue", "signal", "signature"
    ),
    (Split.GATE, DynamicTaskProfile.DENSE_COMPETING_VALUES): _Family(
        "observatory-census-v1", "observatory", "entry", "shade", "beacon", "warrant"
    ),
    (Split.SEALED, DynamicTaskProfile.DENSE_COMPETING_VALUES): _Family(
        "compendium-conclave-v1", "compendium", "notice", "tint", "pulse", "signet"
    ),
}


@dataclass(frozen=True, slots=True)
class DynamicPrivateItem:
    """Evaluator-side item metadata; only visible instances may be exported."""

    split: Split
    task_profile: DynamicTaskProfile
    template_family: str
    evaluation_item: EvaluationItem


@dataclass(frozen=True, slots=True)
class DynamicLongContextDataset:
    """A deterministic panel with an explicit researcher/evaluator split boundary."""

    _evaluator_items: tuple[DynamicPrivateItem, ...]
    fingerprint: str

    def visible_items(self) -> tuple[DynamicPrivateItem, ...]:
        return self.evaluator_items(Split.VISIBLE)

    def evaluator_items(self, split: Split) -> tuple[DynamicPrivateItem, ...]:
        return tuple(item for item in self._evaluator_items if item.split is split)


def _digest(seed: str, split: Split, profile: DynamicTaskProfile, index: int) -> bytes:
    payload = f"{seed}\x00{split.value}\x00{profile.value}\x00{index}"
    return hashlib.sha256(payload.encode()).digest()


def _name(digest: bytes, offset: int) -> str:
    first = _NAME_PARTS[digest[offset % len(digest)] % len(_NAME_PARTS)]
    second = _NAME_PARTS[digest[(offset + 1) % len(digest)] % len(_NAME_PARTS)]
    suffix = digest[(offset + 2) % len(digest)]
    return f"{first}{second}-{suffix:02x}"


def _padded_text(sentence: str, digest: bytes, chunk_index: int) -> str:
    words = sentence.split()
    if len(words) > _CHUNK_TOKENS:
        raise AssertionError("dynamic task sentence exceeds its fixed chunk budget")
    offset = (digest[chunk_index % len(digest)] + 17 * chunk_index) % len(_FILLER_WORDS)
    words.extend(
        _FILLER_WORDS[(offset + 17 * word_index) % len(_FILLER_WORDS)]
        for word_index in range(_CHUNK_TOKENS - len(words))
    )
    return " ".join(words)


def _chunks(
    *, document_id: str, sentences: tuple[str, ...], gold_indices: frozenset[int], digest: bytes
) -> tuple[tuple[DocumentChunk, ...], frozenset[str]]:
    if len(sentences) != _CHUNK_COUNT:
        raise AssertionError("dynamic task must have exactly 64 chunks")
    chunks: list[DocumentChunk] = []
    gold_ids: set[str] = set()
    cursor = 0
    for index, sentence in enumerate(sentences):
        text = _padded_text(sentence, digest, index)
        chunk_id = f"ck-{hashlib.sha256(f'{document_id}:{index}'.encode()).hexdigest()[:16]}"
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                start=cursor,
                end=cursor + len(text),
                text=text,
                token_count=_CHUNK_TOKENS,
            )
        )
        if index in gold_indices:
            gold_ids.add(chunk_id)
        cursor += len(text) + 1
    return tuple(chunks), frozenset(gold_ids)


def _sparse_item(*, seed: str, split: Split, index: int, family: _Family) -> DynamicPrivateItem:
    profile = DynamicTaskProfile.SPARSE_MULTI_HOP
    digest = _digest(seed, split, profile, index)
    document_id = f"dx-{digest.hex()[:20]}"
    entity = _name(digest, 0)
    target_record = _name(digest, 4)
    answer = _CODES[digest[8] % len(_CODES)]
    layouts = ((0, 5), (27, 36), (57, 63))
    relation_index, value_index = layouts[index % len(layouts)]

    sentences: list[str] = []
    alternatives = tuple(code for code in _CODES if code != answer)
    for chunk_index in range(_CHUNK_COUNT):
        distractor_entity = _name(digest, chunk_index + 9)
        distractor_record = _name(digest, chunk_index + 15)
        if chunk_index % 2 == 0:
            sentence = (
                f"The {family.collection} {family.credential} for {distractor_entity} forwards "
                f"its current reference to {family.pointer} {distractor_record}."
            )
        else:
            distractor_code = alternatives[(chunk_index + digest[12]) % len(alternatives)]
            sentence = (
                f"{family.pointer.title()} {distractor_record} bears {distractor_code} under "
                "the current issue."
            )
        sentences.append(sentence)
    sentences[relation_index] = (
        f"The {family.collection} {family.credential} for {entity} forwards its current "
        f"reference to {family.pointer} {target_record}."
    )
    sentences[value_index] = (
        f"{family.pointer.title()} {target_record} bears {answer} under the current issue."
    )
    chunks, gold_ids = _chunks(
        document_id=document_id,
        sentences=tuple(sentences),
        gold_indices=frozenset((relation_index, value_index)),
        digest=digest,
    )
    query = (
        f"Within the {family.collection}, what {family.attribute} {family.value} is currently "
        f"assigned to {entity}?"
    )
    return DynamicPrivateItem(
        split=split,
        task_profile=profile,
        template_family=family.name,
        evaluation_item=EvaluationItem(
            item_id=document_id,
            query=query,
            answer=answer,
            artifact=Artifact(document_id=document_id, chunks=chunks),
            gold_chunk_ids=gold_ids,
        ),
    )


def _dense_item(*, seed: str, split: Split, index: int, family: _Family) -> DynamicPrivateItem:
    profile = DynamicTaskProfile.DENSE_COMPETING_VALUES
    digest = _digest(seed, split, profile, index)
    document_id = f"dx-{digest.hex()[:20]}"
    entity = _name(digest, 0)
    authority = _name(digest, 4)
    cycle = 20 + digest[8] % 70
    answer = _COLORS[digest[9] % len(_COLORS)]
    alternatives = tuple(color for color in _COLORS if color != answer)
    competitor = alternatives[digest[10] % len(alternatives)]
    layouts = (
        (0, 1, 2, 3, 4, 5, 6, 7),
        (0, 9, 18, 27, 36, 45, 54, 63),
        (56, 57, 58, 59, 60, 61, 62, 63),
    )
    gold_indices = layouts[index % len(layouts)]

    sentences: list[str] = []
    for chunk_index in range(_CHUNK_COUNT):
        other_authority = _name(digest, chunk_index + 12)
        distractor_value = alternatives[(chunk_index + digest[13]) % len(alternatives)]
        sentences.append(
            f"A {family.collection} {family.pointer} for {entity} in cycle {cycle} carries "
            f"{distractor_value} as its {family.attribute} {family.value} and has "
            f"{family.credential} {other_authority}."
        )

    sentences[gold_indices[0]] = (
        f"The {family.collection} consensus counts only {family.pointer} records carrying "
        f"{family.credential} {authority}; the most frequent {family.value} is adopted."
    )
    eligible_values = (answer, competitor, answer, competitor, answer, competitor, answer)
    for observation_index, (chunk_index, observed_value) in enumerate(
        zip(gold_indices[1:], eligible_values, strict=True), start=1
    ):
        sentences[chunk_index] = (
            f"{family.collection.title()} {family.pointer} {observation_index} for {entity} in "
            f"cycle {cycle} carries {observed_value} as its {family.attribute} {family.value} "
            f"and has {family.credential} {authority}."
        )

    chunks, gold_ids = _chunks(
        document_id=document_id,
        sentences=tuple(sentences),
        gold_indices=frozenset(gold_indices),
        digest=digest,
    )
    query = (
        f"Under the {family.collection} consensus, which {family.attribute} {family.value} is "
        f"assigned to {entity} for cycle {cycle}?"
    )
    return DynamicPrivateItem(
        split=split,
        task_profile=profile,
        template_family=family.name,
        evaluation_item=EvaluationItem(
            item_id=document_id,
            query=query,
            answer=answer,
            artifact=Artifact(document_id=document_id, chunks=chunks),
            gold_chunk_ids=gold_ids,
        ),
    )


def generate_dynamic_long_context_dataset(
    *, seed: str, items_per_profile: int
) -> DynamicLongContextDataset:
    """Build an exact-32K panel while keeping the seed and private splits evaluator-side."""

    if not isinstance(seed, str):
        raise TypeError("dynamic dataset seed must be a string")
    if not seed:
        raise ValueError("dynamic dataset seed must be non-empty")
    if isinstance(items_per_profile, bool) or not isinstance(items_per_profile, int):
        raise TypeError("items_per_profile must be an integer")
    if items_per_profile < 1:
        raise ValueError("items_per_profile must be positive")

    items: list[DynamicPrivateItem] = []
    for split in Split:
        for profile in DynamicTaskProfile:
            family = _FAMILIES[(split, profile)]
            for index in range(items_per_profile):
                if profile is DynamicTaskProfile.SPARSE_MULTI_HOP:
                    item = _sparse_item(seed=seed, split=split, index=index, family=family)
                else:
                    item = _dense_item(seed=seed, split=split, index=index, family=family)
                items.append(item)

    canonical = [
        {
            "answer": item.evaluation_item.answer,
            "chunks": [
                hashlib.sha256(chunk.text.encode()).hexdigest()
                for chunk in item.evaluation_item.artifact.chunks
            ],
            "family": item.template_family,
            "gold": sorted(item.evaluation_item.gold_chunk_ids),
            "item_id": item.evaluation_item.item_id,
            "profile": item.task_profile.value,
            "split": item.split.value,
        }
        for item in items
    ]
    fingerprint = hashlib.sha256(
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()
    return DynamicLongContextDataset(tuple(items), fingerprint)
