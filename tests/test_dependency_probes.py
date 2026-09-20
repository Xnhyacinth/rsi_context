"""Tests for the step-3 dependency/counterfactual probe script.

Fast, no network: the loader discipline, the alias-aware matcher, the
fact-swap and irrelevant-perturbation editors, the no-history probe's
oracle hook, and JSON artifact round-trips. Real-reader runs are the
script's job, not the suite's; nothing here needs SIFLOW_API_KEY.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "dependency_probes.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dependency_probes_script_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the dependency-probes script")
    module = importlib.util.module_from_spec(spec)
    # Module-level dataclasses resolve their class module through
    # sys.modules; the script must be registered before exec.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT = _load_script()


def _ctx(ctx_id: str, title: str, text: str, *, gold: bool = False) -> dict[str, Any]:
    return {
        "id": ctx_id,
        "title": title,
        "text": text,
        "score": 0.5,
        "has_answer": gold,
    }


def _row(
    row_id: int = 1,
    question: str = "What genre is Alpha?",
    answers: str = '["alpha rock", "alpha"]',
    ctxs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if ctxs is None:
        ctxs = [
            _ctx("gold", "Gold source", "The verified answer is alpha rock.", gold=True),
            _ctx("noise", "Noise one", "Unrelated filler passage for bulk padding here."),
        ]
    return {
        "id": row_id,
        "question": question,
        "possible_answers": answers,
        "ctxs": ctxs,
    }


# --- loader discipline ----------------------------------------------------------


def test_loader_dedups_by_id_and_keeps_first(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    first = _row(1)
    dupe = _row(1, question="Different question sharing the id")
    second = _row(2, question="What genre is Beta?")
    path.write_text(
        "\n".join(json.dumps(entry) for entry in (first, dupe, second)) + "\n",
        encoding="utf-8",
    )
    rows = SCRIPT.load_rows(path, 8)
    # PopQA packs multiple relations under one entity id; only the first
    # row per id is usable, and order is corpus order.
    assert [row["id"] for row in rows] == [1, 2]
    assert rows[0]["question"] == "What genre is Alpha?"


def test_loader_requires_a_clean_gold_ctx(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    # Gold ctx with an empty text: not usable evidence, row must be skipped.
    bad_gold = _row(
        1,
        ctxs=[
            _ctx("gold-empty", "Gold source", "   ", gold=True),
            _ctx("noise", "Noise one", "Unrelated filler passage for bulk padding here."),
        ],
    )
    good = _row(2)
    path.write_text(json.dumps(bad_gold) + "\n" + json.dumps(good) + "\n", encoding="utf-8")
    assert [row["id"] for row in SCRIPT.load_rows(path, 8)] == [2]


def test_loader_requires_a_clean_non_gold_ctx(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    # Gold-only row: build_example_instance (and the distractor pick) need
    # at least one clean non-gold ctx, so the loader skips it.
    gold_only = _row(
        1,
        ctxs=[
            _ctx("gold", "Gold source", "The verified answer is alpha rock.", gold=True),
            _ctx("noise-empty", "Noise one", ""),
        ],
    )
    good = _row(2)
    path.write_text(json.dumps(gold_only) + "\n" + json.dumps(good) + "\n", encoding="utf-8")
    assert [row["id"] for row in SCRIPT.load_rows(path, 8)] == [2]


def test_loader_stops_at_n(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    rows = [_row(index) for index in range(5)]
    path.write_text("\n".join(json.dumps(entry) for entry in rows) + "\n", encoding="utf-8")
    assert [row["id"] for row in SCRIPT.load_rows(path, 3)] == [0, 1, 2]


# --- alias-aware matching -------------------------------------------------------


def test_alias_hit_matches_any_alias_not_just_the_first() -> None:
    aliases = ("punk rock", "punk", "punk music")
    # The reply is an alias but not possible_answers[0] — the root-cause
    # report's single-alias-pinning failure mode.
    assert SCRIPT.alias_hit("punk", aliases) is True
    # Bidirectional containment: the reply quotes a longer phrase.
    assert SCRIPT.alias_hit("power pop, punk, punk pop era", aliases) is True


def test_alias_hit_rejects_misses_empty_and_insufficient() -> None:
    aliases = ("poet", "poetess", "bard")
    assert SCRIPT.alias_hit("novelist", aliases) is False
    assert SCRIPT.alias_hit("", aliases) is False
    assert SCRIPT.alias_hit("INSUFFICIENT", aliases) is False
    assert SCRIPT.alias_hit("Insufficient.", aliases) is False


def test_alias_hit_normalizes_reasoning_reader_wrappers() -> None:
    aliases = ("Poland", "Polska")
    assert SCRIPT.alias_hit("The answer is Poland.", aliases) is True
    assert SCRIPT.alias_hit("**Poland**", aliases) is True
    assert SCRIPT.alias_hit('"Republic of Poland and Poland alike"', aliases) is True


def test_alias_hit_short_alias_does_not_match_inside_words() -> None:
    # POL (an ISO code alias) must not match inside "polarity"; this is
    # why the matcher is lookaround-based rather than a bare substring.
    assert SCRIPT.alias_hit("polarity", ("POL",)) is False
    assert SCRIPT.alias_hit("POL", ("POL",)) is True


def test_decode_aliases_accepts_json_string_and_list() -> None:
    assert SCRIPT.decode_aliases('["a", "b"]') == ("a", "b")
    assert SCRIPT.decode_aliases(["a", "b"]) == ("a", "b")
    assert SCRIPT.decode_aliases("[]") == ()
    assert SCRIPT.decode_aliases(None) == ()
    assert SCRIPT.decode_aliases('"not a list"') == ()


# --- fact-swap editor -----------------------------------------------------------


def _swap_aliases() -> tuple[str, ...]:
    return ("alpha rock", "alpha")


def test_fact_swap_produces_changed_passage_with_alternate_and_without_original() -> None:
    gold = "The band plays alpha rock on the alpha stage every winter."
    swap = SCRIPT.fact_swap(gold, _swap_aliases())
    assert swap is not None
    edited, replaced, alternate = swap
    # The edited passage changed, contains the alternate value...
    assert edited != gold
    assert SCRIPT._contains(alternate, edited)
    # ...carries no original alias anymore...
    assert not any(SCRIPT._contains(alias, edited) for alias in _swap_aliases())
    # ...and reports which alias was replaced.
    assert replaced in _swap_aliases()


def test_fact_swap_replaces_every_alias_occurrence() -> None:
    gold = "alpha rock began in Bolton; fans of alpha rock spread it."
    swap = SCRIPT.fact_swap(gold, _swap_aliases())
    assert swap is not None
    edited = swap[0]
    assert edited.count(swap[2]) == 2
    assert "alpha" not in edited


def test_fact_swap_returns_none_when_no_alias_in_text() -> None:
    assert SCRIPT.fact_swap("Nothing relevant here at all.", _swap_aliases()) is None


def test_fact_swap_alternate_must_not_collide_with_aliases_or_text() -> None:
    # The only alternates available are 'alpha' (an alias) and 'Bolton'
    # (already in the passage): no collision-free swap exists.
    gold = "The band plays alpha rock in Bolton."
    assert SCRIPT.fact_swap(gold, _swap_aliases(), alternates=["alpha", "Bolton"]) is None


# --- irrelevant-perturbation editor ---------------------------------------------


def test_distractor_pick_skips_alias_sentences_and_short_ones() -> None:
    ctxs = [
        _ctx("gold", "Gold", "The genre is alpha rock.", gold=True),
        _ctx("noise-1", "Noise", "Short. Also short. The cron job failed twice nightly."),
    ]
    picked = SCRIPT.pick_distractor(ctxs, _swap_aliases())
    assert picked == "The cron job failed twice nightly."
    # An alias-carrying sentence is never a distractor (it would be
    # relevant, not irrelevant).
    alias_ctxs = [_ctx("noise-2", "Noise", "They also mention alpha rock loudly today.")]
    assert SCRIPT.pick_distractor(alias_ctxs, _swap_aliases()) is None


def test_append_distractor_appends_and_changes_nothing_else() -> None:
    gold = "The verified answer is alpha rock."
    distractor = "The cron job failed twice nightly."
    perturbed = SCRIPT.append_distractor(gold, distractor)
    assert perturbed == f"{gold}\n\n{distractor}"
    assert perturbed.startswith(gold)
    assert perturbed.endswith(distractor)


def test_to_probe_item_resolves_gold_and_distractor() -> None:
    item = SCRIPT.to_probe_item(_row())
    assert item.id == "1"
    assert item.question == "What genre is Alpha?"
    assert item.aliases == ("alpha rock", "alpha")
    assert "alpha rock" in item.gold_text
    assert item.distractor == "Unrelated filler passage for bulk padding here."


# --- evidence-missing probe (strict gold-drop readout) ---------------------------


def test_evidence_missing_prompt_omits_the_knowledge_permission_sentence() -> None:
    # The probe's condition is longdoc-necessity's (b) MINUS the
    # permission to answer from memory; the prompt must carry only the
    # question and the bare no-evidence statement, and never the words
    # that would license a parametric answer.
    prompts: list[str] = []

    def spy_reader(prompt: str) -> str:
        prompts.append(prompt)
        return "INSUFFICIENT"

    items = [SCRIPT.to_probe_item(_row(1))]
    result = SCRIPT.run_evidence_missing(items, spy_reader)
    assert len(prompts) == 1
    assert prompts[0] == "Question:\nWhat genre is Alpha?\n\nNo evidence is supplied."
    assert "own knowledge" not in prompts[0]
    # Refusal rate metric: the INSUFFICIENT reply is the compliant output.
    assert result["summary"]["refusal_rate"] == 1.0
    assert result["summary"]["parametric_answer_rate"] == 0.0
    assert result["verdict"]["reader_treats_evidence_as_necessary"] is True


def test_evidence_missing_counts_parametric_answers_as_gate_failures() -> None:
    # A reader that answers correctly from memory when the evidence is
    # gone fails this gate: the reply is not a refusal and would have
    # scored a hit had evidence been supplied.
    replies = iter(["alpha rock", "INSUFFICIENT", "Some other guess."])
    items = [SCRIPT.to_probe_item(_row(index)) for index in range(3)]
    result = SCRIPT.run_evidence_missing(items, lambda prompt: next(replies))
    summary = result["summary"]
    assert summary["refusal_rate"] == round(1 / 3, 3)
    assert summary["parametric_answer_rate"] == round(1 / 3, 3)
    assert summary["other_answer_rate"] == round(1 / 3, 3)
    assert result["verdict"]["reader_treats_evidence_as_necessary"] is False
    assert [entry["refused"] for entry in result["per_item"]] == [False, True, False]
    assert [entry["parametric_answer"] for entry in result["per_item"]] == [True, False, False]


def test_evidence_missing_refusal_detection_normalizes_the_reply() -> None:
    # Reasoning-reader wrappers around INSUFFICIENT still count as
    # refusals: the same normalization alias_hit applies.
    replies = iter(["INSUFFICIENT", "Insufficient.", "The answer is INSUFFICIENT."])
    items = [SCRIPT.to_probe_item(_row(index)) for index in range(3)]
    result = SCRIPT.run_evidence_missing(items, lambda prompt: next(replies))
    assert result["summary"]["refusal_rate"] == 1.0


# --- no-history probe (offline: oracle hook + real runner) -----------------------


def test_no_history_probe_runs_offline_and_reports_both_conditions() -> None:
    result = SCRIPT.run_no_history([_row(1), _row(2)])
    assert result["probe"] == "no-history"
    assert result["n"] == 2
    assert result["summary"]["stateful"]["n"] == 2
    assert result["summary"]["empty_state"]["n"] == 2
    # The oracle extractor reads the alias from the stage documents, so
    # both conditions hit in this synthetic case.
    assert result["summary"]["stateful"]["rate"] == 1.0
    assert result["summary"]["empty_state"]["rate"] == 1.0
    # The structural fact the review asked about: does the act_verify
    # prompt text itself carry the answer?
    assert result["per_item"][0]["answer_in_final_prompt"] is True
    # Verdict semantics: memory is NOT necessary when the conditions tie.
    assert result["verdict"]["memory_necessary"] is False


def test_no_history_probe_discriminates_when_evidence_is_survey_stage_only() -> None:
    # A row whose gold passage does not state the alias (the root-cause
    # report's label/evidence-mismatch defect class), but whose SURVEY
    # noise doc mentions it: the survey stage sees all ctxs, so the
    # stateful hook records the alias and commits it at act_verify, while
    # the empty-state hook loses it — cross-stage memory is the only
    # channel to the answer. This is the discriminating case the probe
    # exists to measure.
    mismatched = _row(
        3,
        ctxs=[
            _ctx(
                "gold",
                "Gold source",
                "An unrelated gold passage about weather.",
                gold=True,
            ),
            _ctx("noise", "Noise one", "A quiet mention of alpha rock appears here."),
        ],
    )
    result = SCRIPT.run_no_history([mismatched])
    assert result["summary"]["stateful"]["rate"] == 1.0
    assert result["summary"]["empty_state"]["rate"] == 0.0
    assert result["verdict"]["memory_necessary"] is True
    per_item = result["per_item"][0]
    assert per_item["stateful_answer"] == "alpha rock"
    assert per_item["empty_answer"] == ""
    assert per_item["answer_in_final_prompt"] is True


# --- JSON artifact round-trip ----------------------------------------------------


def test_write_artifact_round_trips_and_refuses_overwrite(tmp_path: Path) -> None:
    payload = {"probe": "fact-swap", "n": 1, "per_item": [{"id": "1"}], "verdict": {"x": 1}}
    target = tmp_path / "artifacts" / "qualification" / "probe-fact-swap-20260920.json"
    SCRIPT.write_artifact(target, payload)
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == payload
    assert target.read_text(encoding="utf-8").endswith("\n")
    with pytest.raises(FileExistsError):
        SCRIPT.write_artifact(target, payload)


def test_write_artifact_creates_parent_directories(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b" / "c" / "probe.json"
    SCRIPT.write_artifact(target, {"probe": "x"})
    assert target.exists()


# --- CLI guards ------------------------------------------------------------------


def test_cli_requires_a_probe_argument() -> None:
    with pytest.raises(SystemExit) as excinfo:
        SCRIPT.main_with_args([])
    assert excinfo.value.code == 2


def test_cli_missing_key_reader_probes_exit_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIFLOW_API_KEY", raising=False)
    assert (
        SCRIPT.main_with_args(
            ["--probe", "fact-swap", "--n", "2", "--output", "/no/such/probe.json"]
        )
        == 2
    )


def test_cli_refuses_an_existing_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SIFLOW_API_KEY", raising=False)
    output = tmp_path / "existing.json"
    output.write_text("immutable\n", encoding="utf-8")
    assert (
        SCRIPT.main_with_args(["--probe", "no-history", "--n", "1", "--output", str(output)]) == 2
    )
    assert output.read_text(encoding="utf-8") == "immutable\n"


def test_cli_no_history_runs_without_a_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SIFLOW_API_KEY", raising=False)
    source = tmp_path / "rows.jsonl"
    source.write_text(json.dumps(_row(1)) + "\n", encoding="utf-8")
    monkeypatch.setattr(SCRIPT, "POPQA_ROWS", source)
    output = tmp_path / "probe-no-history.json"
    assert (
        SCRIPT.main_with_args(["--probe", "no-history", "--n", "1", "--output", str(output)]) == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["probe"] == "no-history"
    assert payload["n"] == 1
    assert payload["summary"]["stateful"]["rate"] == 1.0


# --- lifecycle-fact-swap probe (v2-only, offline: oracle hook + real runner) ------


def _v2_row(
    row_id: int = 1,
    *,
    answers: str = '["alpha rock"]',
    gold_text: str = "Zephyr is a band whose verified genre is alpha rock.",
    noise_text: str = "Unrelated filler passage for bulk padding here.",
) -> dict[str, Any]:
    """A research-v2-usable row: the gold-sane gate needs the question's
    subject (subj / s_wiki_title) mentioned in the gold passage alongside
    an answer alias, and the subject must not itself be an answer alias
    (otherwise the swap's alias-survival guard would always fire)."""

    row = _row(
        row_id,
        question="What genre is Zephyr?",
        answers=answers,
        ctxs=[
            _ctx("gold", "Gold source", gold_text, gold=True),
            _ctx("noise", "Noise one", noise_text),
        ],
    )
    row["subj"] = "Zephyr"
    row["s_wiki_title"] = "Zephyr (band)"
    return row


def _set_active_family(value: str) -> None:
    # SCRIPT's type is ModuleType; mypy cannot see the script's private
    # globals through it, so the family switch goes through one cast.
    cast(Any, SCRIPT)._ACTIVE_FAMILY = value


def _build_v2(row: dict[str, Any]) -> Any:
    _set_active_family("research-v2")
    try:
        return SCRIPT._build_instance(row)
    finally:
        _set_active_family("research-v1")


def test_lifecycle_swap_edits_gold_bodies_and_repoints_stage_five() -> None:
    aliases = ("alpha rock",)
    instance = _build_v2(_v2_row())
    swapped_pair = SCRIPT.swap_lifecycle_instance(instance, aliases, "Luxembourg")
    assert swapped_pair is not None
    swapped, replaced = swapped_pair
    assert replaced == "alpha rock"
    # Stage 1: the gold document's BODY carries the alternate and no
    # original alias; its identity (header line: doc marker + title) and
    # the noise document are untouched — only the fact changed, not the
    # world's document structure.
    baseline_s1, swapped_s1 = instance.stages[0], swapped.stages[0]
    assert swapped_s1.documents[0] == baseline_s1.documents[0]
    header, body = SCRIPT._split_doc_text(swapped_s1.documents[1])
    assert header == SCRIPT._split_doc_text(baseline_s1.documents[1])[0]
    assert SCRIPT._contains("Luxembourg", body)
    assert not SCRIPT._contains("alpha rock", body)
    assert swapped_s1.gold_evidence_ids == baseline_s1.gold_evidence_ids
    # Stages 2-4 (constraint, delegation, rule change) are byte-identical.
    assert swapped.stages[1:4] == instance.stages[1:4]
    # Stage 5 expectations follow the edit: the checker measures
    # follow-the-edit, so committing the edited fact is what passes.
    baseline_act, swapped_act = instance.stages[-1], swapped.stages[-1]
    assert swapped_act.expected_aliases == ("Luxembourg",)
    assert swapped_act.expected_state_delta is not None
    assert swapped_act.expected_state_delta[SCRIPT.RECORD_ID]["answer"] == "Luxembourg"
    assert (
        swapped_act.expected_state_delta[SCRIPT.RECORD_ID]["supports"]
        == baseline_act.expected_state_delta[SCRIPT.RECORD_ID]["supports"]
    )
    assert swapped.answer_norm == "Luxembourg"
    assert swapped.answer_aliases == ("Luxembourg",)


def test_lifecycle_fact_swap_positive_control_follows_the_edit_end_to_end() -> None:
    # The measurement's positive control: an evidence-following participant
    # (the stateful oracle) must commit the alternate under the swapped
    # world AND pass the re-pointed final check, and hit the original under
    # the baseline world. If this cannot pass, the probe measures nothing.
    from rsicontext.lifecycle import ProjectState, run_lifecycle

    row = _v2_row()
    aliases = ("alpha rock",)
    instance = _build_v2(row)
    swapped_pair = SCRIPT.swap_lifecycle_instance(instance, aliases, "Luxembourg")
    assert swapped_pair is not None
    swapped, _ = swapped_pair
    baseline_record = run_lifecycle(
        instance, SCRIPT._OracleStatefulHook({}, aliases, force_empty=False), ProjectState()
    )
    swapped_record = run_lifecycle(
        swapped, SCRIPT._OracleStatefulHook({}, ("Luxembourg",), force_empty=False), ProjectState()
    )
    assert SCRIPT._committed_answer(baseline_record) == "alpha rock"
    assert baseline_record.final_check.passed is True
    assert SCRIPT._committed_answer(swapped_record) == "Luxembourg"
    assert swapped_record.final_check.passed is True

    _set_active_family("research-v2")
    try:
        result = SCRIPT.run_lifecycle_fact_swap([row])
    finally:
        _set_active_family("research-v1")
    assert result["probe"] == "lifecycle-fact-swap"
    per_item = result["per_item"][0]
    assert per_item["replaced"] == "alpha rock"
    assert per_item["alternate"] == "Luxembourg"
    assert per_item["baseline_committed"] == "alpha rock"
    assert per_item["baseline_hit"] is True
    assert per_item["swapped_committed"] == "Luxembourg"
    assert per_item["followed_swap"] is True
    assert result["summary"]["follow_rate"] == 1.0
    assert result["summary"]["baseline_hit_rate"] == 1.0
    assert result["summary"]["uninformative"] == 0
    assert result["verdict"]["fact_followed"] is True
    assert result["verdict"]["baseline_sane"] is True


def test_lifecycle_fact_swap_skips_when_no_whole_phrase_alias_in_gold_bodies() -> None:
    # gold-sane normalizes punctuation, so 'alpha-rock' satisfies the alias
    # containment gate while no whole-phrase alias occurs in the gold BODY
    # — nothing swappable, and the skip must say so (not "alias survives").
    row = _v2_row(gold_text="Zephyr plays a kind of alpha-rock hybrid on stage.")
    _build_v2(row)  # proves the row itself is v2-usable (gold-sane passes)
    _set_active_family("research-v2")
    try:
        result = SCRIPT.run_lifecycle_fact_swap([row])
    finally:
        _set_active_family("research-v1")
    assert result["summary"]["evaluated"] == 0
    assert result["per_item"][0]["skipped"] == "no swappable answer span in stage-1 gold bodies"
    assert result["verdict"]["fact_followed"] is False


def test_lifecycle_fact_swap_skips_when_alias_survives_outside_gold_bodies() -> None:
    # An alias-carrying noise document rides along in the stage-1 survey
    # slice: the counterfactual world would still state the original fact,
    # so the item is ill-formed and must skip rather than measure.
    row = _v2_row(noise_text="Critics compared them to alpha rock bands of the era.")
    _set_active_family("research-v2")
    try:
        result = SCRIPT.run_lifecycle_fact_swap([row])
    finally:
        _set_active_family("research-v1")
    assert result["summary"]["evaluated"] == 0
    assert (
        result["per_item"][0]["skipped"]
        == "original alias survives outside the stage-1 gold bodies"
    )


def test_lifecycle_fact_swap_skips_when_alias_survives_in_a_prompt() -> None:
    # The stage-1 prompt embeds the question: when the question itself
    # carries an answer alias (the label-defect class), the swapped world
    # would still state the original fact in its own instructions — the
    # survival guard must scan prompt texts, not just documents.
    row = _v2_row()
    row["question"] = "What genre is Zephyr's alpha rock sound?"
    _build_v2(row)  # v2-usable: gold-sane never looks at the question
    _set_active_family("research-v2")
    try:
        result = SCRIPT.run_lifecycle_fact_swap([row])
    finally:
        _set_active_family("research-v1")
    assert result["summary"]["evaluated"] == 0
    assert (
        result["per_item"][0]["skipped"]
        == "original alias survives outside the stage-1 gold bodies"
    )


def test_pick_lifecycle_alternate_collision_guards() -> None:
    instance = _build_v2(_v2_row())
    aliases = ("alpha rock",)
    # Equals an alias, contained inside an alias, and already visible to
    # the participant (the question names the subject Zephyr) are all
    # collisions: a committed alternate must be attributable to the edit.
    assert SCRIPT.pick_lifecycle_alternate(instance, aliases, alternates=["alpha rock"]) is None
    assert SCRIPT.pick_lifecycle_alternate(instance, aliases, alternates=["rock"]) is None
    assert SCRIPT.pick_lifecycle_alternate(instance, aliases, alternates=["Zephyr"]) is None
    assert SCRIPT.pick_lifecycle_alternate(instance, aliases, alternates=["Luxembourg"]) == (
        "Luxembourg"
    )
    # The default pool's first collision-free alternate.
    assert SCRIPT.pick_lifecycle_alternate(instance, aliases) == "Luxembourg"


def test_lifecycle_fact_swap_rejects_v1_family() -> None:
    # research-v1's stage-5 leak hands the answer to the participant, so a
    # committed answer cannot be attributed to a stage-1 edit: the probe
    # refuses the family outright instead of measuring noise.
    _set_active_family("research-v1")
    with pytest.raises(ValueError, match="v2-only"):
        SCRIPT.run_lifecycle_fact_swap([_row(1)])


def test_cli_lifecycle_fact_swap_rejects_v1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SIFLOW_API_KEY", raising=False)
    output = tmp_path / "probe-lifecycle-fact-swap.json"
    assert (
        SCRIPT.main_with_args(
            [
                "--probe",
                "lifecycle-fact-swap",
                "--family",
                "research-v1",
                "--n",
                "1",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


def test_cli_lifecycle_fact_swap_runs_without_a_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Reader-free probe: no SIFLOW_API_KEY, full CLI round-trip, artifact
    # parses back with the probe's payload shape.
    monkeypatch.delenv("SIFLOW_API_KEY", raising=False)
    monkeypatch.setattr(SCRIPT, "_ACTIVE_FAMILY", "research-v1")
    source = tmp_path / "rows.jsonl"
    source.write_text(json.dumps(_v2_row(1)) + "\n", encoding="utf-8")
    monkeypatch.setattr(SCRIPT, "POPQA_ROWS", source)
    output = tmp_path / "probe-lifecycle-fact-swap.json"
    assert (
        SCRIPT.main_with_args(
            [
                "--probe",
                "lifecycle-fact-swap",
                "--family",
                "research-v2",
                "--n",
                "1",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["probe"] == "lifecycle-fact-swap"
    assert payload["n"] == 1
    assert payload["summary"]["follow_rate"] == 1.0
    assert payload["verdict"]["fact_followed"] is True
    assert payload["per_item"][0]["swapped_committed"] == "Luxembourg"
    assert "run_date" in payload
