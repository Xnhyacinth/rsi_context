from __future__ import annotations

import json
from pathlib import Path

import pytest

from rsicontext.campaign.autonomous_dynamic import DynamicReaderIdentity
from rsicontext.campaign.dynamic_replay import (
    run_dynamic_candidate_replay,
    write_dynamic_candidate_replay,
)
from rsicontext.datasets import generate_dynamic_long_context_dataset
from rsicontext.eval import ReaderOutput
from rsicontext.policy import ContextPack


class GoldEvidenceReader:
    def __init__(
        self,
        *,
        seed: str,
        items_per_profile: int,
        mutate_after_first_call: Path | None = None,
    ) -> None:
        dataset = generate_dynamic_long_context_dataset(
            seed=seed,
            items_per_profile=items_per_profile,
        )
        self.expected = {
            item.evaluation_item.query: (
                item.evaluation_item.answer,
                item.evaluation_item.gold_chunk_ids,
            )
            for item in dataset.visible_items()
        }
        self.mutate_after_first_call = mutate_after_first_call
        self.calls = 0

    def read(self, query: str, context: ContextPack) -> ReaderOutput:
        self.calls += 1
        if self.calls == 1 and self.mutate_after_first_call is not None:
            self.mutate_after_first_call.write_text(
                "from rsicontext.policy import TruncationPolicy\n\n"
                "class Policy(TruncationPolicy):\n"
                "    def __init__(self):\n"
                "        super().__init__('tail')\n",
                encoding="utf-8",
            )
        answer, gold_ids = self.expected[query]
        selected = {span.chunk_id for span in context.spans}
        prediction = answer if gold_ids <= selected else ""
        return ReaderOutput(prediction, context.token_count + 7, int(bool(prediction)))


def _candidate(tmp_path: Path) -> Path:
    candidate = tmp_path / "candidate"
    candidate.mkdir(parents=True)
    (candidate / "policy.py").write_text(
        "from rsicontext.policy import LexicalPolicy\n\nclass Policy(LexicalPolicy):\n    pass\n",
        encoding="utf-8",
    )
    return candidate


def test_replay_freezes_exact_candidate_bytes_and_records_every_item(tmp_path: Path) -> None:
    seed = "dynamic-replay-test"
    candidate = _candidate(tmp_path)
    reader = GoldEvidenceReader(
        seed=seed,
        items_per_profile=1,
        mutate_after_first_call=candidate / "policy.py",
    )

    result = run_dynamic_candidate_replay(
        candidate_policy_directory=candidate,
        reader=reader,
        dataset_seed=seed,
        items_per_profile=1,
        repeats=3,
        reader_identity=DynamicReaderIdentity(
            profile_id="local-reader",
            profile_hash="a" * 64,
            provider="vllm-0.25.1",
            requested_model="Qwen/Qwen3.6-27B",
            provider_revision="b" * 40,
            max_model_len=131_072,
            max_output_tokens=512,
            seed=42,
            temperature=0.0,
            chat_template_enable_thinking=False,
            serving_profile_id="qwen-local",
            serving_profile_hash="c" * 64,
        ),
    )

    assert result.split == "visible"
    assert result.qualification_only is True
    assert len(result.candidate_sha256) == 64
    assert result.reader_calls == 6
    assert result.reader_identity is not None
    assert result.to_dict()["reader_identity"]["serving_profile_hash"] == "c" * 64
    assert reader.calls == 6
    assert len(result.observations) == 3
    assert [observation.repeat_index for observation in result.observations] == [0, 1, 2]
    assert len({observation.score for observation in result.observations}) == 1
    assert len({observation.item_scores for observation in result.observations}) == 1
    assert len({observation.predictions for observation in result.observations}) == 1
    assert all(len(observation.item_scores) == 2 for observation in result.observations)
    assert result.reader_input_tokens == sum(
        observation.reader_input_tokens for observation in result.observations
    )
    assert (
        result.dataset_fingerprint
        == generate_dynamic_long_context_dataset(
            seed=seed,
            items_per_profile=1,
        ).fingerprint
    )


def test_candidate_hash_is_path_and_byte_stable_and_writer_refuses_overwrite(
    tmp_path: Path,
) -> None:
    seed = "stable-replay-hash"
    candidate = _candidate(tmp_path)
    first = run_dynamic_candidate_replay(
        candidate_policy_directory=candidate,
        reader=GoldEvidenceReader(seed=seed, items_per_profile=1),
        dataset_seed=seed,
        items_per_profile=1,
        repeats=1,
    )
    second = run_dynamic_candidate_replay(
        candidate_policy_directory=candidate,
        reader=GoldEvidenceReader(seed=seed, items_per_profile=1),
        dataset_seed=seed,
        items_per_profile=1,
        repeats=1,
    )
    assert first.candidate_sha256 == second.candidate_sha256

    output = tmp_path / "replay.json"
    write_dynamic_candidate_replay(first, output)
    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["candidate_sha256"] == first.candidate_sha256
    assert stored["qualification_only"] is True
    assert "stable-replay-hash" not in json.dumps(stored)
    with pytest.raises(FileExistsError):
        write_dynamic_candidate_replay(first, output)

    (candidate / "policy.py").write_text(
        (candidate / "policy.py").read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    changed = run_dynamic_candidate_replay(
        candidate_policy_directory=candidate,
        reader=GoldEvidenceReader(seed=seed, items_per_profile=1),
        dataset_seed=seed,
        items_per_profile=1,
        repeats=1,
    )
    assert changed.candidate_sha256 != first.candidate_sha256


def test_replay_accepts_and_records_a_seed_entrypoint(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    (candidate / "policy.py").rename(candidate / "seed.py")

    result = run_dynamic_candidate_replay(
        candidate_policy_directory=candidate,
        entrypoint="seed.py",
        reader=GoldEvidenceReader(seed="seed-entrypoint", items_per_profile=1),
        dataset_seed="seed-entrypoint",
        items_per_profile=1,
        repeats=1,
    )

    assert result.entrypoint == "seed.py"
    assert result.candidate_files == ("seed.py",)


@pytest.mark.parametrize("repeats", [0, False])
def test_replay_rejects_invalid_repeat_count_before_reader_calls(
    tmp_path: Path,
    repeats: int,
) -> None:
    reader = GoldEvidenceReader(seed="invalid-repeats", items_per_profile=1)

    with pytest.raises((TypeError, ValueError), match="repeats"):
        run_dynamic_candidate_replay(
            candidate_policy_directory=_candidate(tmp_path),
            reader=reader,
            dataset_seed="invalid-repeats",
            items_per_profile=1,
            repeats=repeats,
        )
    assert reader.calls == 0
