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
from typing import Any

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
