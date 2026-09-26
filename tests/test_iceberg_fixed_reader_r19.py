"""One-call/session and fail-closed carry checks for the R19 reader hook."""

from __future__ import annotations

from pathlib import Path

import pytest

from rsicontext.analysis.iceberg_fixed_reader_r19 import (
    RULE_BUNDLES,
    IcebergFixedHook,
    InvalidReaderReply,
    parse_plan,
    parse_rule,
)
from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_iceberg_row_scan import Case, build_iceberg_row_scan_sessions
from rsicontext.lifecycle.session_sequence import run_session_sequence

_SOURCE = Path("/volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake")


def test_parser_rejects_mixed_or_extra_fields() -> None:
    for bundle in RULE_BUNDLES:
        assert parse_rule(bundle) == bundle
        assert parse_rule(bundle + "\n") == bundle
    for invalid in (
        "counter=data; bound=unknown; partition=same-or-global; row=all-equality-ids",
        RULE_BUNDLES[0] + "\nexplanation",
        "counter=data",
        "",
    ):
        with pytest.raises(InvalidReaderReply, match="S1 rule"):
            parse_rule(invalid)
    assert parse_plan("plan=emit-row") == "emit-row"
    assert parse_plan("plan=emit-row\n") == "emit-row"
    assert parse_plan("plan=suppress-row") == "suppress-row"
    with pytest.raises(InvalidReaderReply, match="S2 plan"):
        parse_plan("plan=maybe")


@pytest.mark.parametrize(
    ("case", "bundle", "plan"),
    (
        ("authentic-pack", RULE_BUNDLES[0], "suppress-row"),
        ("constructed-file-sequence", RULE_BUNDLES[1], "emit-row"),
        ("source-free", RULE_BUNDLES[2], "suppress-row"),
        ("identity-only", RULE_BUNDLES[2], "suppress-row"),
    ),
)
def test_two_session_hook_calls_once_and_exposes_only_carry(
    case: Case, bundle: str, plan: str
) -> None:
    if not _SOURCE.is_dir():
        pytest.skip("pinned Iceberg source checkout unavailable")
    pair = build_iceberg_row_scan_sessions(_SOURCE, case=case)
    requests: list[str] = []
    starting_states: list[dict[str, object]] = []

    def responder(prompt: str) -> str:
        requests.append(prompt)
        return bundle if len(requests) == 1 else f"plan={plan}"

    def factory(state: dict[str, object]) -> IcebergFixedHook:
        starting_states.append(dict(state))
        return IcebergFixedHook(
            state,
            responder,
            lambda source: "S1\n" + source,
            lambda request, rule: "S2\n" + rule + "\n" + request,
        )

    env = ProjectState()
    record = run_session_sequence(list(pair), factory, envs=[env, env], max_turns_per_stage=2)
    assert [item.passed for item in record.sessions] == [True, True]
    assert [item.model_calls for item in record.sessions] == [1, 1]
    assert len(requests) == 2
    assert "[[doc:reference-source]]" in requests[0]
    assert "[[doc:reference-source]]" not in requests[1]
    assert requests[1].startswith("S2\n" + bundle + "\n")
    assert starting_states == [{"carry": {}}, {"carry": {"rule": bundle}}]
    assert env.records["row_scan_decision"]["plan"] == plan


def test_mixed_s1_reply_stops_before_s2() -> None:
    if not _SOURCE.is_dir():
        pytest.skip("pinned Iceberg source checkout unavailable")
    pair = build_iceberg_row_scan_sessions(_SOURCE, case="authentic-pack")
    calls: list[str] = []

    def responder(prompt: str) -> str:
        calls.append(prompt)
        return "counter=data; bound=unknown; partition=same-or-global; row=all-equality-ids"

    env = ProjectState()
    with pytest.raises(InvalidReaderReply, match="S1 rule"):
        run_session_sequence(
            list(pair),
            lambda state: IcebergFixedHook(state, responder, lambda text: text, lambda a, b: a + b),
            envs=[env, env],
            max_turns_per_stage=2,
        )
    assert len(calls) == 1
    assert env.records == {}


@pytest.mark.parametrize(
    "case", ("authentic-pack", "constructed-file-sequence", "source-free", "identity-only")
)
@pytest.mark.parametrize("bundle", RULE_BUNDLES)
def test_every_coherent_s1_bundle_reaches_s2(case: Case, bundle: str) -> None:
    if not _SOURCE.is_dir():
        pytest.skip("pinned Iceberg source checkout unavailable")
    pair = build_iceberg_row_scan_sessions(_SOURCE, case=case)
    calls: list[str] = []

    def responder(prompt: str) -> str:
        calls.append(prompt)
        return bundle if len(calls) == 1 else "plan=suppress-row"

    env = ProjectState()
    record = run_session_sequence(
        list(pair),
        lambda state: IcebergFixedHook(
            state, responder, lambda source: "S1\n" + source, lambda request, rule: rule + request
        ),
        envs=[env, env],
        max_turns_per_stage=2,
    )
    assert len(calls) == 2
    assert [item.model_calls for item in record.sessions] == [1, 1]
    assert calls[1].startswith(bundle)
