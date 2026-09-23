"""Option-2 world builder: one shared constructor for real-document-segment worlds.

Spec: the frozen task cards (docs/task-card-research-v3-{zephyr,quill,atlas}.md).
Every Option-2 world is the same v3 dependency structure instantiated over a
DISJOINT real PopQA/KILT segment: five candidate rows (gold passage = the
candidate's plan document; the row's answer = the candidate property), the
rows' noise passages as survey bulk, a scope constraint, a PARTIAL rule
change, and an evaluator-owned commit precondition. The GSM1k double-solve
(card properties == corpus possible_answers[0]; legal set == the derived
permitted set) is asserted at build time; row-id disjointness across ALL
Option-2 worlds is asserted here (the FinEvo exclusion gate's mechanical
form) — no two segment worlds may share a row.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
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
_RETRIEVED_DATE = "2026-09-22"

#: One Option-2 world definition: five candidates over one relation, the
#: constraint scope (permitted property values), the rule-change scope
#: (which property values' evidence the revision supersedes), and the
#: check name. Everything else is shared structure.
WORLD_DEFS: dict[str, dict[str, object]] = {
    "zephyr": {
        "task": "Licensing decision",
        "check": "genre",
        "candidates": (
            {"row_id": "107903", "candidate": "play-the-game", "property": "rock music"},
            {"row_id": "110533", "candidate": "ill-be-there", "property": "pop music"},
            {"row_id": "1184585", "candidate": "unknown", "property": "fantasy"},
            {"row_id": "1260399", "candidate": "no-direction-home", "property": "documentary film"},
            {"row_id": "1558369", "candidate": "this-love", "property": "pop rock"},
        ),
        "permitted": ("rock music", "pop music", "pop rock", "documentary film"),
        "revision_scope_properties": ("documentary film",),
        # Constraint-evaluator correspondence (external review 3.4): every
        # sentence here has exactly ONE implemented check. The earlier
        # "post-1990 releases only" clause had no evaluator counterpart
        # (legal_plans derives from genre alone, and play-the-game — a 1980
        # Queen single — sat in the legal set), so the clause is removed
        # rather than half-enforced: a constraint the task does not grade
        # is a lie the evaluator tells the participant.
        "constraint_text": (
            "Scope: this constraint applies to the licensing decision only. "
            "The permitted genres are rock music, pop music, pop rock, and "
            "documentary film; candidates in any other genre are ineligible."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes genre verifications for FILM-CATEGORY "
            "candidates only (documentary film). Protocol revision 2 tightens "
            "the verification standard; genre evidence recorded under revision "
            "1 is stale for film-category commits. All other categories (rock "
            "music, pop music, pop rock) are unaffected."
        ),
    },
    "quill": {
        "task": "Editorial-board appointment",
        "check": "occupation",
        "candidates": (
            {"row_id": "1046764", "candidate": "poonatchi", "property": "politician"},
            {"row_id": "1419550", "candidate": "boyd", "property": "journalist"},
            {"row_id": "1658579", "candidate": "molyneux", "property": "astronomer"},
            {"row_id": "2201087", "candidate": "melani", "property": "composer"},
            {"row_id": "371747", "candidate": "jebb", "property": "diplomat"},
        ),
        "permitted": ("politician", "journalist", "astronomer", "diplomat"),
        "revision_scope_properties": ("politician", "diplomat"),
        "constraint_text": (
            "Scope: this constraint applies to the editorial-board appointment "
            "only. The permitted professions are politician, journalist, "
            "astronomer, and diplomat; the appointment requires a public-facing "
            "profession, so non-public professions (composer) are ineligible."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes occupation verifications for "
            "PUBLIC-OFFICE candidates only (politician, diplomat). Protocol "
            "revision 2 tightens the verification standard; occupation evidence "
            "recorded under revision 1 is stale for public-office commits. All "
            "other categories (journalist, astronomer, composer) are unaffected."
        ),
    },
    "atlas": {
        "task": "Field-station permit",
        "check": "site",
        "candidates": (
            {"row_id": "2182232", "candidate": "burgundy", "property": "France"},
            {"row_id": "2630203", "candidate": "hulst", "property": "France"},
            {"row_id": "4458676", "candidate": "soheyl", "property": "Iran"},
            {"row_id": "4883237", "candidate": "kowale", "property": "Poland"},
            {"row_id": "6312474", "candidate": "ghana-navy", "property": "Ghana"},
        ),
        "permitted": ("France", "Poland"),
        "revision_scope_properties": ("Poland",),
        "constraint_text": (
            "Scope: this constraint applies to the field-station permit only. "
            "The permit covers EU-REGION sites: France and Poland qualify; "
            "sites in any other country are ineligible."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes site-eligibility verifications for "
            "NEW-MEMBER states only (Poland, joined 2004). Protocol revision 2 "
            "tightens the verification standard; site evidence recorded under "
            "revision 1 is stale for new-member commits. Founding-member sites "
            "(France) are unaffected."
        ),
    },
    "lumen": {
        "task": "Narrative-work licensing round",
        "check": "genre",
        "candidates": (
            {"row_id": "1577066", "candidate": "creatures", "property": "platform game"},
            {"row_id": "1827971", "candidate": "sublime", "property": "horror film"},
            {"row_id": "1830615", "candidate": "the-experts", "property": "comedy film"},
            {"row_id": "2075682", "candidate": "satanic-slaughter", "property": "black metal"},
        ),
        "permitted": ("platform game", "horror film", "comedy film"),
        "revision_scope_properties": ("platform game",),
        "constraint_text": (
            "Scope: this constraint applies to the narrative-work licensing "
            "round only. The permitted genres are platform game, horror film, "
            "and comedy film; music-category candidates (black metal) are "
            "ineligible — the round covers narrative and screen works only."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes genre verifications for GAME-"
            "CATEGORY candidates only (platform game). Protocol revision 2 "
            "tightens the verification standard; genre evidence recorded under "
            "revision 1 is stale for game-category commits. Film categories "
            "(horror film, comedy film) are unaffected."
        ),
    },
    "swift": {
        "task": "Invitational registration",
        "check": "sport",
        "candidates": (
            {"row_id": "136686", "candidate": "bednarik", "property": "American football"},
            {"row_id": "1841625", "candidate": "racicot", "property": "ice hockey"},
            {"row_id": "211746", "candidate": "era", "property": "baseball"},
            {"row_id": "2225185", "candidate": "dulin", "property": "rugby union"},
            {"row_id": "2714297", "candidate": "koroviansky", "property": "volleyball"},
        ),
        "permitted": ("American football", "ice hockey", "rugby union", "volleyball"),
        "revision_scope_properties": ("ice hockey",),
        "constraint_text": (
            "Scope: this constraint applies to the invitational registration "
            "only. The permitted sports are American football, ice hockey, "
            "rugby union, and volleyball; baseball is ineligible — the "
            "invitational covers field and team sports only."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes sport verifications for WINTER-"
            "SPORT candidates only (ice hockey). Protocol revision 2 tightens "
            "the verification standard; sport evidence recorded under revision "
            "1 is stale for winter-sport commits. All other categories are "
            "unaffected."
        ),
    },
    "mirror": {
        "task": "Treaty accession review",
        "check": "capital",
        "candidates": (
            {"row_id": "1867834", "candidate": "belize", "property": "Belmopan"},
            {"row_id": "1939901", "candidate": "indonesia", "property": "Jakarta"},
            {"row_id": "2658151", "candidate": "denmark", "property": "Copenhagen"},
            {"row_id": "1620826", "candidate": "tokugawa", "property": "Edo"},
            {"row_id": "1003808", "candidate": "hanover", "property": "Hanover"},
        ),
        "permitted": ("Belmopan", "Jakarta", "Copenhagen", "Edo"),
        "revision_scope_properties": ("Belmopan",),
        "constraint_text": (
            "Scope: this constraint applies to the treaty accession review "
            "only. The permitted capital seats are Belmopan, Jakarta, "
            "Copenhagen, and Edo; electoral-electorate states (the Kingdom of "
            "Hanover was an Electorate per its own passage) are ineligible."
        ),
        "rule_change_text": (
            "Scope: this revision supersedes capital verifications for "
            "RELOCATED-CAPITAL states only (Belize — Belmopan was a planned "
            "relocation per its own passage). Protocol revision 2 tightens the "
            "verification standard; capital evidence recorded under revision 1 "
            "is stale for relocated-capital commits. All other seats are "
            "unaffected."
        ),
    },
}


def option2_world_ids() -> tuple[str, ...]:
    """The registered Option-2 world ids, in definition order."""

    return tuple(WORLD_DEFS)


def _load_rows() -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    with _POPQA.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows[str(parsed.get("id"))] = parsed
    return rows


def _gold_passage(row: Mapping[str, object]) -> tuple[str, str, str]:
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
                return f"doc-gold-{row.get('id')}-{position}", title, text
    raise ValueError(f"row {row.get('id')} has no usable gold passage")


def _noise_passages(row: Mapping[str, object], limit: int) -> list[tuple[str, str, str]]:
    ctxs = row.get("ctxs")
    if not isinstance(ctxs, list):
        return []
    out: list[tuple[str, str, str]] = []
    for position, ctx in enumerate(ctxs):
        if len(out) >= limit:
            break
        if not isinstance(ctx, Mapping) or ctx.get("has_answer") in (True, 1):
            continue
        title = str(ctx.get("title") or "").strip()
        text = str(ctx.get("text") or "").strip()
        if title and text:
            out.append((f"doc-noise-{row.get('id')}-{position}", title, text))
    return out


def _doc(doc_id: str, title: str, text: str, *, source: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=source,
        retrieved_date=_RETRIEVED_DATE,
    )


def _assert_option2_gates(rows: Mapping[str, Mapping[str, object]]) -> None:
    """The Option-2 gates, mechanical form.

    (1) Disjointness (FinEvo exclusion): no row id may appear in two
    Option-2 worlds. (2) Double-solve (GSM1k): every candidate's card
    property == the corpus row's first possible_answer, and every
    world's legal set == the derived permitted set.
    """

    seen_rows: dict[str, str] = {}
    for world_id, definition in WORLD_DEFS.items():
        candidates = definition["candidates"]
        assert isinstance(candidates, tuple)
        for candidate in candidates:
            row_id = str(candidate["row_id"])
            if row_id in seen_rows and seen_rows[row_id] != world_id:
                raise ValueError(
                    f"Option-2 gate: row {row_id} is shared between worlds "
                    f"{seen_rows[row_id]!r} and {world_id!r}"
                )
            seen_rows[row_id] = world_id
            row = rows.get(row_id)
            if not isinstance(row, dict):
                raise ValueError(f"Option-2 candidate row {row_id} is missing")
            raw = row.get("possible_answers")
            answers = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(answers, list) or not answers:
                raise ValueError(f"row {row_id} has no possible_answers")
            if str(candidate["property"]) != str(answers[0]):
                raise ValueError(
                    f"card/constructor disagreement on row {row_id}: card says "
                    f"{candidate['property']!r}, corpus says {answers[0]!r}"
                )
        permitted = definition["permitted"]
        assert isinstance(permitted, tuple)
        derived = sorted(
            str(candidate["candidate"])
            for candidate in candidates
            if str(candidate["property"]) in permitted
        )
        if len(derived) != len(set(derived)):
            raise ValueError(f"world {world_id!r}: duplicate candidate keys")


def build_option2_world(world_id: str, *, instance_id: str | None = None) -> LifecycleInstance:
    """Build one Option-2 world instance from its definition."""

    definition = WORLD_DEFS.get(world_id)
    if not isinstance(definition, dict):
        raise ValueError(f"unknown Option-2 world: {world_id!r}")
    rows = _load_rows()
    _assert_option2_gates(rows)

    candidates = definition["candidates"]
    assert isinstance(candidates, tuple)
    permitted = definition["permitted"]
    assert isinstance(permitted, tuple)
    scope_properties = definition["revision_scope_properties"]
    assert isinstance(scope_properties, tuple)
    check_name = str(definition["check"])
    task = str(definition["task"])

    legal_plans = tuple(
        str(candidate["candidate"])
        for candidate in candidates
        if str(candidate["property"]) in permitted
    )
    # The evaluator-owned verification oracle: the environment can execute
    # the world's check for every candidate, with a verdict derived from the
    # SAME properties the legal set derives from (permitted -> pass). The
    # evidence record therefore cannot disagree with the world's own
    # semantics, and a participant cannot write one at all — only request
    # it (env-side ``request_verification``).
    verification_oracle: dict[str, dict[str, bool]] = {
        check_name: {
            str(candidate["candidate"]): str(candidate["property"]) in permitted
            for candidate in candidates
        }
    }
    # plan_requirements: the revision-scoped plans need the check at the
    # current revision; the domain label is the scope property (the
    # requirement is keyed by the COMMITTED PLAN, evaluator-side).
    plan_requirements: dict[str, dict[str, str]] = {}
    for candidate in candidates:
        if str(candidate["property"]) in scope_properties:
            plan_requirements[str(candidate["candidate"])] = {
                "domain": str(candidate["property"]),
                "requires_check": check_name,
            }

    survey_docs: list[DocumentRef] = []
    for candidate in candidates:
        row = rows[str(candidate["row_id"])]
        _doc_id, title, text = _gold_passage(row)
        survey_docs.append(
            _doc(
                f"doc-cand-{candidate['candidate']}",
                title,
                text,
                source=f"kilt:popqa:{candidate['row_id']}",
            )
        )
        for noise_id, noise_title, noise_text in _noise_passages(row, 2):
            survey_docs.append(
                _doc(
                    noise_id,
                    noise_title,
                    noise_text,
                    source=f"kilt:popqa:{candidate['row_id']}",
                )
            )

    prefix = f"v3-{world_id}"
    survey_docs.append(
        _doc(
            f"doc-{world_id}-verif-db",
            "Verification protocol",
            (
                f"The verification protocol defines: the {check_name} check "
                f"validates a candidate's {check_name} claim against its "
                "passage. Protocol revision 1 applies; commits in the "
                "revision's scope require revision 2."
            ),
            source=f"{prefix}:protocol",
        )
    )
    constraint_doc = _doc(
        f"doc-{world_id}-constraint-k",
        f"{task} constraint",
        str(definition["constraint_text"]),
        source=f"{prefix}:constraint",
    )
    delegation_doc = _doc(
        f"doc-{world_id}-delegation-targets",
        "Delegation surface",
        (
            "A bounded sub-agent may be asked to verify a named candidate "
            "document against a named check. A usable return carries finding, "
            "source doc id, and applicability condition; a return without "
            "those fields cannot justify a conclusion."
        ),
        source=f"{prefix}:delegation",
    )
    rule_change_doc = DocumentRef(
        doc_id=f"doc-{world_id}-rule-change",
        title=f"{check_name}-verification protocol revision notice",
        text=(
            f"[[doc:doc-{world_id}-rule-change]] {check_name}-verification "
            f"protocol revision notice\n{definition['rule_change_text']}"
        ),
        source_url=f"{prefix}:rule-change",
        retrieved_date=_RETRIEVED_DATE,
        superseded_by=f"doc-{world_id}-verif-db",
    )

    information_scale_tokens = sum(1 + len(doc.text.split()) for doc in survey_docs)
    return LifecycleInstance(
        instance_id=instance_id or f"research-v3-{world_id}-0001",
        family=_FAMILY,
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text=(
                    f"[{task} project] Survey the candidate documents and the "
                    "verification protocol. Build your working notes; they are "
                    "your only carry-forward — later stages will not re-show "
                    "these documents (re-reading is available at a ledgered "
                    "cost through your own tool surface)."
                ),
                documents=tuple(survey_docs),
                gold_evidence_ids=tuple(
                    f"doc-cand-{candidate['candidate']}" for candidate in candidates
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
                rule_change_effect=2,
                rule_change_scope=[check_name],
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text=(
                    f"Commit the {task.lower()}: create and finalize record "
                    f"{_COMMIT_RECORD} naming the chosen candidate, with "
                    f"candidate status records ({_STATUS_RECORD}) and "
                    f"verification runs ({_VERIF_RECORD}) it relies on. "
                    "Finalization is refused unless the referenced records "
                    "exist, the committed candidate is legal, revision-scoped "
                    "commits carry current-revision evidence, and the "
                    "constraint holds. No documents are attached."
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
                    "legal_plans": list(legal_plans),
                    "plan_requirements": plan_requirements,
                    "current_revision": 2,
                    "revision_scope": [check_name],
                },
                verification_oracle=verification_oracle,
            ),
        ),
        axes=DescriptionAxes(
            information_scale_tokens=information_scale_tokens,
            dependency_distance_stages=4,
            persistence_span_resets=4,
            action_dependency="strong",
            environment_changes=1,
        ),
        answer_norm=legal_plans[0],
        sandbox_spec={
            "records": [_COMMIT_RECORD, _STATUS_RECORD, _VERIF_RECORD],
            "action_kinds": [
                "create_record",
                "update_record",
                "finalize",
                "request_verification",
            ],
        },
        answer_aliases=legal_plans,
    )


def option2_row_ids(world_ids: Sequence[str] | None = None) -> frozenset[str]:
    """The row ids used by the given Option-2 worlds (all by default)."""

    ids: set[str] = set()
    for world_id in world_ids or WORLD_DEFS:
        definition = WORLD_DEFS[world_id]
        candidates = definition["candidates"]
        assert isinstance(candidates, tuple)
        ids.update(str(candidate["row_id"]) for candidate in candidates)
    return frozenset(ids)


__all__ = [
    "build_option2_world",
    "option2_row_ids",
    "option2_world_ids",
]
