"""Independent task worlds for the research-v1 family (review step 4).

The 2026-09-20 review and the root-cause record
(``docs/root-cause-24-of-24-20260920.md``) name the n=16 panel's structural
limitation: 24 item-level instances over ONE template and ONE corpus slice
are not independent task worlds. This module is the step-4 deliverable: the
WORLD — one corpus entity and its whole retrieval base — becomes the unit of
independence, and dev/holdout splits happen by world, never by instance.

Design (manifest mapping, not per-instance world ids): a world is a
``TaskWorld`` — a ``WorldSpec`` (world id, family template, entity seed,
variant notes) mapped to its instances. ``lifecycle/`` is frozen for this
workstream (a parallel workstream owns its alias handling), and
``LifecycleInstance`` has no metadata field for a world id; smuggling one
through ``sandbox_spec`` would pollute an evaluator-owned field. The
world-to-instances mapping therefore lives in this container type, and the
``WorldManifest`` (``manifest.py``) audits it.

One world yields 2-4 instances ("projects") that legitimately share the
world's document base — same entity, same gold evidence, same final answer —
while differing in project aspect: each project surveys a disjoint slice of
the world's non-gold documents, carries its own stage-4 supersession target,
and frames its stage-1 survey prompt with its aspect label. Stages 2-5 keep
the family's canonical prompt shapes byte-for-byte (the root-cause report
shows the reader is format-sensitive; variant framing is confined to the
stage-1 prompt). Within-world answer recurrence is legitimate case-(a)
memory content by construction; cross-world answer caching is impossible
under a world-level split because no corpus row feeds two worlds.

Gold sanity: ``gold_sane`` is this package's own alias check over
``possible_answers`` (the alias-aware scoring workstream owns
``lifecycle/material.py``): a row is usable only when some gold passage
contains BOTH an answer alias and a subject alias. The subject half is the
4402885 defect class — gold retrieval about a different entity that
incidentally contains the answer string ("north-central Poland").
"""

from __future__ import annotations

import json
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_FAMILY_TEMPLATE_ID = "research-v1"
_FAMILY = "research-v1"
_MIN_INSTANCES_PER_WORLD = 2
_MAX_INSTANCES_PER_WORLD = 4
_MIN_NOISE_DOCS = 2  # one disjoint non-gold survey doc per minimum variant
_MAX_DOCS_PER_VARIANT = 8  # mirrors the family example constructor's survey bulk
_MIN_MENTION_LEN = 3  # substring noise floor: 'PL'/'P' style aliases match anywhere
_DOC_ID_PREFIX = "doc"
_DOC_ID_SLUG_MAX = 60
_FINAL_RECORD_ID = "answer_project"
_SOURCE_URL_TEMPLATE = "kilt:popqa:{row_id}"
_RETRIEVED_DATE = "2026-09-20"
# (aspect label, stage-1 framing sentence) — variant k of a world uses entry k.
_ASPECTS: tuple[tuple[str, str], ...] = (
    ("primary-scope", "Establish the primary evidence line for the answer."),
    ("secondary-scope", "Corroborate the answer through the secondary document slice."),
    ("audit-scope", "Audit the constraint scope across the audit slice before committing."),
    ("triage-scope", "Triage supersession risk across the triage slice before committing."),
)


def _require_str(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value:
        raise ValueError(f"{field} must not be empty")


def _require_int(value: object, field: str, *, minimum: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    if value < minimum:
        raise ValueError(f"{field} must be at least {minimum}")


@dataclass(frozen=True, slots=True)
class WorldSpec:
    """Provenance record for one task world.

    ``world_id`` is the unique parent-world identifier shared by all of the
    world's instances (recorded here — never on ``LifecycleInstance``);
    ``template_id`` names the family lifecycle template the world
    instantiates; ``entity_seed`` carries the corpus row id(s) the world's
    material was drawn from; ``variant_notes`` holds one note per variant,
    describing that project's scope within the world.
    """

    world_id: str
    template_id: str
    entity_seed: tuple[str, ...]
    variant_notes: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_str(self.world_id, "world_id")
        _require_str(self.template_id, "template_id")
        object.__setattr__(self, "entity_seed", tuple(self.entity_seed))
        object.__setattr__(self, "variant_notes", tuple(self.variant_notes))
        if not self.entity_seed:
            raise ValueError("entity_seed must name at least one corpus row id")
        for row_id in self.entity_seed:
            _require_str(row_id, "entity_seed entry")
        if not self.variant_notes:
            raise ValueError("variant_notes must carry at least one note")
        for note in self.variant_notes:
            _require_str(note, "variant_notes entry")


@dataclass(frozen=True, slots=True)
class TaskWorld:
    """One independent task world: a spec mapped to its project instances.

    The instances legitimately share the world's document base (same entity,
    gold evidence, and final answer) and differ in project aspect — each
    surveys a disjoint non-gold slice and carries its own supersession
    target. The world, not the instance, is the unit of dev/holdout
    splitting and of statistical independence.
    """

    spec: WorldSpec
    instances: tuple[LifecycleInstance, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.spec, WorldSpec):
            raise TypeError("spec must be a WorldSpec")
        object.__setattr__(self, "instances", tuple(self.instances))
        if any(not isinstance(inst, LifecycleInstance) for inst in self.instances):
            raise TypeError("world instances must be LifecycleInstance values")
        if not _MIN_INSTANCES_PER_WORLD <= len(self.instances) <= _MAX_INSTANCES_PER_WORLD:
            raise ValueError(
                f"a world carries {_MIN_INSTANCES_PER_WORLD}-{_MAX_INSTANCES_PER_WORLD} "
                f"instances; got {len(self.instances)}"
            )
        instance_ids = [inst.instance_id for inst in self.instances]
        if len(instance_ids) != len(set(instance_ids)):
            raise ValueError("instance ids must be unique within a world")
        if len(self.spec.variant_notes) != len(self.instances):
            raise ValueError("variant_notes must carry one note per instance")

    @property
    def world_id(self) -> str:
        return self.spec.world_id


def _ctx_has_answer(ctx: Mapping[str, object]) -> bool:
    flag = ctx.get("has_answer")
    return flag is True or flag == 1


def _ctx_body(ctx: Mapping[str, object]) -> str:
    text = ctx.get("text")
    if not isinstance(text, str) or not text.strip():
        return ""
    return text


def _ctx_heading(ctx: Mapping[str, object]) -> str:
    title = ctx.get("title")
    if not isinstance(title, str) or not title.strip():
        return ""
    return title


def _decode_possible_answers(raw: object) -> tuple[str, ...]:
    """Decode PopQA ``possible_answers`` (JSON list string or list).

    Reimplemented here rather than imported from ``lifecycle/material.py``:
    that module is under concurrent revision by the alias workstream, and
    this package must not depend on its private helpers.
    """

    if isinstance(raw, str):
        decoded: object = json.loads(raw)
        if not isinstance(decoded, list) or not decoded:
            raise ValueError("possible_answers must decode to a non-empty list")
        answers = [entry for entry in decoded if isinstance(entry, str) and entry.strip()]
        if not answers:
            raise ValueError("possible_answers must contain at least one string")
        return tuple(answers)
    if isinstance(raw, list):
        if not raw or not all(isinstance(entry, str) and entry.strip() for entry in raw):
            raise ValueError("possible_answers must be a non-empty list of strings")
        return tuple(raw)
    raise ValueError("possible_answers must be a JSON-encoded list string or a list")


def _decode_subject_aliases(row: Mapping[str, object]) -> tuple[str, ...]:
    """Entity-name aliases a gold passage may be grounded by (len >= 3)."""

    aliases: list[str] = []
    subj = row.get("subj")
    if isinstance(subj, str) and subj.strip():
        aliases.append(subj)
    wiki_title = row.get("s_wiki_title")
    if isinstance(wiki_title, str) and wiki_title.strip():
        aliases.append(wiki_title)
    raw_s_aliases = row.get("s_aliases")
    try:
        for entry in _decode_possible_answers(raw_s_aliases):
            aliases.append(entry)
    except (ValueError, TypeError):
        pass  # tolerate a malformed alias side-field; subj/wiki title still ground
    return tuple(
        dict.fromkeys(alias.strip() for alias in aliases if len(alias.strip()) >= _MIN_MENTION_LEN)
    )


def _mentions(aliases: tuple[str, ...], text: str) -> bool:
    lowered = text.lower()
    return any(alias.lower() in lowered for alias in aliases)


def gold_sane(row: Mapping[str, object]) -> bool:
    """Build-time gold-passage sanity gate (root-cause report §Consequences).

    A row is gold-sane when some gold ctx carries non-empty text in which
    BOTH (a) at least one answer alias and (b) at least one subject alias
    appear (aliases shorter than 3 characters are ignored — substring noise).
    Condition (b) is the 4402885 defect class: gold retrieval about a
    different entity that incidentally contains the answer string. Rows with
    no derivable subject aliases cannot be verified as entity-grounded and
    are rejected; this is a selection gate, so it returns False rather than
    raising on unusable rows.
    """

    ctxs = row.get("ctxs")
    if not isinstance(ctxs, list):
        return False
    try:
        answer_aliases = tuple(
            alias
            for alias in _decode_possible_answers(row.get("possible_answers"))
            if len(alias.strip()) >= _MIN_MENTION_LEN
        )
    except ValueError:
        return False
    if not answer_aliases:
        return False
    subject_aliases = _decode_subject_aliases(row)
    if not subject_aliases:
        return False
    for ctx in ctxs:
        if not isinstance(ctx, Mapping):
            return False
        if not _ctx_has_answer(ctx):
            continue
        text = _ctx_body(ctx)
        if not text:
            continue
        if _mentions(answer_aliases, text) and _mentions(subject_aliases, text):
            return True
    return False


def _row_id(row: Mapping[str, object]) -> str:
    raw = row.get("id")
    if isinstance(raw, bool) or raw is None:
        raise ValueError("world construction requires a corpus row id")
    if isinstance(raw, str):
        if not raw.strip():
            raise ValueError("world construction requires a non-empty row id")
        return raw
    if isinstance(raw, int):
        return str(raw)
    raise ValueError("row id must be an integer or a non-empty string")


def _optional_row_id(row: Mapping[str, object]) -> str | None:
    try:
        return _row_id(row)
    except ValueError:
        return None


def _optional_entity_key(row: Mapping[str, object]) -> str | None:
    raw = row.get("subj_id")
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, str) and raw.strip():
        return raw
    if isinstance(raw, int):
        return str(raw)
    return None


def _ctx_doc_id(ctx: Mapping[str, object], position: int) -> str:
    """Deterministic doc id from the ctx's corpus position (shared by variants)."""

    raw_id = ctx.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        slug = re.sub(r"[^A-Za-z0-9_-]", "-", raw_id.strip())[:_DOC_ID_SLUG_MAX]
        return f"{_DOC_ID_PREFIX}-{slug}-{position}"
    if isinstance(raw_id, int) and not isinstance(raw_id, bool):
        return f"{_DOC_ID_PREFIX}-{raw_id}-{position}"
    return f"{_DOC_ID_PREFIX}-{position}"


def _build_document(ctx: Mapping[str, object], position: int, row_id: str) -> DocumentRef:
    doc_id = _ctx_doc_id(ctx, position)
    title = _ctx_heading(ctx)
    if not title:
        raise ValueError(f"ctx at position {position} has no usable title")
    body = _ctx_body(ctx)
    if not body:
        raise ValueError(f"ctx at position {position} has no usable text")
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{body.strip()}",
        source_url=_SOURCE_URL_TEMPLATE.format(row_id=row_id),
        retrieved_date=_RETRIEVED_DATE,
    )


def build_world(row: Mapping[str, object], world_id: str) -> TaskWorld:
    """Build one task world — 2-4 project instances — from a PopQA KILT row.

    ``row`` is a PopQA-shaped record (``id``, ``question``,
    ``possible_answers``, ``ctxs`` of ``{id,title,text,score,has_answer}``;
    ``subj``/``subj_id``/``s_aliases``/``s_wiki_title`` when present are used
    only by ``gold_sane``). The world's non-gold documents are split into
    disjoint per-variant slices (round-robin over retrieval order, capped at
    ``_MAX_DOCS_PER_VARIANT`` each); every variant's instance surveys its
    slice plus ALL of the world's gold documents, so instances share the
    gold evidence (and the world's answer) while differing in project
    scope. Stage shapes mirror ``lifecycle/material.py``: stage 2 anchors
    the scope constraint on the first gold document, stage 4 marks the
    variant's own slice head as the supersession signal, stage 5 commits
    the finalize record with the gold support as provenance. Raises
    ``ValueError`` for rows without enough usable material.
    """

    _require_str(world_id, "world_id")
    question = row.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("world construction requires a non-empty question")
    row_id = _row_id(row)
    answer_norm = _decode_possible_answers(row.get("possible_answers"))[0]
    raw_ctxs = row.get("ctxs")
    if not isinstance(raw_ctxs, list) or not raw_ctxs:
        raise ValueError("ctxs must be a non-empty list")
    ctxs: list[Mapping[str, object]] = []
    for ctx in raw_ctxs:
        if not isinstance(ctx, Mapping):
            raise TypeError("each ctx must be a mapping")
        ctxs.append(ctx)
    gold_positions = [
        position
        for position, ctx in enumerate(ctxs)
        if _ctx_has_answer(ctx) and _ctx_body(ctx) and _ctx_heading(ctx)
    ]
    noise_positions = [
        position
        for position, ctx in enumerate(ctxs)
        if not _ctx_has_answer(ctx) and _ctx_body(ctx) and _ctx_heading(ctx)
    ]
    if not gold_positions:
        raise ValueError("world construction requires at least one usable gold ctx")
    if len(noise_positions) < _MIN_NOISE_DOCS:
        raise ValueError(
            f"world construction requires at least {_MIN_NOISE_DOCS} usable non-gold ctxs"
        )
    n_variants = min(
        _MAX_INSTANCES_PER_WORLD, max(_MIN_INSTANCES_PER_WORLD, len(noise_positions) // 2)
    )
    slice_positions_per_variant = [
        noise_positions[variant::n_variants][:_MAX_DOCS_PER_VARIANT]
        for variant in range(n_variants)
    ]
    used_positions = sorted(
        {position for positions in slice_positions_per_variant for position in positions}
        | set(gold_positions)
    )
    documents = {
        position: _build_document(ctxs[position], position, row_id) for position in used_positions
    }
    gold_docs = tuple(documents[position] for position in gold_positions)
    gold_doc_ids = tuple(document.doc_id for document in gold_docs)
    anchor_gold = gold_docs[0]
    instances: list[LifecycleInstance] = []
    variant_notes: list[str] = []
    for variant in range(n_variants):
        aspect_label, aspect_frame = _ASPECTS[variant]
        slice_positions = slice_positions_per_variant[variant]
        target = documents[slice_positions[0]]
        survey_docs = tuple(documents[position] for position in (*slice_positions, *gold_positions))
        instances.append(
            LifecycleInstance(
                instance_id=f"{_FAMILY}-{world_id}-{aspect_label}",
                family=_FAMILY,
                stages=(
                    StageSpec(
                        stage_id="s1-survey",
                        kind="survey",
                        prompt_text=(
                            f"[Project {aspect_label} | world {world_id}] {aspect_frame} "
                            f"Survey the project document base for the question: {question!r}. "
                            "Build your working notes; they are your only carry-forward."
                        ),
                        documents=survey_docs,
                        gold_evidence_ids=gold_doc_ids,
                    ),
                    StageSpec(
                        stage_id="s2-constraint",
                        kind="constraint_injection",
                        prompt_text=(
                            "A new constraint arrives: only evidence whose source passage "
                            f"matches {anchor_gold.title!r} in its support may be used for the "
                            "final answer. Re-check your notes against this scope rule."
                        ),
                        documents=(anchor_gold,),
                        gold_evidence_ids=(anchor_gold.doc_id,),
                    ),
                    StageSpec(
                        stage_id="s3-delegation",
                        kind="delegation",
                        prompt_text=(
                            "Delegate verification of the candidate answer to a bounded "
                            "sub-agent. Required sub-return template fields: finding, "
                            "source (doc id), applicability condition."
                        ),
                        documents=(anchor_gold,),
                        gold_evidence_ids=(anchor_gold.doc_id,),
                    ),
                    StageSpec(
                        stage_id="s4-rule-change",
                        kind="rule_change",
                        prompt_text=(
                            f"Rule change: document {target.doc_id} ({target.title!r}) "
                            "is now marked as a superseding signal. Any prior conclusion "
                            "relying on pre-rule-change state must be re-verified against "
                            "the current gold support before the final commit."
                        ),
                        documents=(
                            DocumentRef(
                                doc_id=target.doc_id,
                                title=target.title,
                                text=target.text,
                                source_url=target.source_url,
                                retrieved_date=target.retrieved_date,
                                superseded_by=anchor_gold.doc_id,
                            ),
                            anchor_gold,
                        ),
                        gold_evidence_ids=(anchor_gold.doc_id,),
                    ),
                    StageSpec(
                        stage_id="s5-act-verify",
                        kind="act_verify",
                        prompt_text=(
                            "Commit the final answer artifact through a sandbox write: "
                            f"create record {_FINAL_RECORD_ID} with the normalized answer "
                            f"({answer_norm!r}) and the gold support doc ids, then finalize "
                            "it with provenance."
                        ),
                        documents=(anchor_gold,),
                        gold_evidence_ids=(anchor_gold.doc_id,),
                        expected_state_delta={
                            _FINAL_RECORD_ID: {
                                "answer": answer_norm,
                                "supports": list(gold_doc_ids),
                                "status": "final",
                            },
                        },
                    ),
                ),
                axes=DescriptionAxes(
                    information_scale_tokens=sum(
                        1 + len(document.text.split()) for document in survey_docs
                    ),
                    dependency_distance_stages=4,
                    persistence_span_resets=3,
                    action_dependency="strong",
                    environment_changes=1,
                ),
                answer_norm=answer_norm,
                sandbox_spec={
                    "records": [_FINAL_RECORD_ID],
                    "action_kinds": ["create_record", "update_record", "finalize"],
                },
            )
        )
        variant_notes.append(
            f"{aspect_label}: {len(slice_positions)}-doc scope slice; "
            f"supersession target {target.doc_id}"
        )
    return TaskWorld(
        spec=WorldSpec(
            world_id=world_id,
            template_id=_FAMILY_TEMPLATE_ID,
            entity_seed=(row_id,),
            variant_notes=tuple(variant_notes),
        ),
        instances=tuple(instances),
    )


def load_worlds(
    popqa_path: str | Path, n_worlds: int, *, dev_worlds: int, seed: int = 0
) -> tuple[list[TaskWorld], list[TaskWorld]]:
    """Load ``n_worlds`` independent worlds and split dev/holdout BY WORLD.

    Streams the PopQA KILT JSONL, keeping the first occurrence of each
    DISTINCT row id (the corpus packs each entity as several adjacent
    duplicate-id lines) and at most one world per ENTITY (``subj_id``) — two
    rows about the same entity would not be independent worlds. Rows must
    pass ``gold_sane`` and carry enough usable material for world
    construction; everything else is skipped. Selection walks the corpus in
    order (deterministic given the file); the world ORDER is then shuffled
    with ``seed`` — the review's layered-randomization rule: randomization
    happens per world, while each world's instances keep their causal stage
    order — and the first ``dev_worlds`` shuffled worlds become dev, the
    rest holdout. Because the split is by world, no world (and no corpus
    row) can appear on both sides. Raises ``ValueError`` when the corpus
    yields fewer gold-sane worlds than requested or the split parameters
    are invalid.
    """

    _require_int(n_worlds, "n_worlds", minimum=2)
    _require_int(dev_worlds, "dev_worlds", minimum=1)
    if dev_worlds >= n_worlds:
        raise ValueError("dev_worlds must leave at least one holdout world")
    _require_int(seed, "seed", minimum=0)
    worlds: list[TaskWorld] = []
    seen_row_ids: set[str] = set()
    seen_entities: set[str] = set()
    with Path(popqa_path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row: object = json.loads(line)
            if not isinstance(row, Mapping):
                raise ValueError("corpus lines must be JSON objects")
            row_id = _optional_row_id(row)
            if row_id is None or row_id in seen_row_ids:
                continue
            seen_row_ids.add(row_id)  # examine each distinct row id once
            entity_key = _optional_entity_key(row)
            if entity_key is not None and entity_key in seen_entities:
                continue
            if not gold_sane(row):
                continue
            try:
                world = build_world(row, f"world-{row_id}")
            except ValueError:
                continue
            if entity_key is not None:
                seen_entities.add(entity_key)
            worlds.append(world)
            if len(worlds) == n_worlds:
                break
    if len(worlds) < n_worlds:
        raise ValueError(f"corpus yielded {len(worlds)} gold-sane worlds; {n_worlds} requested")
    order = list(range(len(worlds)))
    random.Random(seed).shuffle(order)
    shuffled = [worlds[index] for index in order]
    return shuffled[:dev_worlds], shuffled[dev_worlds:]
