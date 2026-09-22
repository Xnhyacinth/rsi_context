"""Option-2 world gates and engine tests: zephyr, quill, atlas.

Pins for every Option-2 world (real PopQA/KILT segment material): the
build-time GSM1k double-solve (card property == corpus possible_answers[0];
legal set == derived permitted set), cross-world row-id disjointness (the
FinEvo exclusion gate's mechanical form), the v3 grammar, and the commit
matrix — permitted non-scoped candidates pass with revision-1 evidence,
revision-scoped candidates need revision 2, out-of-scope candidates are
refused with named causes.
"""

from __future__ import annotations

import json

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3_segment import (
    WORLD_DEFS,
    build_option2_world,
    option2_row_ids,
    option2_world_ids,
)
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle

_COMMIT = "migration_commit"
_STATUS = "candidate_status"

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


def test_option2_rows_disjoint_from_v2_pool_and_each_other() -> None:
    all_ids = option2_row_ids()
    assert all_ids.isdisjoint(_V2_WORLD_IDS)
    assert len(all_ids) == sum(
        len(world["candidates"])  # type: ignore[arg-type]
        for world in WORLD_DEFS.values()
    )


def test_option2_double_solve_against_corpus() -> None:
    rows: dict[str, dict[str, object]] = {}
    with open(
        "data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl", encoding="utf-8"
    ) as handle:
        for line in handle:
            parsed = json.loads(line)
            rows[str(parsed["id"])] = parsed
    for world_id in option2_world_ids():
        definition = WORLD_DEFS[world_id]
        for candidate in definition["candidates"]:  # type: ignore[union-attr]
            answers = json.loads(str(rows[str(candidate["row_id"])]["possible_answers"]))
            assert str(candidate["property"]) == str(answers[0])
    # Builds assert the legal-set derivation (a successful build passes).


@pytest.mark.parametrize("world_id", list(option2_world_ids()))
def test_option2_grammar(world_id: str) -> None:
    inst = build_option2_world(world_id)
    assert inst.family == "research-v3"
    assert [stage.kind for stage in inst.stages] == [
        "survey",
        "constraint_injection",
        "delegation",
        "rule_change",
        "act_verify",
    ]
    assert inst.stages[4].documents == ()
    assert inst.stages[3].documents[0].superseded_by.endswith("verif-db")
    precondition = inst.stages[4].commit_precondition
    assert isinstance(precondition, dict)
    # Real KILT material in the survey; authored event docs separate.
    sources = {
        document.source_url
        for stage in inst.stages
        for document in stage.documents
        if document.source_url
    }
    assert any(s.startswith("kilt:popqa:") for s in sources)
    assert any(s.startswith(f"v3-{world_id}:") for s in sources)


# --- Commit matrix per world -------------------------------------------------------


class _Option2Hook:
    """Commits a named candidate with a check record at a given revision."""

    def __init__(self, candidate: str, check: str, *, revision: int) -> None:
        self.candidate = candidate
        self.check = check
        self.revision = revision

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.kind != "act_verify":
            return StageResponse(pack_text="notes")
        actions: list[Action] = []
        refs: list[str] = []
        actions.append(
            Action(
                kind="create_record",
                record_id="verif-a",
                fields={"check": self.check, "protocol_revision": self.revision},
            )
        )
        refs.append("verif-a")
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
        return StageResponse(pack_text="commit", actions=tuple(actions))


def _commit_matrix(world_id: str) -> list[tuple[str, int, bool, str]]:
    definition = WORLD_DEFS[world_id]
    permitted = set(definition["permitted"])  # type: ignore[arg-type]
    scope = set(definition["revision_scope_properties"])  # type: ignore[arg-type]
    cases: list[tuple[str, int, bool, str]] = []
    for candidate in definition["candidates"]:  # type: ignore[union-attr]
        key = str(candidate["candidate"])
        prop = str(candidate["property"])
        if prop not in permitted:
            cases.append((key, 2, False, "legal set"))
        elif prop in scope:
            cases.append((key, 2, True, ""))
            cases.append((key, 1, False, "stale"))
        else:
            cases.append((key, 1, True, ""))
    return cases


_ZEPHYR = _commit_matrix("zephyr")
_QUILL = _commit_matrix("quill")
_ATLAS = _commit_matrix("atlas")


@pytest.mark.parametrize(
    "world_id,candidate,revision,passes,cause",
    [
        *[("zephyr", *case) for case in _ZEPHYR],
        *[("quill", *case) for case in _QUILL],
        *[("atlas", *case) for case in _ATLAS],
    ],
)
def test_option2_commit_matrix(
    world_id: str, candidate: str, revision: int, passes: bool, cause: str
) -> None:
    check = str(WORLD_DEFS[world_id]["check"])
    record = run_lifecycle(
        build_option2_world(world_id),
        _Option2Hook(candidate, check, revision=revision),
        ProjectState(),
    )
    assert record.final_check.passed is passes, record.final_check.failures
    if not passes:
        failures = " | ".join(record.final_check.failures)
        assert cause in failures, record.final_check.failures
