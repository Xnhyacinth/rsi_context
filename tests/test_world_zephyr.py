"""Engine-validity + Option-2 gate tests for the zephyr world.

The zephyr world is the first Option-2 independent-material world
(docs/task-card-research-v3-zephyr.md): real PopQA/KILT documents, the v3
dependency structure instantiated on them. Pins: (i) the GSM1k-style
double-solve (card genres == corpus answers; legal set == derived set);
(ii) id-disjointness from every existing world's material; (iii) the
engine layer — legal paths pass, illegality and scope failures name
causes, the film-category revision rule is PARTIAL; (iv) surface
differences from the parent worlds (real KILT text vs authored prose).
"""

from __future__ import annotations

import json

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.material_v3_variant import build_research_v3_variant
from rsicontext.lifecycle.material_v3_zephyr import (
    _CANDIDATES,
    build_research_v3_zephyr,
)
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle

_COMMIT = "migration_commit"
_STATUS = "candidate_status"

_ZEPHYR_ROW_IDS = {str(candidate["row_id"]) for candidate in _CANDIDATES}
#: The 20 audited v2 stratification worlds' row ids (from the artifact).
_V2_WORLD_IDS = {
    "1652383",
    "542248",
    "3006731",
    "984804",
    "6391380",
    "2120061",
    "6112233",
    "3538090",
    "3026511",
    "5035834",
    "2004556",
    "6392317",
    "3731527",
    "510782",
    "1650366",
    "3727461",
    "2734115",
    "1948707",
    "6271105",
    "5919594",
}


# --- Option-2 gates --------------------------------------------------------------


def test_zephyr_row_ids_disjoint_from_every_existing_world() -> None:
    # The FinEvo exclusion gate, mechanical form: no material row shared
    # with the v2 world pool; and the v3 main/variant worlds are
    # benchmark-authored (no PopQA rows at all) — asserted by surface.
    assert _ZEPHYR_ROW_IDS.isdisjoint(_V2_WORLD_IDS)
    main = build_research_v3_instance()
    main_ids = {document.source_url for stage in main.stages for document in stage.documents}
    zephyr = build_research_v3_zephyr()
    zephyr_ids = {document.source_url for stage in zephyr.stages for document in stage.documents}
    assert zephyr_ids.isdisjoint(main_ids)
    for spec_id in ("orinoco", "parana"):
        variant = build_research_v3_variant(spec_id)
        variant_ids = {
            document.source_url for stage in variant.stages for document in stage.documents
        }
        assert zephyr_ids.isdisjoint(variant_ids)


def test_double_solve_card_matches_corpus() -> None:
    # GSM1k double-solve, constructor side: the builder itself raises on
    # any card/corpus disagreement (genres and the legal set). A
    # successful build IS the pass; this test also re-derives from the
    # raw file so the invariant is pinned independently of the builder.
    rows: dict[str, dict[str, object]] = {}
    with open(
        "data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl", encoding="utf-8"
    ) as handle:
        for line in handle:
            parsed = json.loads(line)
            rows[str(parsed["id"])] = parsed
    for candidate in _CANDIDATES:
        row = rows[str(candidate["row_id"])]
        answers = json.loads(str(row["possible_answers"]))
        assert str(candidate["genre"]) == str(answers[0])
    zephyr = build_research_v3_zephyr()  # build asserts the legal-set derivation
    assert set(zephyr.answer_aliases) == {
        "play-the-game",
        "ill-be-there",
        "no-direction-home",
        "this-love",
    }


def test_zephyr_material_is_real_kilt_text() -> None:
    # Surface distinctness (odd-one-out basis, mechanical form): the
    # zephyr documents carry kilt:popqa source urls; the authored
    # worlds carry v3:/v3-variant: urls.
    zephyr = build_research_v3_zephyr()
    sources = {
        document.source_url
        for stage in zephyr.stages
        for document in stage.documents
        if document.source_url
    }
    kilt = {s for s in sources if s.startswith("kilt:popqa:")}
    authored = {s for s in sources if s.startswith("v3-zephyr:")}
    assert kilt and authored
    # The candidate plan documents are REAL passages.
    gold_ids = {document.doc_id for document in zephyr.stages[0].documents}
    assert {f"doc-cand-{c['candidate']}" for c in _CANDIDANTS()} <= gold_ids


def _CANDIDANTS() -> tuple[dict[str, object], ...]:
    return _CANDIDATES


# --- Engine layer -----------------------------------------------------------------


class _ZephyrHook:
    """Commits a named candidate with genre verifications at given revisions."""

    def __init__(self, candidate: str, *, genre_revision: int) -> None:
        self.candidate = candidate
        self.genre_revision = genre_revision

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind != "act_verify":
            return StageResponse(pack_text="zephyr notes")
        actions: list[Action] = []
        refs: list[str] = []
        actions.append(
            Action(
                kind="create_record",
                record_id="verif-genre",
                fields={"check": "genre", "protocol_revision": self.genre_revision},
            )
        )
        refs.append("verif-genre")
        actions.append(
            Action(
                kind="create_record",
                record_id=f"{_STATUS}-{self.candidate}",
                fields={"plan": self.candidate, "domain": "candidate"},
            )
        )
        refs.append(f"{_STATUS}-{self.candidate}")
        actions.append(
            Action(kind="create_record", record_id=_COMMIT, fields={"plan": self.candidate})
        )
        actions.append(
            Action(
                kind="finalize",
                record_id=_COMMIT,
                fields={"plan": self.candidate, "status": "final"},
                provenance=tuple(refs),
            )
        )
        return StageResponse(pack_text=f"zephyr commit {self.candidate}", actions=tuple(actions))


@pytest.mark.parametrize(
    "candidate,revision,passes",
    [
        ("play-the-game", 1, True),  # non-film: revision 1 fine
        ("ill-be-there", 1, True),
        ("this-love", 1, True),
        ("no-direction-home", 2, True),  # film-category: needs revision 2
        ("no-direction-home", 1, False),  # film-category with stale evidence
        ("unknown", 2, False),  # genre not permitted — illegal
    ],
)
def test_zephyr_commit_matrix(candidate: str, revision: int, passes: bool) -> None:
    record = run_lifecycle(
        build_research_v3_zephyr(),
        _ZephyrHook(candidate, genre_revision=revision),
        ProjectState(),
    )
    assert record.final_check.passed is passes, record.final_check.failures
    if not passes:
        failures = " | ".join(record.final_check.failures)
        if candidate == "unknown":
            assert "legal set" in failures
        else:
            assert "stale" in failures


def test_zephyr_structure_matches_v3_grammar() -> None:
    inst = build_research_v3_zephyr()
    assert inst.family == "research-v3"
    assert [stage.kind for stage in inst.stages] == [
        "survey",
        "constraint_injection",
        "delegation",
        "rule_change",
        "act_verify",
    ]
    assert inst.stages[4].documents == ()
    assert inst.stages[3].documents[0].superseded_by == "doc-z-verif-db"
    precondition = inst.stages[4].commit_precondition
    assert isinstance(precondition, dict)
    assert precondition["revision_scope"] == ["genre"]  # PARTIAL: only film-category
