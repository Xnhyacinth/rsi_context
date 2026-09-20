"""Contract tests for independent task worlds (review step 4).

Covers ``src/rsicontext/worlds`` against the review's step-4 deliverable:
worlds of 2-4 instances sharing a document base, dev/holdout splits by
world (never by instance), per-world order randomization that never
reorders stages within an instance, the WorldManifest audit surface, and
the gold-sane gate that must reject the 4402885-style defect row (gold
passage about a different entity). Synthetic PopQA-shaped rows throughout;
the real corpus is exercised only in one skipif-guarded integration test.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from rsicontext.lifecycle.spec import LifecycleInstance, dump_instance, load_instance
from rsicontext.worlds import (
    TaskWorld,
    WorldManifest,
    WorldSpec,
    build_world,
    build_world_manifest,
    gold_sane,
    load_worlds,
    read_manifest,
    write_manifest,
)

_REAL_CORPUS = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
_STAGE_KIND_ORDER = [
    "survey",
    "constraint_injection",
    "delegation",
    "rule_change",
    "act_verify",
]


def synth_row(
    row_id: int,
    *,
    question: str = "What genre is Delta?",
    answers: str = '["delta blues"]',
    gold_text: str = "The Delta record is delta blues; the band Delta played it live.",
    noise_count: int = 8,
) -> dict[str, object]:
    """One synthetic PopQA-shaped row: real-corpus fields, tiny bodies.

    ``noise_count`` non-gold ctxs flank one gold ctx, mirroring the corpus
    shape (one gold passage per entity; retrieval bulk around it).
    """

    ctxs: list[dict[str, object]] = []
    for index in range(noise_count):
        ctxs.append(
            {
                "id": f"{row_id}-noise-{index}",
                "title": f"Noise doc {index} {row_id}",
                "text": f"Unrelated filler passage {index} about topic {index % 3}; no gold span.",
                "score": 0.66 - index / 100,
                "has_answer": False,
            }
        )
    ctxs.insert(
        noise_count // 2,
        {
            "id": f"{row_id}-gold",
            "title": f"Gold source {row_id}",
            "text": gold_text,
            "score": 0.71,
            "has_answer": True,
        },
    )
    return {
        "id": row_id,
        "subj": "Delta",
        "subj_id": row_id * 10_000,
        "s_aliases": "[]",
        "s_wiki_title": "Delta",
        "question": question,
        "possible_answers": answers,
        "ctxs": ctxs,
    }


def defect_row() -> dict[str, object]:
    """Synthetic 4402885-style defect: gold passage about a DIFFERENT entity.

    The real row's gold retrieval is the "Wilcza Góra" disambiguation page
    (a different entity) which incidentally contains the answer string
    ("north-central Poland") but never mentions the asked-about subject
    ("Wilcza Jama, Sokółka County"). Subject mention is absent, so the
    label is not supported by the gold passage.
    """

    ctxs = [
        {
            "id": "3119263",
            "title": "Wilcza Góra",
            "text": (
                "Wilcza Góra may refer to the following places:\n"
                "- Wilcza Góra, Kuyavian-Pomeranian Voivodeship (north-central Poland)\n"
                "- Wilcza Góra, Masovian Voivodeship (east Poland)"
            ),
            "score": 0.7,
            "has_answer": True,
        }
    ]
    ctxs.extend(
        {
            "id": f"noise-{index}",
            "title": f"Noise doc {index}",
            "text": "Unrelated filler about other voivodeships; no answer span.",
            "score": 0.6 - index / 100,
            "has_answer": False,
        }
        for index in range(8)
    )
    return {
        "id": 4402885,
        "subj": "Wilcza Jama, Sokółka County",
        "subj_id": 4402885 * 10_000,
        "s_aliases": "[]",
        "s_wiki_title": "Wilcza Jama, Sokółka County",
        "question": "In what country is Wilcza Jama, Sokółka County?",
        "possible_answers": '["Poland", "POL", "Republic of Poland", "PL", "Polska"]',
        "ctxs": ctxs,
    }


def write_corpus(tmp_path: Path, rows: list[dict[str, object]], *, repeats: int = 1) -> Path:
    """Write a PopQA-shaped JSONL corpus; ``repeats`` mimics adjacent dup lines."""

    path = tmp_path / "popqa.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for _ in range(repeats):
            for row in rows:
                handle.write(json.dumps(row) + "\n")
    return path


# --- world construction --------------------------------------------------------


def test_build_world_yields_multiple_instances_sharing_world_id() -> None:
    world = build_world(synth_row(101), "world-101")
    assert isinstance(world, TaskWorld)
    assert 2 <= len(world.instances) <= 4
    assert all(isinstance(inst, LifecycleInstance) for inst in world.instances)
    assert world.world_id == "world-101"
    assert world.spec.world_id == "world-101"
    # every instance runs the canonical five stages in causal order
    for inst in world.instances:
        assert [stage.kind for stage in inst.stages] == _STAGE_KIND_ORDER
    # the shared world document base: gold evidence is identical across instances
    gold_sets = {tuple(inst.stages[0].gold_evidence_ids) for inst in world.instances}
    assert len(gold_sets) == 1
    assert next(iter(gold_sets))
    # instances differ in aspect (unique instance ids and survey scopes)
    ids = [inst.instance_id for inst in world.instances]
    assert len(ids) == len(set(ids))
    assert len(world.spec.variant_notes) == len(world.instances)


def test_build_world_instances_share_answer_and_differ_in_scope() -> None:
    world = build_world(synth_row(102), "world-102")
    answers = {inst.answer_norm for inst in world.instances}
    assert answers == {"delta blues"}
    # disjoint non-gold survey slices: no noise doc appears in two instances
    noise_doc_sets: list[frozenset[str]] = []
    for inst in world.instances:
        survey = inst.stages[0]
        gold_ids = set(survey.gold_evidence_ids)
        noise_doc_sets.append(frozenset(d.doc_id for d in survey.documents) - gold_ids)
    for i, first in enumerate(noise_doc_sets):
        for second in noise_doc_sets[i + 1 :]:
            assert first & second == frozenset()
    # each instance carries its own supersession target (stage 4)
    targets = {inst.stages[3].documents[0].doc_id for inst in world.instances}
    assert len(targets) == len(world.instances)


def test_build_world_variant_count_scales_with_noise() -> None:
    two = build_world(synth_row(103, noise_count=3), "world-103")
    assert len(two.instances) == 2  # 3 noise docs // 2 = 1 per variant... capped at min 2 variants
    many = build_world(synth_row(104, noise_count=16), "world-104")
    assert len(many.instances) == 4
    # instances stay LifecycleInstance-valid and round-trip through the spec
    for inst in many.instances:
        assert load_instance(json.loads(json.dumps(dump_instance(inst)))) == inst


def test_build_world_rejects_unusable_rows() -> None:
    no_gold = synth_row(105)
    raw_ctxs = no_gold["ctxs"]
    assert isinstance(raw_ctxs, list)
    for ctx in raw_ctxs:
        assert isinstance(ctx, dict)
        ctx["has_answer"] = False
    with pytest.raises(ValueError, match="gold"):
        build_world(no_gold, "world-105")
    no_noise = synth_row(106, noise_count=0)
    with pytest.raises(ValueError, match="non-gold"):
        build_world(no_noise, "world-106")
    no_question = synth_row(107)
    no_question["question"] = "  "
    with pytest.raises(ValueError, match="question"):
        build_world(no_question, "world-107")


def test_world_spec_validation() -> None:
    with pytest.raises(ValueError, match="entity_seed"):
        WorldSpec(world_id="w", template_id="research-v1", entity_seed=(), variant_notes=("a",))
    with pytest.raises(ValueError, match="variant_notes"):
        WorldSpec(world_id="w", template_id="research-v1", entity_seed=("r",), variant_notes=())
    spec = WorldSpec(
        world_id="w", template_id="research-v1", entity_seed=("r",), variant_notes=("a",)
    )
    assert spec.entity_seed == ("r",)


def test_task_world_rejects_wrong_shapes() -> None:
    real = build_world(synth_row(108), "world-108")
    spec = WorldSpec(
        world_id="w", template_id="research-v1", entity_seed=("r",), variant_notes=("a",)
    )
    with pytest.raises(ValueError, match="2-4"):
        TaskWorld(spec=spec, instances=(real.instances[0],))
    # two instances but one variant note: the note-per-instance mismatch
    mismatched = WorldSpec(
        world_id="w",
        template_id="research-v1",
        entity_seed=("r",),
        variant_notes=("a",),
    )
    with pytest.raises(ValueError, match="one note per instance"):
        TaskWorld(spec=mismatched, instances=real.instances[:2])


# --- gold-sane gate -------------------------------------------------------------


def test_gold_sane_accepts_supported_row() -> None:
    assert gold_sane(synth_row(201)) is True


def test_gold_sane_rejects_4402885_style_defect_row() -> None:
    # gold passage about a different entity; contains the answer string but
    # never mentions the asked-about subject
    assert gold_sane(defect_row()) is False


def test_gold_sane_rejects_missing_answer_mention() -> None:
    row = synth_row(
        202,
        gold_text="The Delta record is great; genre discussed elsewhere entirely.",
    )
    assert gold_sane(row) is False


def test_gold_sane_matches_any_alias() -> None:
    row = synth_row(203, answers='["delta blues", "Delta Blues Band style"]')
    row["possible_answers"] = '["zzz unmatchable zzz", "delta blues"]'
    assert gold_sane(row) is True


def test_gold_sane_rejects_when_no_subject_aliases() -> None:
    row = synth_row(204)
    del row["subj"]
    del row["s_wiki_title"]
    row["s_aliases"] = "[]"
    assert gold_sane(row) is False


def test_gold_sane_ignores_short_aliases() -> None:
    # 'PL' (len 2) must not ground the answer half; with no usable alias left
    # the row is rejected
    row = synth_row(205, answers='["PL"]')
    assert gold_sane(row) is False


def test_gold_sane_tolerates_malformed_s_aliases() -> None:
    row = synth_row(206)
    row["s_aliases"] = "not-a-json-list"
    assert gold_sane(row) is True  # subj/s_wiki_title still ground the check


def test_gold_sane_handles_list_possible_answers() -> None:
    row = synth_row(207)
    row["possible_answers"] = ["delta blues"]
    assert gold_sane(row) is True
    row["possible_answers"] = ["", "  "]
    assert gold_sane(row) is False


# --- independence discipline (load_worlds) --------------------------------------


def test_load_worlds_splits_by_world_never_by_instance(tmp_path: Path) -> None:
    rows = [synth_row(301 + i) for i in range(6)]
    path = write_corpus(tmp_path, rows)
    dev, holdout = load_worlds(path, 6, dev_worlds=3, seed=0)
    assert len(dev) == 3 and len(holdout) == 3
    dev_ids = {w.world_id for w in dev}
    holdout_ids = {w.world_id for w in holdout}
    assert dev_ids and holdout_ids
    assert dev_ids & holdout_ids == set()
    # no entity (corpus row id) appears on both sides — dedup by world
    dev_rows = {r for w in dev for r in w.spec.entity_seed}
    holdout_rows = {r for w in holdout for r in w.spec.entity_seed}
    assert dev_rows & holdout_rows == set()
    # every world's instances stay together on one side
    all_ids = dev_ids | holdout_ids
    assert all_ids == {f"world-{301 + i}" for i in range(6)}


def test_load_worlds_dedups_repeated_row_ids(tmp_path: Path) -> None:
    rows = [synth_row(401), synth_row(402)]
    path = write_corpus(tmp_path, rows, repeats=3)  # 3x adjacent dup lines per row
    dev, holdout = load_worlds(path, 2, dev_worlds=1, seed=0)
    assert len(dev) + len(holdout) == 2  # not 6 — each row id counted once


def test_load_worlds_dedups_same_entity_across_row_ids(tmp_path: Path) -> None:
    # two row ids about the SAME entity (subj_id) — only one world
    first = synth_row(501)
    second = synth_row(502)
    second["subj_id"] = first["subj_id"]
    path = write_corpus(tmp_path, [first, synth_row(503), second])
    dev, holdout = load_worlds(path, 2, dev_worlds=1, seed=0)
    all_rows = {r for w in (*dev, *holdout) for r in w.spec.entity_seed}
    assert "501" not in all_rows or "502" not in all_rows
    assert len(dev) + len(holdout) == 2


def test_load_worlds_skips_defect_rows(tmp_path: Path) -> None:
    # the defect row is never selected; with only one gold-sane row left the
    # loader can still form a 2-world corpus once a second sane row is added
    path = write_corpus(tmp_path, [defect_row(), synth_row(601)])
    with pytest.raises(ValueError, match="gold-sane worlds"):
        load_worlds(path, 2, dev_worlds=1, seed=0)
    path2 = write_corpus(tmp_path, [defect_row(), synth_row(601), synth_row(602)])
    dev, holdout = load_worlds(path2, 2, dev_worlds=1, seed=0)
    all_rows = {r for w in (*dev, *holdout) for r in w.spec.entity_seed}
    assert all_rows == {"601", "602"}
    assert "4402885" not in all_rows


def test_load_worlds_order_shuffle_reproducible_and_per_world(tmp_path: Path) -> None:
    rows = [synth_row(701 + i) for i in range(8)]
    path = write_corpus(tmp_path, rows)
    dev_a, holdout_a = load_worlds(path, 8, dev_worlds=3, seed=42)
    dev_b, holdout_b = load_worlds(path, 8, dev_worlds=3, seed=42)
    assert [w.world_id for w in dev_a] == [w.world_id for w in dev_b]
    assert [w.world_id for w in holdout_a] == [w.world_id for w in holdout_b]
    # a different seed yields a (generally) different dev order
    dev_c, _ = load_worlds(path, 8, dev_worlds=3, seed=7)
    assert [w.world_id for w in dev_c] != [w.world_id for w in dev_a]


def test_load_worlds_shuffle_never_reorders_stages_within_instance(tmp_path: Path) -> None:
    rows = [synth_row(801 + i) for i in range(4)]
    path = write_corpus(tmp_path, rows)
    dev, holdout = load_worlds(path, 4, dev_worlds=2, seed=1)
    for world in (*dev, *holdout):
        for inst in world.instances:
            assert [stage.kind for stage in inst.stages] == _STAGE_KIND_ORDER
            # exact causal stage ids, in order
            assert [stage.stage_id for stage in inst.stages] == [
                "s1-survey",
                "s2-constraint",
                "s3-delegation",
                "s4-rule-change",
                "s5-act-verify",
            ]


def test_load_worlds_seed_zero_default_and_params(tmp_path: Path) -> None:
    rows = [synth_row(901 + i) for i in range(3)]
    path = write_corpus(tmp_path, rows)
    a = load_worlds(path, 3, dev_worlds=1)
    b = load_worlds(path, 3, dev_worlds=1, seed=0)
    assert [w.world_id for w in a[0]] == [w.world_id for w in b[0]]


def test_load_worlds_rejects_bad_params(tmp_path: Path) -> None:
    path = write_corpus(tmp_path, [synth_row(1001), synth_row(1002)])
    with pytest.raises(ValueError):
        load_worlds(path, 2, dev_worlds=2)  # no holdout left
    with pytest.raises(ValueError):
        load_worlds(path, 1, dev_worlds=1)  # n_worlds minimum 2
    with pytest.raises(ValueError):
        load_worlds(path, 2, dev_worlds=0)  # dev minimum 1
    with pytest.raises(ValueError, match="gold-sane worlds"):
        load_worlds(path, 99, dev_worlds=1)  # corpus too small


def test_load_worlds_returns_valid_lifecycle_instances(tmp_path: Path) -> None:
    rows = [synth_row(1101 + i) for i in range(3)]
    path = write_corpus(tmp_path, rows)
    dev, holdout = load_worlds(path, 3, dev_worlds=1, seed=3)
    for world in (*dev, *holdout):
        for inst in world.instances:
            # full spec round-trip proves LifecycleInstance-validity
            assert load_instance(json.loads(json.dumps(dump_instance(inst)))) == inst


# --- manifest -------------------------------------------------------------------


def make_split(tmp_path: Path) -> tuple[list[TaskWorld], list[TaskWorld], str]:
    rows = [synth_row(1201 + i) for i in range(4)]
    path = write_corpus(tmp_path, rows)
    return (*load_worlds(path, 4, dev_worlds=2, seed=5), str(path))


def test_manifest_round_trip(tmp_path: Path) -> None:
    dev, holdout, corpus = make_split(tmp_path)
    manifest = build_world_manifest(dev, holdout, corpus_path=corpus, repetitions=5)
    out = tmp_path / "worlds.json"
    write_manifest(out, manifest)
    reloaded = read_manifest(out)
    assert reloaded == manifest
    assert reloaded.to_dict() == manifest.to_dict()
    # sorted-key canonical JSON: re-serializing the parsed payload reproduces
    # the same indented, sorted form (key order is canonical, not incidental)
    text = out.read_text(encoding="utf-8")
    canonical = json.dumps(json.loads(text), sort_keys=True, ensure_ascii=False, indent=2) + "\n"
    assert text == canonical


def test_manifest_fields_report_review_deliverable(tmp_path: Path) -> None:
    dev, holdout, corpus = make_split(tmp_path)
    manifest = build_world_manifest(dev, holdout, corpus_path=corpus, repetitions=3)
    assert manifest.worlds_total == 4
    assert manifest.templates_used == 1  # one family template: research-v1
    assert tuple(manifest.instances_per_world) == tuple(len(w.instances) for w in (*dev, *holdout))
    assert all(2 <= count <= 4 for count in manifest.instances_per_world)
    assert manifest.repetitions == 3
    assert manifest.dev_world_ids == frozenset(w.world_id for w in dev)
    assert manifest.holdout_world_ids == frozenset(w.world_id for w in holdout)
    # data_sources: corpus path first, then every used row id
    assert manifest.data_sources[0] == corpus
    assert sorted(manifest.data_sources[1:]) == sorted(
        {r for w in (*dev, *holdout) for r in w.spec.entity_seed}
    )
    # per-world used_for_development flags agree with the split
    for record in manifest.worlds:
        assert record.used_for_development == (record.world_id in manifest.dev_world_ids)


def test_manifest_from_dict_round_trip_via_json_string(tmp_path: Path) -> None:
    dev, holdout, corpus = make_split(tmp_path)
    manifest = build_world_manifest(dev, holdout, corpus_path=corpus, repetitions=1)
    reloaded = WorldManifest.from_dict(json.loads(json.dumps(manifest.to_dict(), sort_keys=True)))
    assert reloaded == manifest


def test_manifest_rejects_invalid_splits(tmp_path: Path) -> None:
    dev, holdout, corpus = make_split(tmp_path)
    good = build_world_manifest(dev, holdout, corpus_path=corpus, repetitions=1)
    payload = json.loads(json.dumps(good.to_dict()))

    # dev side loses a world id → partition invariant broken
    broken = json.loads(json.dumps(payload))
    broken["dev_world_ids"] = broken["dev_world_ids"][:1]
    with pytest.raises(ValueError, match="partition"):
        WorldManifest.from_dict(broken)

    # a world moves to holdout without flipping its flag → flag mismatch
    moved = json.loads(json.dumps(payload))
    dev_ids = moved["dev_world_ids"]
    moved_id = dev_ids.pop(0)
    moved["holdout_world_ids"].append(moved_id)
    moved["holdout_world_ids"].sort()
    with pytest.raises(ValueError, match="used_for_development"):
        WorldManifest.from_dict(moved)

    # same world on both sides → overlap
    overlapped = json.loads(json.dumps(payload))
    overlapped["holdout_world_ids"].append(overlapped["dev_world_ids"][0])
    overlapped["holdout_world_ids"].sort()
    with pytest.raises(ValueError, match="disjoint"):
        WorldManifest.from_dict(overlapped)

    # a corpus row feeding two worlds → independence broken at the source
    dup_row = json.loads(json.dumps(payload))
    dup_row["worlds"][1]["entity_seed"] = list(dup_row["worlds"][0]["entity_seed"])
    with pytest.raises(ValueError, match="two worlds"):
        WorldManifest.from_dict(dup_row)

    # unknown/extra field → strict schema
    extra = json.loads(json.dumps(payload))
    extra["surprise"] = 1
    with pytest.raises(ValueError, match="fields mismatch"):
        WorldManifest.from_dict(extra)


def test_manifest_rejects_bad_shapes(tmp_path: Path) -> None:
    dev, holdout, corpus = make_split(tmp_path)
    with pytest.raises(ValueError, match="non-empty"):
        build_world_manifest([], holdout, corpus_path=corpus, repetitions=1)
    with pytest.raises(ValueError, match="non-empty"):
        build_world_manifest(dev, [], corpus_path=corpus, repetitions=1)
    with pytest.raises(ValueError, match="repetitions"):
        build_world_manifest(dev, holdout, corpus_path=corpus, repetitions=0)
    # duplicate world ids across sides
    with pytest.raises(ValueError, match="unique"):
        build_world_manifest((*dev, holdout[0]), holdout, corpus_path=corpus, repetitions=1)


# --- real-corpus integration (skipif-guarded) -----------------------------------


@pytest.mark.skipif(not _REAL_CORPUS.exists(), reason="real PopQA KILT corpus not present")
def test_real_corpus_worlds_are_independent_and_gold_sane(tmp_path: Path) -> None:
    dev, holdout = load_worlds(_REAL_CORPUS, 8, dev_worlds=4, seed=11)
    assert len(dev) == 4 and len(holdout) == 4
    dev_rows = {r for w in dev for r in w.spec.entity_seed}
    holdout_rows = {r for w in holdout for r in w.spec.entity_seed}
    assert dev_rows & holdout_rows == set()
    manifest = build_world_manifest(dev, holdout, corpus_path=str(_REAL_CORPUS), repetitions=1)
    assert manifest.worlds_total == 8
    assert all(2 <= len(w.instances) <= 4 for w in (*dev, *holdout))
    out = tmp_path / "real-worlds.json"
    write_manifest(out, manifest)
    assert read_manifest(out) == manifest
    # the defect entity must never be selected by the gold-sane gate
    all_rows = dev_rows | holdout_rows
    assert "4402885" not in all_rows


@pytest.mark.skipif(not _REAL_CORPUS.exists(), reason="real PopQA KILT corpus not present")
def test_real_corpus_rejects_defect_row_by_gold_sane() -> None:
    row: Mapping[str, object] = {}
    with _REAL_CORPUS.open(encoding="utf-8") as handle:
        for line in handle:
            parsed = json.loads(line)
            if str(parsed.get("id")) == "4402885":
                row = parsed
                break
    assert row
    assert gold_sane(row) is False
