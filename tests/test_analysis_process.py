from __future__ import annotations

import pytest

from rsicontext.analysis.process import (
    campaign_process_trace,
    changed_paths,
    policy_digest,
    policy_headline,
)


def test_changed_paths_and_digest_detect_policy_edits() -> None:
    seed = {"policy/policy.py": b'MODE = "seed"\n'}
    child = {"policy/policy.py": b'MODE = "lexical"\n', "policy/extra.py": b"X = 1\n"}

    assert changed_paths(seed, child) == ("policy/extra.py", "policy/policy.py")
    assert policy_digest(seed) != policy_digest(child)
    assert policy_digest(seed) == policy_digest(dict(seed))


def test_campaign_process_trace_keeps_h0_peak_and_round_diffs() -> None:
    seed = {"policy/policy.py": b'"""Seed truncation."""\nMODE = "seed"\n'}
    r0 = {"policy/policy.py": b'"""BM25 expansion."""\nMODE = "head"\n'}
    r1 = {"policy/policy.py": b'"""Evidence chain."""\nMODE = "lexical"\n'}

    trace = campaign_process_trace(
        h0_score=0.25,
        round_scores=(0.0, 0.5),
        selected_round=1,
        snapshots=(seed, r0, r1),
    )

    assert trace.scores == (0.25, 0.0, 0.5)
    assert trace.discovery_gain == pytest.approx(0.25)
    assert trace.peak_round == 2
    assert trace.selected_score == pytest.approx(0.5)
    assert trace.last_minus_peak == pytest.approx(0.0)
    assert trace.post_peak_regression is False
    assert trace.round_diffs[0].changed_paths == ("policy/policy.py",)
    assert trace.round_diffs[0].headline == "BM25 expansion."
    assert trace.round_diffs[1].headline == "Evidence chain."
    assert trace.round_diffs[0].policy_sha256 != trace.round_diffs[1].policy_sha256


def test_process_trace_without_h0_starts_at_first_attempt() -> None:
    files = (
        {"policy/policy.py": b"A = 0\n"},
        {"policy/policy.py": b"A = 1\n"},
    )
    trace = campaign_process_trace(
        h0_score=None,
        round_scores=(0.4,),
        selected_round=0,
        snapshots=files,
    )
    assert trace.scores == (0.4,)
    assert trace.selected_score == pytest.approx(0.4)
    assert policy_headline(files[0]) == "A = 0"


def test_process_trace_keeps_h0_when_every_round_is_dropped() -> None:
    trace = campaign_process_trace(
        h0_score=0.4,
        round_scores=(),
        selected_round=None,
        snapshots=({"policy/policy.py": b"A = 0\n"},),
    )
    assert trace.scores == (0.4,)
    assert trace.selected_score == pytest.approx(0.4)
    assert trace.round_diffs == ()


def test_campaign_process_trace_rejects_snapshot_mismatch() -> None:
    with pytest.raises(ValueError, match="seed plus one mapping per round"):
        campaign_process_trace(
            h0_score=0.1,
            round_scores=(0.2,),
            selected_round=0,
            snapshots=({"policy/policy.py": b"A\n"},),
        )
