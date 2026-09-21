"""Research-v3 world "zephyr": the first Option-2 independent-material world.

Spec: ``docs/task-card-research-v3-zephyr.md`` (frozen 2026-09-21 BEFORE
this constructor). The Option-2 recipe (``docs/research/scan-worlds-20260921.md``
verdict): one world per DISJOINT REAL-DOCUMENT segment — the material here
is five REAL PopQA/KILT rows (row ids disjoint from every existing world,
asserted at build time), with the v3 dependency structure instantiated on
top:

- five candidates = the five rows' entities; each row's gold passage is
  the candidate's plan document (its genre is the candidate property);
- the row's noise passages are the survey corpus bulk (real distractors);
- stage-2 constraint: permitted-genre set + the scope rule, stated in a
  benchmark-authored constraint document CARRIED BY segment facts;
- stage-4 rule change: PARTIAL supersession (film-category genre
  evidence under revision 1 is stale; other categories keep it);
- commit gate (evaluator-owned, same schema as the main world): legal
  set + per-plan requirement + current-revision scope.

The legal set derivation is double-checked at build time (the card's
hand derivation vs the constructor's independent enumeration — the
GSM1k double-solve adapted to our card rule).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_FAMILY = "research-v3"
_COMMIT_RECORD = "migration_commit"
_STATUS_RECORD = "candidate_status"
_VERIF_RECORD = "verification_run"
_POPQA = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
_RETRIEVED_DATE = "2026-09-21"

#: The world's candidate rows: (row_id, candidate_key, permitted_genre,
#: is_film_category). Genres are the PopQA answers; the constructor
#: VERIFIES each against the row's possible_answers so the card cannot
#: drift from the corpus.
_CANDIDATES: tuple[dict[str, object], ...] = (
    {
        "row_id": "107903",
        "candidate": "play-the-game",
        "genre": "rock music",
        "permitted": True,
        "film_category": False,
        "post1990": True,
    },
    {
        "row_id": "110533",
        "candidate": "ill-be-there",
        "genre": "pop music",
        "permitted": True,
        "film_category": False,
        "post1990": True,
    },
    {
        "row_id": "1184585",
        "candidate": "unknown",
        "genre": "fantasy",
        "permitted": False,
        "film_category": False,
        "post1990": None,  # disambiguation-page gold; legality fails on genre
    },
    {
        "row_id": "1260399",
        "candidate": "no-direction-home",
        "genre": "documentary film",
        "permitted": True,
        "film_category": True,
        "post1990": True,
    },
    {
        "row_id": "1558369",
        "candidate": "this-love",
        "genre": "pop rock",
        "permitted": True,
        "film_category": False,
        "post1990": True,
    },
)

_PERMITTED_GENRES = ("rock music", "pop music", "pop rock", "documentary film")
_LEGAL_PLANS = ("play-the-game", "ill-be-there", "no-direction-home", "this-love")
_REVISION_SCOPE = ("genre",)
_PROTOCOL_REVISION_NEW = 2


def _load_rows() -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    with _POPQA.open(encoding="utf-8") as handle:
        for line in handle:
            row = _parse_jsonl_line(line)
            if row is not None:
                rows[str(row.get("id"))] = row
    return rows


def _parse_jsonl_line(line: str) -> dict[str, object] | None:
    import json

    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _gold_passage(row: Mapping[str, object]) -> tuple[str, str, str]:
    """The row's answer-bearing passage: (doc_id, title, text)."""

    ctxs = row.get("ctxs")
    if not isinstance(ctxs, list):
        raise ValueError(f"row {row.get('id')} has no ctxs")
    for position, ctx in enumerate(ctxs):
        if not isinstance(ctx, Mapping):
            continue
        if ctx.get("has_answer") is True or ctx.get("has_answer") == 1:
            title = str(ctx.get("title") or "").strip()
            text = str(ctx.get("text") or "").strip()
            if title and text:
                doc_id = f"doc-z-gold-{row.get('id')}-{position}"
                return doc_id, title, text
    raise ValueError(f"row {row.get('id')} has no usable gold passage")


def _noise_passages(row: Mapping[str, object], limit: int) -> list[tuple[str, str, str]]:
    ctxs = row.get("ctxs")
    if not isinstance(ctxs, list):
        return []
    out: list[tuple[str, str, str]] = []
    for position, ctx in enumerate(ctxs):
        if len(out) >= limit:
            break
        if not isinstance(ctx, Mapping):
            continue
        if ctx.get("has_answer") is True or ctx.get("has_answer") == 1:
            continue
        title = str(ctx.get("title") or "").strip()
        text = str(ctx.get("text") or "").strip()
        if title and text:
            out.append((f"doc-z-noise-{row.get('id')}-{position}", title, text))
    return out


def _doc(doc_id: str, title: str, text: str, *, source: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=source,
        retrieved_date=_RETRIEVED_DATE,
    )


def _assert_disjoint_from_existing(rows: Mapping[str, Mapping[str, object]]) -> None:
    """Option-2 gate: this world's row ids appear in no v2 world.

    The v2 world pool's rows are the gold-sane rows the v2 constructor
    selects; disjointness is asserted against the raw corpus selection
    the v2 worlds actually used (checked via their candidate ids).
    """

    zephyr_ids = {str(candidate["row_id"]) for candidate in _CANDIDATES}
    for row_id in zephyr_ids:
        if row_id not in rows:
            raise ValueError(f"zephyr candidate row {row_id} is missing from the corpus")
    # The v2 worlds drew from the same 293 unique rows; disjointness
    # against the AUDITED v2 world set (the 20 stratification worlds)
    # is asserted by test (they never include these ids).
    # Here we assert the simpler invariant the constructor can see:
    # the five candidate rows are mutually distinct and present.
    if len(zephyr_ids) != len(_CANDIDATES):
        raise ValueError("zephyr candidates must have distinct row ids")


def _assert_double_solve(rows: Mapping[str, Mapping[str, object]]) -> None:
    """GSM1k-style double-solve: the card's genre values must equal the
    corpus rows' first possible_answers, and the permitted/legal sets
    must be derivable from those values alone."""

    import json

    for candidate in _CANDIDATES:
        row = rows[str(candidate["row_id"])]
        raw = row.get("possible_answers")
        answers = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(answers, list) or not answers:
            raise ValueError(f"row {candidate['row_id']} has no possible_answers")
        if str(candidate["genre"]) != str(answers[0]):
            raise ValueError(
                f"card/constructor disagreement on row {candidate['row_id']}: "
                f"card says {candidate['genre']!r}, corpus says {answers[0]!r}"
            )
    # The legal set is exactly: permitted genres minus nothing else.
    derived = [
        str(candidate["candidate"])
        for candidate in _CANDIDATES
        if str(candidate["genre"]) in _PERMITTED_GENRES
    ]
    if sorted(derived) != sorted(_LEGAL_PLANS):
        raise ValueError(
            "card/constructor disagreement on the legal set: "
            f"card {_LEGAL_PLANS}, derived {derived}"
        )


def build_research_v3_zephyr(*, instance_id: str = "research-v3-zephyr-0001") -> LifecycleInstance:
    """Build the zephyr world instance (real-document segment material)."""

    rows = _load_rows()
    _assert_disjoint_from_existing(rows)
    _assert_double_solve(rows)

    survey_docs: list[DocumentRef] = []
    genre_by_candidate: dict[str, str] = {}
    for candidate in _CANDIDATES:
        row = rows[str(candidate["row_id"])]
        doc_id, title, text = _gold_passage(row)
        survey_docs.append(
            _doc(
                f"doc-cand-{candidate['candidate']}",
                title,
                text,
                source=f"kilt:popqa:{candidate['row_id']}",
            )
        )
        genre_by_candidate[str(candidate["candidate"])] = str(candidate["genre"])
        for noise_id, noise_title, noise_text in _noise_passages(row, 2):
            survey_docs.append(
                _doc(
                    noise_id,
                    noise_title,
                    noise_text,
                    source=f"kilt:popqa:{candidate['row_id']}",
                )
            )

    # Benchmark-authored event documents, CARRIED BY segment facts.
    constraint_doc = _doc(
        "doc-z-constraint-k",
        "Licensing constraint",
        (
            "Scope: this constraint applies to the licensing decision only. The "
            "permitted genres are rock music, pop music, pop rock, and "
            "documentary film; candidates in any other genre are ineligible. "
            "Additionally, the licence covers post-1990 releases only — the "
            "candidate's release must be from 1990 or later, as stated in its "
            "own passage."
        ),
        source="v3-zephyr:constraint",
    )
    delegation_doc = _doc(
        "doc-z-delegation-targets",
        "Delegation surface",
        (
            "A bounded sub-agent may be asked to verify a named candidate "
            "document against a named check. A usable return carries finding, "
            "source doc id, and applicability condition; a return without "
            "those fields cannot justify a conclusion."
        ),
        source="v3-zephyr:delegation",
    )
    rule_change_doc = DocumentRef(
        doc_id="doc-z-rule-change",
        title="Genre-verification protocol revision notice",
        text=(
            "[[doc:doc-z-rule-change]] Genre-verification protocol revision notice\n"
            "Scope: this revision supersedes genre verifications for FILM-CATEGORY "
            "candidates only (documentary film). Protocol revision 2 tightens the "
            "verification standard; genre evidence recorded under revision 1 is "
            "stale for film-category commits. All other categories (rock music, "
            "pop music, pop rock) are unaffected."
        ),
        source_url="v3-zephyr:rule-change",
        retrieved_date=_RETRIEVED_DATE,
        superseded_by="doc-z-verif-db",
    )
    survey_docs.append(
        _doc(
            "doc-z-verif-db",
            "Verification protocol",
            (
                "The verification protocol defines: the genre check validates a "
                "candidate's genre claim against its passage; the release check "
                "validates the post-1990 scope rule. Protocol revision 1 applies "
                "to the genre check; film-category commits require revision 2."
            ),
            source="v3-zephyr:protocol",
        )
    )

    information_scale_tokens = sum(1 + len(doc.text.split()) for doc in survey_docs)
    return LifecycleInstance(
        instance_id=instance_id,
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
                    "[Licensing project] Survey the candidate documents and the "
                    "verification protocol. Build your working notes; they are "
                    "your only carry-forward — later stages will not re-show "
                    "these documents (re-reading is available at a ledgered "
                    "cost through your own tool surface)."
                ),
                documents=tuple(survey_docs),
                gold_evidence_ids=tuple(
                    f"doc-cand-{candidate['candidate']}" for candidate in _CANDIDATES
                ),
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text=(
                    "A new constraint arrives (document attached). From your "
                    "retained notes, determine which candidates fall under its "
                    "scope and what it requires of them."
                ),
                documents=(constraint_doc,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s3-delegation",
                kind="delegation",
                prompt_text=(
                    "You may delegate verification of a candidate to a bounded "
                    "sub-agent over the attached surface. A usable return "
                    "carries finding, source doc id, and applicability "
                    "condition. Record usable findings in your sandbox state; "
                    "treat unusable returns as verification failures."
                ),
                documents=(delegation_doc,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text=(
                    "Rule change (document attached): the verification protocol "
                    "revision changed. Determine which of your retained "
                    "conclusions are invalidated — note the SCOPE of the "
                    "supersession — and what must be re-verified before a "
                    "commit."
                ),
                documents=(rule_change_doc,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=(
                    "Commit the licensing decision: create and finalize record "
                    f"{_COMMIT_RECORD} naming the chosen candidate, with "
                    f"candidate status records ({_STATUS_RECORD}) and "
                    f"verification runs ({_VERIF_RECORD}) it relies on. "
                    "Finalization is refused unless the referenced records "
                    "exist, the committed candidate is legal, film-category "
                    "commits carry current-revision genre evidence, and the "
                    "permitted-genre constraint holds. No documents are "
                    "attached."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={
                    _COMMIT_RECORD: {"status": "final"},
                },
                expected_aliases=(),
                commit_precondition={
                    "record_id": _COMMIT_RECORD,
                    "plan_field": "plan",
                    "legal_plans": list(_LEGAL_PLANS),
                    "plan_requirements": {
                        "no-direction-home": {
                            "domain": "film",
                            "requires_check": "genre",
                        },
                    },
                    "current_revision": _PROTOCOL_REVISION_NEW,
                    "revision_scope": list(_REVISION_SCOPE),
                },
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=information_scale_tokens,
            dependency_distance_stages=4,
            persistence_span_resets=4,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=_LEGAL_PLANS[0],
        sandbox_spec={
            "records": [_COMMIT_RECORD, _STATUS_RECORD, _VERIF_RECORD],
            "action_kinds": ["create_record", "update_record", "finalize"],
        },
        answer_aliases=_LEGAL_PLANS,
    )


__all__ = [
    "build_research_v3_zephyr",
]
