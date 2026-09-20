"""Research-v2 instance construction: the leak-closed task family.

Spec: ``docs/dependency-probes-20260920.md`` §Consequences (mandatory
family revision) and §Root structural finding (the two verified stage-5
leak channels in research-v1 that this module closes):

1. The act_verify prompt TEXT named the answer — v2's stage-5 instruction
   says WHAT to commit (record shape, provenance requirement), never the
   answer value. The participant decides the value; the checker knows the
   expectation (``expected_state_delta`` is evaluator-only by
   ``StageView`` construction).
2. The gold-anchor (answer-bearing) document was attached to the final
   stage — v2's stage-5 attaches NO documents: the answer must be
   reconstructed from what the participant retained across stages 1-4.

Stage evidence allocation (dependency structure the probes demanded):

- s1 survey: the variant's noise slice PLUS the answer-bearing gold
  passages (long documents load-bearing for the answer path — the only
  stage where the answer text is legitimately visible).
- s2 constraint: a NON-answer-bearing scope rule (noise document) — the
  constraint references the gold document's TITLE only; applying it
  requires having noted which document carries it.
- s3 delegation: noise documents only — the sub-agent verifies format and
  source discipline; it cannot answer, and the principal must recognize
  that a return lacking an answer-bearing source cannot justify one.
- s4 rule change: the supersession signal (noise) plus a VERIFICATION
  CHECK block: a deterministic checksum-style clue derived from the
  answer aliases that DISCRIMINATES candidate answers without containing
  them (first letter + word count + initials of each alias). This is the
  review's option (a): a check that validates a candidate the
  participant supplies from memory.
- s5 act_verify: NO documents. Commit from retained state; the
  instruction names the record shape and provenance discipline only.

Also implements the two gate upgrades the probe record adopted: the
subject-mention conjunction (a gold passage must mention both an answer
alias AND the question's subject) and word-boundary matching for short
aliases (below 4 normalized characters) in both ``alias_hit_v2`` and
``gold_sane_v2``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from rsicontext.lifecycle.env import normalize_answer_text
from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_FAMILY = "research-v2"
_SURVEY_NOISE_DOCS = 8
_FINAL_RECORD_ID = "answer_project"
_SOURCE_URL_TEMPLATE = "kilt:popqa:{row_id}"
_RETRIEVED_DATE = "2026-09-20"
_SHORT_ALIAS_BOUNDARY = 4
_WORD = r"\b{}\b"


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _ctx_has_answer(ctx: Mapping[str, object]) -> bool:
    flag = ctx.get("has_answer")
    return flag is True or flag == 1


def _ctx_body(ctx: Mapping[str, object]) -> bool:
    return bool(str(ctx.get("text") or "").strip() and str(ctx.get("title") or "").strip())


def _decode_possible_answers(raw: object) -> tuple[str, ...]:
    import json

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


def _decode_subject_aliases(raw: object) -> tuple[str, ...]:
    """PopQA subjects carry ``s_aliases`` as a JSON list string (or list)."""

    import json

    if raw is None:
        return ()
    try:
        decoded = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return ()
    if not isinstance(decoded, list):
        return ()
    return tuple(entry for entry in decoded if isinstance(entry, str) and entry.strip())


def _ctx_doc_id(ctx: Mapping[str, object], position: int) -> str:
    raw_id = ctx.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        slug = re.sub(r"[^A-Za-z0-9_-]", "-", raw_id.strip())[:60]
        return f"doc-{slug}-{position}"
    if isinstance(raw_id, int) and not isinstance(raw_id, bool):
        return f"doc-{raw_id}-{position}"
    return f"doc-{position}"


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


def alias_hit_v2(reply: str, aliases: tuple[str, ...]) -> bool:
    """Alias containment with word boundaries for short aliases.

    Long aliases (>= 4 normalized characters) use plain containment in
    either direction, as in ``lifecycle.env.alias_hit``; short aliases
    (country codes like 'PL') require a whole-word match on at least one
    side, so 'PL' no longer hits inside 'places'.
    """

    reply_norm = normalize_answer_text(reply)
    if not reply_norm:
        return False
    for alias in aliases:
        alias_norm = normalize_answer_text(alias)
        if not alias_norm:
            continue
        if len(alias_norm) >= _SHORT_ALIAS_BOUNDARY:
            if alias_norm in reply_norm or reply_norm in alias_norm:
                return True
        else:
            if re.search(_WORD.format(re.escape(alias_norm)), reply_norm) or (
                reply_norm == alias_norm
            ):
                return True
    return False


def gold_sane_v2(row: Mapping[str, object]) -> bool:
    """Answer-alias AND subject-mention conjunction gate (v2).

    A row is gold-sane when some gold passage (``has_answer`` flagged,
    non-empty) contains, after normalization, both (i) an answer alias —
    long aliases by containment, short aliases by whole-word match — and
    (ii) the question's subject: ``subj``, ``s_wiki_title``, or an entry
    of ``s_aliases``. The subject half is what rejects the wrong-entity
    retrieval class (the 4402885 pattern: a 'Poland' passage that never
    mentions 'Wilcza Jama'). Malformed rows return False, never raise.
    """

    try:
        aliases = _decode_possible_answers(row.get("possible_answers"))
    except (TypeError, ValueError):
        return False
    subject = row.get("subj")
    subject_terms = [str(subject)] if isinstance(subject, str) and subject.strip() else []
    wiki_title = row.get("s_wiki_title")
    if isinstance(wiki_title, str) and wiki_title.strip():
        subject_terms.append(wiki_title)
    subject_terms.extend(_decode_subject_aliases(row.get("s_aliases")))
    subject_norms = [
        normalize_answer_text(term) for term in subject_terms if normalize_answer_text(term)
    ]
    if not subject_norms:
        return False
    raw_ctxs = row.get("ctxs")
    if not isinstance(raw_ctxs, list):
        return False
    gold_texts: list[str] = []
    for ctx in raw_ctxs:
        if not isinstance(ctx, Mapping) or not _ctx_has_answer(ctx):
            continue
        text = ctx.get("text")
        if not isinstance(text, str) or not text.strip():
            return False
        gold_texts.append(text)
    if not gold_texts:
        return False
    normalized = [normalize_answer_text(text) for text in gold_texts]
    answer_seen = any(alias_hit_v2(text, aliases) for text in normalized)
    subject_seen = any(
        term in text for text in normalized for term in subject_norms if len(term) >= 3
    ) or any(
        re.search(_WORD.format(re.escape(term)), text)
        for text in normalized
        for term in subject_norms
        if 0 < len(term) < 3
    )
    return answer_seen and subject_seen


def _verification_check(answer_aliases: tuple[str, ...]) -> str:
    """A clue that discriminates candidates without containing the answer.

    Derives, per alias: first letter, word count, and initials. E.g.
    aliases ('punk rock', 'punk') → 'primary alias: 2 words, starts with
    "p", initials "pr"'. A participant holding a candidate can check it;
    a participant with nothing gains no answer from this block.
    """

    parts: list[str] = []
    for alias in answer_aliases[:3]:
        words = [word for word in re.findall(r"[A-Za-z]+", alias) if word]
        if not words:
            continue
        initials = "".join(word[0] for word in words)
        parts.append(f"{len(words)} word(s), starts with '{words[0][0]}', initials '{initials}'")
    listed = "; ".join(parts) if parts else "no alias clue available"
    return (
        "Verification check (does NOT contain the answer): the accepted answer "
        f"must satisfy one of — {listed}."
    )


def build_research_v2_instance(
    popqa_jsonl_row: Mapping[str, object],
    *,
    world_id: str,
    variant_label: str,
    noise_positions: list[int],
) -> LifecycleInstance:
    """Build one leak-closed research-v2 instance.

    ``noise_positions`` selects this variant's survey slice (positions in
    the row's ctxs); gold passages always join stage 1. Raises ValueError
    for rows without usable material.
    """

    question = _require_str(popqa_jsonl_row.get("question"), "question")
    row_id_raw = popqa_jsonl_row.get("id")
    row_id = str(row_id_raw) if row_id_raw is not None else "unknown"
    answer_aliases = _decode_possible_answers(popqa_jsonl_row.get("possible_answers"))
    answer_norm = answer_aliases[0]
    raw_ctxs = popqa_jsonl_row.get("ctxs")
    if not isinstance(raw_ctxs, list) or not raw_ctxs:
        raise ValueError("ctxs must be a non-empty list")
    ctxs: list[Mapping[str, object]] = [ctx for ctx in raw_ctxs if isinstance(ctx, Mapping)]
    gold_positions = [
        position for position, ctx in enumerate(ctxs) if _ctx_has_answer(ctx) and _ctx_body(ctx)
    ]
    if not gold_positions:
        raise ValueError("research-v2 requires at least one usable gold ctx")
    usable_noise = [
        position
        for position in noise_positions
        if position < len(ctxs) and _ctx_body(ctxs[position])
    ]
    if not usable_noise:
        raise ValueError("research-v2 requires at least one usable noise doc in the slice")
    survey_noise = usable_noise[:_SURVEY_NOISE_DOCS]

    def doc_at(position: int) -> DocumentRef:
        return _build_document(ctxs[position], position, row_id)

    survey_docs = tuple(doc_at(position) for position in (*survey_noise, *gold_positions))
    gold_docs = tuple(doc_at(position) for position in gold_positions)
    gold_doc_ids = tuple(document.doc_id for document in gold_docs)
    anchor_gold = gold_docs[0]
    scope_noise = doc_at(usable_noise[0])
    signal_noise = doc_at(usable_noise[-1])

    information_scale_tokens = sum(1 + len(d.text.split()) for d in survey_docs)
    return LifecycleInstance(
        instance_id=f"{_FAMILY}-{world_id}-{variant_label}",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
                    f"[Project {variant_label} | world {world_id}] Survey the project "
                    f"document base for the question: {question!r}. Build your working "
                    "notes; they are your ONLY carry-forward — later stages will not "
                    "re-show these documents."
                ),
                documents=survey_docs,
                gold_evidence_ids=gold_doc_ids,
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text=(
                    "A scope constraint arrives: only evidence whose source passage "
                    f"carries the title {anchor_gold.title!r} may support the final "
                    "answer. From your retained notes, identify which document ids "
                    "qualify. (The document is NOT re-shown.)"
                ),
                documents=(scope_noise,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s3-delegation",
                kind="delegation",
                prompt_text=(
                    "Delegate verification of your candidate answer to a bounded "
                    "sub-agent over the documents below. Required sub-return fields: "
                    "finding, source (doc id), applicability condition. The documents "
                    "below do NOT contain the answer; a return citing them cannot "
                    "justify an answer — treat that as a verification failure."
                ),
                documents=(scope_noise, signal_noise),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text=(
                    f"Rule change: document {signal_noise.doc_id} "
                    f"({signal_noise.title!r}) is now marked as a superseding signal; "
                    "prior conclusions relying on pre-rule-change state must be "
                    "re-verified. " + _verification_check(answer_aliases)
                ),
                documents=(
                    DocumentRef(
                        doc_id=signal_noise.doc_id,
                        title=signal_noise.title,
                        text=signal_noise.text,
                        source_url=signal_noise.source_url,
                        retrieved_date=signal_noise.retrieved_date,
                        superseded_by=anchor_gold.doc_id,
                    ),
                ),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Commit the final answer artifact through a sandbox write: create "
                    f"record {_FINAL_RECORD_ID} with your answer and the gold support "
                    "doc ids you retained, then finalize it with provenance. No "
                    "documents are attached: the answer and its support must come "
                    "from your retained state."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={
                    _FINAL_RECORD_ID: {
                        "answer": answer_norm,
                        "supports": list(gold_doc_ids),
                        "status": "final",
                    },
                },
                expected_aliases=answer_aliases,
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=information_scale_tokens,
            dependency_distance_stages=4,
            persistence_span_resets=4,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=answer_norm,
        sandbox_spec={
            "records": [_FINAL_RECORD_ID],
            "action_kinds": ["create_record", "update_record", "finalize"],
        },
        answer_aliases=answer_aliases,
    )


__all__ = [
    "alias_hit_v2",
    "build_research_v2_instance",
    "gold_sane_v2",
]
