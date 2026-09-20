"""Contract tests for the Phase B lifecycle runtime (research-v1).

Covers the WS-2 scope of ``docs/contract-tests-phase-b.md``: schema
round-trip byte-stability, evaluator-only field exclusion from StageView,
ObjectiveChecker exact/structural cases, an end-to-end scripted hook run,
provenance retention, and canonical run-record serialization. No reader
calls; qualification-gate panels are later deliverables and not tested here.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from rsicontext.lifecycle import (
    Action,
    CheckResult,
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    LifecycleRunRecord,
    ObjectiveChecker,
    ProjectState,
    StageResponse,
    StageSpec,
    StageView,
    alias_hit,
    build_example_instance,
    dump_instance,
    gold_entailment_sane,
    load_instance,
    run_lifecycle,
)
from rsicontext.lifecycle.env import ProjectStateError
from rsicontext.lifecycle.spec import canonical_instance_json


def make_document(doc_id: str, *, text: str = "evidence text", title: str = "Doc") -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\n{text}",
        source_url=f"kilt:popqa:test-{doc_id}",
        retrieved_date="2026-09-19",
    )


def make_axes() -> DescriptionAxes:
    return DescriptionAxes(
        information_scale_tokens=128,
        dependency_distance_stages=4,
        persistence_span_resets=3,
        action_dependency="strong",
        environment_changes=1,
    )


def make_instance() -> LifecycleInstance:
    final_fields = {"answer": "punk rock", "supports": ["doc-1"], "status": "final"}
    return LifecycleInstance(
        instance_id="research-v1-test-1",
        family="research-v1",
        stages=(
            StageSpec(
                stage_id="s1-survey",
                kind="survey",
                prompt_text="Survey the corpus.",
                documents=(make_document("doc-1"), make_document("doc-2")),
                gold_evidence_ids=("doc-1",),
            ),
            StageSpec(
                stage_id="s2-constraint",
                kind="constraint_injection",
                prompt_text="Scope rule: only gold-anchored support.",
                documents=(make_document("doc-1"),),
                gold_evidence_ids=("doc-1",),
            ),
            StageSpec(
                stage_id="s3-delegation",
                kind="delegation",
                prompt_text="Delegate verification.",
                documents=(make_document("doc-1"),),
                gold_evidence_ids=("doc-1",),
            ),
            StageSpec(
                stage_id="s4-rule-change",
                kind="rule_change",
                prompt_text="A document is superseded.",
                documents=(make_document("doc-2"),),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="s5-act-verify",
                kind="act_verify",
                prompt_text="Commit the final artifact.",
                documents=(make_document("doc-1"),),
                gold_evidence_ids=("doc-1",),
                expected_state_delta={"answer_project": final_fields},
            ),
        ),
        axes=make_axes(),
        answer_norm="punk rock",
        sandbox_spec={"records": ["answer_project"]},
    )


class ScriptedHook:
    """A deterministic hook: packs cite gold docs, act_verify writes the state."""

    def __init__(self, *, cite: bool = True, final_fields: dict[str, object] | None = None) -> None:
        self.cite = cite
        self.final_fields = final_fields
        self.seen_views: list[StageView] = []

    def on_stage(self, stage: StageView) -> StageResponse:
        self.seen_views.append(stage)
        if stage.kind == "act_verify":
            fields = (
                self.final_fields
                if self.final_fields is not None
                else {
                    "answer": "punk rock",
                    "supports": ["doc-1"],
                    "status": "final",
                }
            )
            return StageResponse(
                pack_text="[[doc:doc-1]] final answer commit" if self.cite else "no markers",
                actions=(
                    Action(kind="create_record", record_id="answer_project", fields=fields),
                    Action(
                        kind="finalize",
                        record_id="answer_project",
                        fields={},
                        provenance=("doc-1",),
                    ),
                ),
            )
        marker = f"notes citing [[doc:doc-1]] for {stage.stage_id}" if self.cite else "bare notes"
        return StageResponse(pack_text=marker, actions=())


def popqa_row() -> dict[str, object]:
    return {
        "id": 1652383,
        "question": "What genre is Holiday?",
        "possible_answers": '["punk rock", "punk", "punk music"]',
        "ctxs": [
            {
                "id": "2387652",
                "title": "Scuba Dice",
                "text": "power pop and punk, covering Green Day's Holiday.",
                "score": 0.68,
                "has_answer": True,
            },
            {
                "id": "33375787",
                "title": "The Holiday",
                "text": "The Holiday is a film unrelated to the song.",
                "score": 0.62,
                "has_answer": False,
            },
            {
                "id": "9182736",
                "title": "Punk rock",
                "text": "Punk rock is a music genre with fast tempos.",
                "score": 0.60,
                "has_answer": False,
            },
        ],
    }


# --- schema round-trip and byte stability -----------------------------------


def test_instance_round_trip_is_exact() -> None:
    inst = make_instance()
    reloaded = load_instance(json.loads(json.dumps(dump_instance(inst))))
    assert reloaded == inst


def test_round_trip_byte_stable_canonical_json() -> None:
    inst = make_instance()
    first = canonical_instance_json(inst)
    second = canonical_instance_json(load_instance(json.loads(first)))
    assert first == second


def test_round_trip_byte_stable_across_dict_orders() -> None:
    inst = make_instance()
    payload = dump_instance(inst)
    reordered = dict(reversed(list(payload.items())))
    reordered["stages"] = [
        {key: stage[key] for key in reversed(list(stage.keys()))} for stage in payload["stages"]
    ]
    assert canonical_instance_json(inst) == canonical_instance_json(
        load_instance(json.loads(json.dumps(reordered)))
    )


def test_load_instance_rejects_wrong_family() -> None:
    payload = dump_instance(make_instance())
    payload["family"] = "other-v1"
    with pytest.raises(ValueError, match="family"):
        load_instance(payload)


def test_stage_spec_rejects_gold_ids_not_in_documents() -> None:
    with pytest.raises(ValueError, match="gold evidence"):
        StageSpec(
            stage_id="s1-survey",
            kind="survey",
            prompt_text="p",
            documents=(make_document("doc-1"),),
            gold_evidence_ids=("doc-9",),
        )


def test_act_verify_requires_expected_state_delta() -> None:
    with pytest.raises(ValueError, match="expected_state_delta"):
        StageSpec(
            stage_id="s5-act-verify",
            kind="act_verify",
            prompt_text="p",
            documents=(make_document("doc-1"),),
            gold_evidence_ids=("doc-1",),
        )


def test_dependency_distance_bounded() -> None:
    with pytest.raises(ValueError, match="dependency_distance"):
        DescriptionAxes(
            information_scale_tokens=128,
            dependency_distance_stages=5,
            persistence_span_resets=3,
            action_dependency="strong",
            environment_changes=1,
        )


# --- evaluator-only fields never surface to participants --------------------


def test_stage_view_excludes_evaluator_fields_by_serialization() -> None:
    inst = make_instance()
    hook = ScriptedHook()
    run_lifecycle(inst, hook, ProjectState())
    for view in hook.seen_views:
        serialized = json.dumps(view, default=lambda o: getattr(o, "__dict__", str(o)))
        assert "gold_evidence_ids" not in serialized
        assert "expected_state_delta" not in serialized
        assert not hasattr(view, "gold_evidence_ids")
        assert not hasattr(view, "expected_state_delta")


def test_stage_view_excludes_evaluator_fields_by_construction() -> None:
    inst = make_instance()
    stage = inst.stages[0]
    view = StageView(
        stage_id=stage.stage_id,
        kind=stage.kind,
        prompt_text=stage.prompt_text,
        documents=stage.documents,
        axes=inst.axes,
        remaining_budget=5,
    )
    assert set(view.__dataclass_fields__) == {
        "stage_id",
        "kind",
        "prompt_text",
        "documents",
        "axes",
        "remaining_budget",
    }
    assert "gold_evidence_ids" not in view.__dataclass_fields__


# --- ObjectiveChecker --------------------------------------------------------


def test_objective_checker_exact_match_passes() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={"answer": "x"}))
    result = ObjectiveChecker().check(state, {"r": {"answer": "x"}})
    assert result.passed
    assert result.failures == ()


def test_objective_checker_reports_per_field_failures() -> None:
    state = ProjectState()
    state.apply(
        Action(kind="create_record", record_id="r", fields={"answer": "wrong", "note": "n"})
    )
    result = ObjectiveChecker().check(state, {"r": {"answer": "x", "missing": 1}})
    assert not result.passed
    assert len(result.failures) == 2
    assert any("field 'answer'" in failure for failure in result.failures)
    assert any("field 'missing' missing" in failure for failure in result.failures)


def test_objective_checker_missing_record_is_failure() -> None:
    result = ObjectiveChecker().check(ProjectState(), {"r": {"answer": "x"}})
    assert not result.passed
    assert result.failures == ("record 'r': missing",)


def test_objective_checker_ignores_extra_records_and_fields() -> None:
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="r",
            fields={"answer": "x", "extra": "ignored"},
            provenance=("doc-1",),
        )
    )
    state.apply(Action(kind="create_record", record_id="other", fields={"a": 1}))
    result = ObjectiveChecker().check(state, {"r": {"answer": "x"}})
    assert result.passed


def test_objective_checker_list_vs_tuple_equality() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={"supports": ["doc-1"]}))
    assert ObjectiveChecker().check(state, {"r": {"supports": ("doc-1",)}}).passed
    assert not ObjectiveChecker().check(state, {"r": {"supports": ["doc-9"]}}).passed


# --- sandbox action environment ----------------------------------------------


def test_finalize_requires_provenance() -> None:
    with pytest.raises(ValueError, match="provenance"):
        Action(kind="finalize", record_id="r", fields={})


def test_create_then_duplicate_raises() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={}))
    with pytest.raises(ProjectStateError):
        state.apply(Action(kind="create_record", record_id="r", fields={}))


def test_update_missing_record_raises() -> None:
    with pytest.raises(ProjectStateError):
        ProjectState().apply(Action(kind="update_record", record_id="nope", fields={}))


def test_snapshot_is_deep_copy() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={"supports": ["doc-1"]}))
    snapshot = state.snapshot()
    snapshot["r"]["supports"].append("doc-9")
    assert state.records["r"]["supports"] == ["doc-1"]


# --- runner end-to-end --------------------------------------------------------


def test_run_lifecycle_scripted_hook_end_to_end() -> None:
    inst = make_instance()
    hook = ScriptedHook()
    env = ProjectState()
    record = run_lifecycle(inst, hook, env)
    assert isinstance(record, LifecycleRunRecord)
    assert record.final_check.passed
    assert record.final_check.failures == ()
    assert len(record.stage_records) == 5
    assert record.stage_records[-1].actions_applied == 2
    assert record.cost["wall_seconds"] >= 0.0
    assert env.records["answer_project"]["answer"] == "punk rock"
    assert env.records["answer_project"]["provenance"] == ["doc-1"]


def test_run_lifecycle_failing_state_check() -> None:
    inst = make_instance()
    hook = ScriptedHook(final_fields={"answer": "wrong"})
    record = run_lifecycle(inst, hook, ProjectState())
    assert not record.final_check.passed
    assert any("field 'answer'" in failure for failure in record.final_check.failures)


def test_run_lifecycle_bad_hook_return_raises() -> None:
    class BadHook:
        def on_stage(self, stage: StageView) -> object:
            return "not a StageResponse"

    with pytest.raises(TypeError, match="StageResponse"):
        run_lifecycle(make_instance(), BadHook(), ProjectState())  # type: ignore[arg-type]


def test_provenance_retention_counts_citing_vs_not_citing() -> None:
    inst = make_instance()
    citing = run_lifecycle(inst, ScriptedHook(cite=True), ProjectState())
    bare = run_lifecycle(inst, ScriptedHook(cite=False), ProjectState())
    assert citing.stage_records[0].provenance_retention == 1.0
    assert bare.stage_records[0].provenance_retention == 0.0
    # stages carrying gold evidence all drop to 0.0 without citations
    bare_with_gold = [
        r for r, s in zip(bare.stage_records, inst.stages, strict=True) if s.gold_evidence_ids
    ]
    assert all(r.provenance_retention == 0.0 for r in bare_with_gold)


def test_unknown_cites_are_noted_not_counted() -> None:
    inst = make_instance()

    class PhantomHook(ScriptedHook):
        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.kind == "act_verify":
                return super().on_stage(stage)
            return StageResponse(pack_text="[[doc:doc-99]] phantom cite", actions=())

    record = run_lifecycle(inst, PhantomHook(), ProjectState())
    first = record.stage_records[0]
    assert first.provenance_retention == 0.0
    assert first.notes == ("cited unknown doc ids: ['doc-99']",)


# --- example material ----------------------------------------------------------


def test_build_example_instance_five_stages_and_gold_anchor() -> None:
    inst = build_example_instance(popqa_row())
    assert inst.family == "research-v1"
    assert [stage.kind for stage in inst.stages] == [
        "survey",
        "constraint_injection",
        "delegation",
        "rule_change",
        "act_verify",
    ]
    survey_docs = inst.stages[0].documents
    assert len(survey_docs) == 3  # 2 non-gold + 1 gold
    assert survey_docs[0].doc_id == "doc-33375787-1"
    gold_ids = inst.stages[0].gold_evidence_ids
    assert gold_ids == ("doc-2387652-0",)
    assert all("[[doc:" in document.text for document in survey_docs)
    anchor_title = survey_docs[2].title
    assert anchor_title in inst.stages[1].prompt_text


def test_build_example_instance_expected_state_delta_from_first_answer() -> None:
    inst = build_example_instance(popqa_row())
    delta = inst.stages[4].expected_state_delta
    assert delta is not None
    expected_fields = delta["answer_project"]
    assert isinstance(expected_fields, dict)
    assert expected_fields["answer"] == "punk rock"
    assert expected_fields["supports"] == ["doc-2387652-0"]


def test_build_example_instance_rule_change_marks_non_gold_doc() -> None:
    inst = build_example_instance(popqa_row())
    rule_stage = inst.stages[3]
    doc = rule_stage.documents[0]
    gold_id = inst.stages[0].gold_evidence_ids[0]
    assert doc.doc_id != gold_id
    assert doc.superseded_by == gold_id
    # the gold anchor stays available for the required re-verification
    assert rule_stage.documents[1].doc_id == gold_id


def test_build_example_instance_round_trips() -> None:
    inst = build_example_instance(popqa_row())
    assert canonical_instance_json(inst) == canonical_instance_json(
        load_instance(json.loads(json.dumps(dump_instance(inst))))
    )


def test_build_example_instance_rejects_no_gold_row() -> None:
    row = popqa_row()
    raw_ctxs = row["ctxs"]
    assert isinstance(raw_ctxs, list)
    for ctx in raw_ctxs:
        assert isinstance(ctx, dict)
        ctx["has_answer"] = False
    with pytest.raises(ValueError, match="gold"):
        build_example_instance(row)


def test_example_instance_full_run_through_runner() -> None:
    inst = build_example_instance(popqa_row())
    gold_doc_id = inst.stages[0].gold_evidence_ids[0]
    delta = inst.stages[4].expected_state_delta
    assert delta is not None
    expected_fields = delta["answer_project"]
    assert isinstance(expected_fields, dict)
    fields = dict(expected_fields)

    class ExampleHook:
        def __init__(self) -> None:
            self.views: list[StageView] = []

        def on_stage(self, stage: StageView) -> StageResponse:
            self.views.append(stage)
            if stage.kind != "act_verify":
                return StageResponse(
                    pack_text=f"working notes [[doc:{gold_doc_id}]]",
                    actions=(),
                )
            return StageResponse(
                pack_text=f"final commit [[doc:{gold_doc_id}]]",
                actions=(
                    Action(kind="create_record", record_id="answer_project", fields=fields),
                    Action(
                        kind="finalize",
                        record_id="answer_project",
                        fields={},
                        provenance=(gold_doc_id,),
                    ),
                ),
            )

    env = ProjectState()
    record = run_lifecycle(inst, ExampleHook(), env)
    assert record.final_check.passed
    assert record.stage_records[0].provenance_retention == 1.0
    assert record.cost["wall_seconds"] >= 0.0


# --- canonical run-record serialization ---------------------------------------


def test_run_record_to_dict_canonical() -> None:
    record = run_lifecycle(make_instance(), ScriptedHook(), ProjectState())
    as_dict = record.to_dict()
    encoded = json.dumps(as_dict, sort_keys=True)
    again = json.loads(encoded)
    assert json.dumps(again, sort_keys=True) == encoded
    assert as_dict["final_check"] == {"passed": True, "failures": []}
    assert as_dict["family"] == "research-v1"
    assert len(as_dict["stage_records"]) == 5


def test_check_result_rejects_non_bool_passed() -> None:
    with pytest.raises(TypeError, match="passed"):
        CheckResult(passed=1, failures=())  # type: ignore[arg-type]


# --- alias-aware scoring (root-cause report 2026-09-20) -----------------------


def test_answer_aliases_round_trip() -> None:
    inst = build_example_instance(popqa_row())
    assert inst.answer_aliases == ("punk rock", "punk", "punk music")
    assert inst.stages[4].expected_aliases == ("punk rock", "punk", "punk music")
    payload = json.loads(json.dumps(dump_instance(inst)))
    assert payload["answer_aliases"] == ["punk rock", "punk", "punk music"]
    assert payload["stages"][4]["expected_aliases"] == ["punk rock", "punk", "punk music"]
    reloaded = load_instance(payload)
    assert reloaded == inst
    assert canonical_instance_json(reloaded) == canonical_instance_json(inst)


def test_instance_without_aliases_defaults_empty_and_round_trips() -> None:
    inst = make_instance()
    assert inst.answer_aliases == ()
    assert inst.stages[4].expected_aliases == ()
    payload = dump_instance(inst)
    assert payload["answer_aliases"] == []
    assert load_instance(json.loads(json.dumps(payload))) == inst


def test_load_instance_accepts_legacy_payload_without_alias_keys() -> None:
    payload = dump_instance(make_instance())
    del payload["answer_aliases"]
    for stage in payload["stages"]:
        del stage["expected_aliases"]
    reloaded = load_instance(payload)
    assert reloaded.answer_aliases == ()
    assert all(stage.expected_aliases == () for stage in reloaded.stages)


def test_answer_aliases_must_contain_primary_answer() -> None:
    with pytest.raises(ValueError, match="answer_aliases"):
        replace(make_instance(), answer_aliases=("waltz",))


def test_expected_aliases_rejected_on_non_act_verify_stage() -> None:
    with pytest.raises(ValueError, match="expected_aliases"):
        StageSpec(
            stage_id="s1-survey",
            kind="survey",
            prompt_text="p",
            documents=(make_document("doc-1"),),
            gold_evidence_ids=("doc-1",),
            expected_aliases=("punk",),
        )


def test_alias_hit_true_cases() -> None:
    # case-insensitive match
    assert alias_hit("PUNK ROCK", ("punk rock",))
    # alias contained in a longer evidence phrasing (PopQA 1652383 pattern:
    # the gold passage says "power pop, punk, punk pop" while the primary
    # answer is the KILT normalization "punk rock")
    assert alias_hit("power pop punk punk pop", ("punk rock", "punk", "power pop"))
    # reply contained in an alias (short-form codes, PopQA 4402885 aliases)
    assert alias_hit("POL", ("Poland", "POL", "Republic of Poland", "PL", "Polska"))
    assert alias_hit("republic of poland", ("Poland", "Republic of Poland"))
    # punctuation differences collapse before matching
    assert alias_hit("punk-rock!", ("punk rock",))
    assert alias_hit("power-pop, punk", ("punk",))
    # an alias that normalizes to empty is skipped, not fatal
    assert alias_hit("punk", ("!!", "punk"))


def test_alias_hit_false_cases() -> None:
    assert not alias_hit("", ("punk rock",))
    assert not alias_hit("   ", ("punk",))
    assert not alias_hit("punk", ())
    assert not alias_hit("jazz trio", ("punk rock", "punk"))
    # substring in neither direction (PopQA 3006731 residual class: the
    # reader phrase is a genuine normalization gap outside the alias set)
    assert not alias_hit("comedy horror", ("horror film",))


def test_objective_checker_alias_mode_passes_evidence_phrasing() -> None:
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="answer_project",
            fields={
                "answer": "power pop punk punk pop",
                "supports": ["doc-2387652-0"],
                "status": "final",
            },
        )
    )
    result = ObjectiveChecker().check(
        state,
        {
            "answer_project": {
                "answer": "punk rock",
                "supports": ["doc-2387652-0"],
                "status": "final",
            }
        },
        aliases=("punk rock", "punk", "power pop"),
    )
    assert result.passed
    assert result.failures == ()


def test_objective_checker_alias_mode_keeps_other_fields_exact() -> None:
    state = ProjectState()
    state.apply(
        Action(
            kind="create_record",
            record_id="r",
            fields={"answer": "punk", "supports": ["doc-wrong"]},
        )
    )
    result = ObjectiveChecker().check(
        state,
        {"r": {"answer": "punk rock", "supports": ["doc-1"]}},
        aliases=("punk rock", "punk"),
    )
    assert not result.passed
    assert not any("field 'answer'" in failure for failure in result.failures)
    assert any("field 'supports'" in failure for failure in result.failures)


def test_objective_checker_alias_mode_fails_without_any_alias_hit() -> None:
    state = ProjectState()
    state.apply(Action(kind="create_record", record_id="r", fields={"answer": "jazz"}))
    result = ObjectiveChecker().check(
        state, {"r": {"answer": "punk rock"}}, aliases=("punk rock", "punk")
    )
    assert not result.passed


def test_objective_checker_exact_mode_unchanged_by_alias_addition() -> None:
    state = ProjectState()
    state.apply(
        Action(kind="create_record", record_id="r", fields={"answer": "power pop punk punk pop"})
    )
    expected: dict[str, object] = {"r": {"answer": "punk rock"}}
    assert not ObjectiveChecker().check(state, expected).passed
    assert not ObjectiveChecker().check(state, expected, aliases=None).passed


def test_run_lifecycle_alias_scoring_accepts_evidence_phrasing() -> None:
    inst = build_example_instance(popqa_row())

    class EvidencePhraseHook(ScriptedHook):
        """Commits the verbatim evidence phrasing instead of the primary answer."""

        def on_stage(self, stage: StageView) -> StageResponse:
            if stage.kind == "act_verify":
                return StageResponse(
                    pack_text="final commit [[doc:doc-2387652-0]]",
                    actions=(
                        Action(
                            kind="create_record",
                            record_id="answer_project",
                            fields={
                                "answer": "power pop and punk",
                                "supports": ["doc-2387652-0"],
                                "status": "final",
                            },
                        ),
                        Action(
                            kind="finalize",
                            record_id="answer_project",
                            fields={},
                            provenance=("doc-2387652-0",),
                        ),
                    ),
                )
            return super().on_stage(stage)

    record = run_lifecycle(inst, EvidencePhraseHook(), ProjectState())
    assert record.final_check.passed
    assert record.final_check.failures == ()


def test_stage_view_excludes_expected_aliases() -> None:
    inst = build_example_instance(popqa_row())
    hook = ScriptedHook()
    run_lifecycle(inst, hook, ProjectState())
    for view in hook.seen_views:
        serialized = json.dumps(view, default=lambda o: getattr(o, "__dict__", str(o)))
        assert "expected_aliases" not in serialized
        assert not hasattr(view, "expected_aliases")


# --- gold-passage entailment sanity gate (build-time) -------------------------


def wilcza_row() -> dict[str, object]:
    """The PopQA 4402885 pattern: gold retrieval about a DIFFERENT entity.

    The corpus row's gold passage is the Wilcza Góra disambiguation page, not
    the asked-about Wilcza Jama; this fixture keeps the wrong-entity text but
    drops the incidental parenthetical place-name tokens so the alias-
    containment gate sees the defect (in the literal corpus row the gold text
    mentions "Poland" only inside Voivodeship parentheticals, which the
    substring gate cannot distinguish from support).
    """

    return {
        "id": 4402885,
        "question": "In what country is Wilcza Jama, Sokółka County?",
        "possible_answers": '["Poland", "POL", "Republic of Poland", "PL", "Polska"]',
        "ctxs": [
            {
                "id": "3119263",
                "title": "Wilcza Góra",
                # NB: phrased without words containing the short code aliases
                # ("PL" is a substring of "places") — under plain containment
                # semantics a two-letter alias matches inside unrelated words.
                "text": (
                    "Wilcza Góra\nWilcza Góra may refer to the following localities:\n"
                    "- Wilcza Góra, Kuyavian-Pomeranian Voivodeship\n"
                    "- Wilcza Góra, Masovian Voivodeship\n"
                    "- Wilcza Góra, Silesian Voivodeship"
                ),
                "score": 0.70,
                "has_answer": True,
            },
            {
                "id": "23428304",
                "title": "Wilcza Jama, Sokółka County",
                "text": (
                    "Wilcza Jama is a village in the administrative district of "
                    "Gmina Sokółka, within Sokółka County, Podlaskie Voivodeship, "
                    "in north-eastern Poland, close to the border with Belarus."
                ),
                "score": 0.94,
                "has_answer": False,
            },
        ],
    }


def poet_row() -> dict[str, object]:
    """The PopQA 542248 pattern: gold passage names the answer (alias present)."""

    return {
        "id": 542248,
        "question": "What is Tadhg Dall Ó hUiginn's occupation?",
        "possible_answers": '["poet", "poetess", "bard"]',
        "ctxs": [
            {
                "id": "6010898",
                "title": "Tadhg Dall Ó hUiginn",
                "text": (
                    "Tadhg Dall Ó hUiginn\nTadhg Dall Ó hUiginn (c. 1550 - c.1591) "
                    "was an Irish poet. A well-known late-Gaelic era poet, he was a "
                    "member of a family of professional poets from north Connacht."
                ),
                "score": 0.84,
                "has_answer": True,
            },
            {
                "id": "6010900",
                "title": "Tadhg Dall Ó hUiginn",
                "text": "Later life details and descendants of the same figure.",
                "score": 0.82,
                "has_answer": False,
            },
        ],
    }


def test_gold_entailment_sane_true_when_alias_in_gold_text() -> None:
    assert gold_entailment_sane(poet_row())


def test_gold_entailment_sane_false_when_gold_about_different_entity() -> None:
    assert not gold_entailment_sane(wilcza_row())


def test_gold_entailment_sane_false_for_malformed_rows() -> None:
    empty_gold_text = poet_row()
    empty_gold_text["ctxs"] = [
        {"id": "g", "title": "T", "text": "  ", "score": 0.9, "has_answer": True}
    ]
    assert not gold_entailment_sane(empty_gold_text)

    no_gold = poet_row()
    no_gold["ctxs"] = [dict(poet_row()["ctxs"][1])]  # type: ignore[index]
    assert not gold_entailment_sane(no_gold)

    bad_answers = poet_row()
    bad_answers["possible_answers"] = "not-json"
    assert not gold_entailment_sane(bad_answers)

    missing_ctxs = poet_row()
    del missing_ctxs["ctxs"]
    assert not gold_entailment_sane(missing_ctxs)


def test_gold_entailment_sane_any_gold_ctx_suffices() -> None:
    row = poet_row()
    second_gold = {
        "id": "6010999",
        "title": "Bard",
        "text": "A bard is a professional story teller.",
        "score": 0.80,
        "has_answer": True,
    }
    row["ctxs"] = [
        {
            "id": "6010898-b",
            "title": "Tadhg Dall Ó hUiginn",
            "text": "Biography without naming the occupation.",
            "score": 0.84,
            "has_answer": True,
        },
        second_gold,
    ]
    # "poet" appears in neither gold text, but "bard" does
    assert gold_entailment_sane(row)


def test_build_example_instance_still_constructs_insane_rows() -> None:
    # the gate is a filter for callers, not a constructor exception
    inst = build_example_instance(wilcza_row())
    assert inst.answer_aliases == ("Poland", "POL", "Republic of Poland", "PL", "Polska")
    assert not gold_entailment_sane(wilcza_row())
