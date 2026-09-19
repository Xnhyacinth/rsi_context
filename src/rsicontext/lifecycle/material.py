"""Example research-v1 instance construction from a PopQA KILT row.

Spec: ``docs/task-family-research-v1.md`` §Instance material and construction.
This is ONE deterministic example constructor used by the Phase B contract
tests — the full family builder (position balancing, difficulty kills,
qualification panels) is a later deliverable and lives elsewhere.

Construction follows the spec's rules: material is drawn from the wired real
corpus (HELMET PopQA k1000 KILT passages), the coupling events are
benchmark-authored and deterministic, and constraint/rule-change events are
causally anchored to specific gold evidence spans — never free-form
invention. Every document text embeds a ``[[doc:ID]]`` provenance marker so
provenance retention is measurable from the acting context alone.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_SURVEY_NON_GOLD_DOCS = 8
_DOC_ID_PREFIX = "doc"
_DOC_ID_SLUG_MAX = 60
_FINAL_RECORD_ID = "answer_project"
_SOURCE_URL_TEMPLATE = "kilt:popqa:{row_id}"
_RETRIEVED_DATE = "2026-09-19"


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _ctx_has_answer(ctx: Mapping[str, object]) -> bool:
    flag = ctx.get("has_answer")
    return flag is True or flag == 1


def _ctx_doc_id(ctx: Mapping[str, object], position: int) -> str:
    """Deterministic unique doc id: source id slug plus corpus position."""

    raw_id = ctx.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        slug = re.sub(r"[^A-Za-z0-9_-]", "-", raw_id.strip())[:_DOC_ID_SLUG_MAX]
        return f"{_DOC_ID_PREFIX}-{slug}-{position}"
    if isinstance(raw_id, int) and not isinstance(raw_id, bool):
        return f"{_DOC_ID_PREFIX}-{raw_id}-{position}"
    return f"{_DOC_ID_PREFIX}-{position}"


def _build_document(ctx: Mapping[str, object], position: int, row_id: str) -> DocumentRef:
    doc_id = _ctx_doc_id(ctx, position)
    title = _require_str(ctx.get("title"), "ctx title")
    text = _require_str(ctx.get("text"), "ctx text")
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text.strip()}",
        source_url=_SOURCE_URL_TEMPLATE.format(row_id=row_id),
        retrieved_date=_RETRIEVED_DATE,
    )


def _finalize_record_fields(answer_norm: str, gold_doc_ids: tuple[str, ...]) -> dict[str, Any]:
    return {"answer": answer_norm, "supports": list(gold_doc_ids), "status": "final"}


def _decode_possible_answers(raw: object) -> tuple[str, ...]:
    """PopQA k1000 rows encode ``possible_answers`` as a JSON list string."""

    if isinstance(raw, str):
        decoded = json.loads(raw)
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


def build_example_instance(popqa_jsonl_row: Mapping[str, object]) -> LifecycleInstance:
    """Deterministically build the five-stage research-v1 example instance.

    ``popqa_jsonl_row`` is a PopQA KILT record with fields ``question``,
    ``possible_answers`` (JSON-encoded list string per the corpus rows), and
    ``ctxs`` (list of ``{id,title,text,score,has_answer}``). The five stages:

    1. survey — top-N non-gold ctxs plus every gold ctx (N=8);
    2. constraint injection — a scope rule referencing a gold doc's title
       (checkable against that span only);
    3. delegation — a sub-return template (finding / source / applicability);
    4. rule change — one non-gold doc marked as superseding signal plus a
       re-verification requirement;
    5. act_verify — ``expected_state_delta`` derived from
       ``possible_answers[0]``: a finalize write of the answer with the gold
       support as provenance.
    """

    question = _require_str(popqa_jsonl_row.get("question"), "question")
    row_id_raw = popqa_jsonl_row.get("id")
    row_id = str(row_id_raw) if row_id_raw is not None else "unknown"
    answer_norm = _decode_possible_answers(popqa_jsonl_row.get("possible_answers"))[0]
    raw_ctxs = popqa_jsonl_row.get("ctxs")
    if not isinstance(raw_ctxs, list) or not raw_ctxs:
        raise ValueError("ctxs must be a non-empty list")
    ctxs: list[Mapping[str, object]] = []
    for ctx in raw_ctxs:
        if not isinstance(ctx, Mapping):
            raise TypeError("each ctx must be a mapping")
        ctxs.append(ctx)
    gold_positions = [position for position, ctx in enumerate(ctxs) if _ctx_has_answer(ctx)]
    if not gold_positions:
        raise ValueError("the example constructor requires at least one gold ctx")
    non_gold_positions = [
        position for position, ctx in enumerate(ctxs) if not _ctx_has_answer(ctx)
    ][:_SURVEY_NON_GOLD_DOCS]
    if not non_gold_positions:
        raise ValueError("the example constructor requires at least one non-gold ctx")
    survey_positions = non_gold_positions + gold_positions
    survey_docs = tuple(
        _build_document(ctxs[position], position, row_id) for position in survey_positions
    )
    doc_by_position = dict(zip(survey_positions, survey_docs, strict=True))
    gold_doc_ids = tuple(doc_by_position[position].doc_id for position in gold_positions)
    anchor_gold = doc_by_position[gold_positions[0]]
    non_gold_anchor = doc_by_position[non_gold_positions[0]]
    information_scale_tokens = sum(1 + len(document.text.split()) for document in survey_docs)
    return LifecycleInstance(
        instance_id=f"research-v1-example-{row_id}",
        family="research-v1",
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
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
                    f"Rule change: document {non_gold_anchor.doc_id} "
                    f"({non_gold_anchor.title!r}) is now marked as a superseding "
                    "signal. Any prior conclusion relying on pre-rule-change state "
                    "must be re-verified against the current gold support before "
                    "the final commit."
                ),
                documents=(
                    DocumentRef(
                        doc_id=non_gold_anchor.doc_id,
                        title=non_gold_anchor.title,
                        text=non_gold_anchor.text,
                        source_url=non_gold_anchor.source_url,
                        retrieved_date=non_gold_anchor.retrieved_date,
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
                    f"Commit the final answer artifact through a sandbox write: "
                    f"create record {_FINAL_RECORD_ID} with the normalized answer "
                    f"({answer_norm!r}) and the gold support doc ids, then finalize "
                    "it with provenance."
                ),
                documents=(anchor_gold,),
                gold_evidence_ids=(anchor_gold.doc_id,),
                expected_state_delta={
                    _FINAL_RECORD_ID: _finalize_record_fields(answer_norm, gold_doc_ids),
                },
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=information_scale_tokens,
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
