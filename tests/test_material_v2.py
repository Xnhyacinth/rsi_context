"""Tests for the leak-closed research-v2 family (material_v2 + worlds v2).

Implements the dependency-probes record's revision checklist as test
assertions: no answer-bearing evidence after stage 1; stage-5 instruction
never names the answer and carries no documents; stage-4 verification
check discriminates without containing the answer; subject-mention gate;
short-alias word boundaries; worlds discipline preserved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.lifecycle.material_v2 import (
    alias_hit_v2,
    build_research_v2_instance,
    gold_sane_v2,
)
from rsicontext.worlds.constructor_v2 import build_world_v2

_CORPUS = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")


def _row(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": 999999,
        "subj": "Example Band",
        "subj_id": 99999900,
        "s_aliases": '["The Example Band"]',
        "s_wiki_title": "Example Band",
        "question": "What genre is Example Song?",
        "possible_answers": '["punk rock", "punk"]',
        "ctxs": [
            {
                "id": f"gold-{i}",
                "title": f"Gold {i}",
                "text": f"Example Band plays punk rock music on album {i}.",
                "score": 9.0,
                "has_answer": True,
            }
            for i in range(2)
        ]
        + [
            {
                "id": f"noise-{i}",
                "title": f"Noise {i}",
                "text": f"Unrelated passage {i} about places and polar bears.",
                "score": 1.0,
                "has_answer": False,
            }
            for i in range(6)
        ],
    }
    base.update(overrides)
    return base


def test_stage5_has_no_documents_and_never_names_the_answer() -> None:
    instance = build_research_v2_instance(
        _row(), world_id="w-test", variant_label="primary-scope", noise_positions=[2, 3, 4]
    )
    s5 = instance.stages[4]
    assert s5.documents == ()
    for alias in instance.answer_aliases:
        assert alias.lower() not in s5.prompt_text.lower()
    assert "your answer" in s5.prompt_text.lower()


def test_no_answer_bearing_evidence_after_stage1() -> None:
    instance = build_research_v2_instance(
        _row(), world_id="w-test", variant_label="primary-scope", noise_positions=[2, 3, 4]
    )
    for index, stage in enumerate(instance.stages[1:], start=2):
        for doc in stage.documents:
            assert not alias_hit_v2(doc.text, instance.answer_aliases), (
                f"stage {index} leaks answer-bearing document {doc.doc_id}"
            )


def test_stage4_verification_check_discriminates_without_containing() -> None:
    instance = build_research_v2_instance(
        _row(), world_id="w-test", variant_label="primary-scope", noise_positions=[2, 3, 4]
    )
    s4 = instance.stages[3]
    assert "Verification check" in s4.prompt_text
    # The clue carries structural hints but not the answer phrase itself.
    assert "2 word(s)" in s4.prompt_text
    for alias in instance.answer_aliases:
        normalized = alias.lower()
        assert normalized not in s4.prompt_text.lower()


def test_stage1_carries_the_gold_passages() -> None:
    instance = build_research_v2_instance(
        _row(), world_id="w-test", variant_label="primary-scope", noise_positions=[2, 3, 4]
    )
    s1 = instance.stages[0]
    assert any(alias_hit_v2(d.text, instance.answer_aliases) for d in s1.documents)


def test_gold_sane_v2_requires_subject_mention() -> None:
    # The 4402885 pattern: gold text has the answer alias but never the subject.
    wrong_entity = _row()
    wrong_entity["ctxs"] = [
        {
            "id": "mis-retrieved",
            "title": "Wilcza Góra",
            "text": "Wilcza Góra may refer to places in punk rock voivodeships.",
            "score": 9.0,
            "has_answer": True,
        }
    ]
    assert gold_sane_v2(wrong_entity) is False
    assert gold_sane_v2(_row()) is True


def test_alias_hit_v2_word_boundary_for_short_aliases() -> None:
    # 'PL' must not match inside 'places'.
    assert alias_hit_v2("places", ("PL",)) is False
    assert alias_hit_v2("the PL region", ("PL",)) is True
    # A long reply is never contained in a short alias; it matches via the
    # alias's own long forms instead.
    assert alias_hit_v2("Republic of Poland", ("PL", "Republic of Poland")) is True
    # Long aliases keep containment semantics.
    assert alias_hit_v2("power pop punk punk pop", ("punk rock", "punk")) is True


def test_instance_round_trip_and_family_registration() -> None:
    instance = build_research_v2_instance(
        _row(), world_id="w-test", variant_label="primary-scope", noise_positions=[2, 3, 4]
    )
    assert instance.family == "research-v2"
    from rsicontext.lifecycle.spec import dump_instance, load_instance

    dumped = dump_instance(instance)
    assert dumped["family"] == "research-v2"
    assert load_instance(dumped) == instance


def test_build_world_v2_shapes_and_discipline() -> None:
    world = build_world_v2(_row(), "world-999999")
    assert world.spec.template_id == "research-v2"
    assert len(world.instances) >= 2
    for instance in world.instances:
        assert instance.family == "research-v2"
        # The leak closure holds for every variant.
        assert instance.stages[4].documents == ()
        for stage in instance.stages[1:]:
            for doc in stage.documents:
                assert not alias_hit_v2(doc.text, instance.answer_aliases)


@pytest.mark.skipif(not _CORPUS.exists(), reason="corpus not present")
def test_real_corpus_world_construction() -> None:
    seen: set[str] = set()
    with _CORPUS.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = str(row["id"])
            if key in seen:
                continue
            seen.add(key)
            if not gold_sane_v2(row):
                continue
            world = build_world_v2(row, f"world-{key}")
            assert 2 <= len(world.instances) <= 4
            return
    pytest.fail("no gold-sane-v2 row found in corpus")
