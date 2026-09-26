"""Offline construction checks for the unqualified Kafka parent candidate."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_kafka_migration import (
    AUTHENTIC_URL,
    CASES,
    RULE_END,
    RULE_SHA256,
    RULE_START,
    SOURCE_RELATIVE,
    SOURCE_SHA256,
    Case,
    build_kafka_migration_sessions,
    kafka_source_ledger,
)
from rsicontext.lifecycle.runner import StageResponse, StageView
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance, canonical_instance_json

_SOURCE = Path("/volume/pt-dev/qjiu/rsi_context_external/data/apache-kafka-site-kip848-intake")


@pytest.fixture(scope="module")
def source_root() -> Path:
    if not _SOURCE.is_dir():
        pytest.skip("pinned Kafka source checkout unavailable")
    return _SOURCE


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pair(source_root: Path, case: Case) -> tuple[LifecycleInstance, LifecycleInstance]:
    assert case in CASES
    return build_kafka_migration_sessions(source_root, case=case)


def test_pinned_source_and_exact_single_interval(source_root: Path) -> None:
    raw = (source_root / SOURCE_RELATIVE).read_bytes()
    ledger = kafka_source_ledger(source_root)
    assert ledger["source_url"] == AUTHENTIC_URL
    assert ledger["source_sha256"] == _sha(raw) == SOURCE_SHA256
    assert ledger["rule_byte_interval"] == [RULE_START, RULE_END]
    assert ledger["rule_sha256"] == _sha(raw[RULE_START:RULE_END]) == RULE_SHA256
    assert ledger["source_bytes"] == len(raw) == 5375
    assert ledger["untouched_prefix_suffix_exact"] is True
    assert ledger["constructed_not_upstream"] is True

    authentic = _pair(source_root, "full-source")[0].stages[0].documents[0].text
    constructed = _pair(source_root, "constructed-online-rule")[0].stages[0].documents[0].text
    marker = "[[doc:reference-source]]\n"
    assert authentic.startswith(marker) and constructed.startswith(marker)
    changed_raw = constructed[len(marker) :].encode()
    assert authentic[len(marker) :].encode() == raw
    assert changed_raw[:RULE_START] == raw[:RULE_START]
    assert changed_raw[-(len(raw) - RULE_END) :] == raw[RULE_END:]
    assert _sha(changed_raw) == ledger["constructed_source_sha256"]
    assert b"does not embed custom metadata" not in changed_raw
    assert b"Client-side assignors are not supported" in changed_raw


def test_pair_changes_only_source_text_and_private_legal_choice(source_root: Path) -> None:
    full = _pair(source_root, "full-source")
    constructed = _pair(source_root, "constructed-online-rule")
    for original, altered in zip(full, constructed, strict=True):
        assert original.instance_id == altered.instance_id
        assert original.axes == altered.axes
        assert original.sandbox_spec == altered.sandbox_spec
        for left, right in zip(original.stages, altered.stages, strict=True):
            assert left.stage_id == right.stage_id
            assert left.kind == right.kind
            assert left.prompt_text == right.prompt_text
            assert len(left.documents) == len(right.documents)
            for left_doc, right_doc in zip(left.documents, right.documents, strict=True):
                assert left_doc.doc_id == right_doc.doc_id
                assert left_doc.title == right_doc.title
                assert left_doc.source_url == right_doc.source_url
                assert left_doc.retrieved_date == right_doc.retrieved_date
                if left.stage_id != "source-survey":
                    assert left_doc.text == right_doc.text
            if left.stage_id != "decide-migration":
                assert left.commit_precondition == right.commit_precondition
                assert left.verification_oracle == right.verification_oracle
    full_gate = full[1].stages[2].commit_precondition
    changed_gate = constructed[1].stages[2].commit_precondition
    assert full_gate is not None and changed_gate is not None
    assert full_gate["legal_plans"] == ["drain-then-migrate"]
    assert changed_gate["legal_plans"] == ["rolling-migration"]
    assert full[1].stages[2].verification_oracle == constructed[1].stages[2].verification_oracle
    assert canonical_instance_json(full[0]) != canonical_instance_json(constructed[0])


def test_controls_withhold_rule_and_source_free_identity(source_root: Path) -> None:
    withheld = _pair(source_root, "source-free")
    identity = _pair(source_root, "identity-only")
    text_free = withheld[0].stages[0].documents[0].text
    text_identity = identity[0].stages[0].documents[0].text
    assert "Kafka" not in text_free and "KIP" not in text_free
    assert "Classic" not in text_free and "metadata" not in text_free
    visible_parts = [stage.prompt_text for session in withheld for stage in session.stages]
    visible_parts.extend(
        item
        for session in withheld
        for stage in session.stages
        for doc in stage.documents
        for item in (doc.title, doc.text, doc.source_url)
    )
    visible = "\n".join(visible_parts)
    assert all(
        token not in visible.casefold()
        for token in ("kafka", "kip-848", "group.protocol", "classic", "consumer rebalance")
    )
    assert "Kafka 4.0" in text_identity and "KIP-848" in text_identity
    assert SOURCE_RELATIVE in text_identity and AUTHENTIC_URL in text_identity
    assert "does not embed" not in text_identity and "ignores" not in text_identity
    assert withheld[1].stages[1].documents == identity[1].stages[1].documents
    assert (
        withheld[1].stages[1].documents == _pair(source_root, "full-source")[1].stages[1].documents
    )
    assert withheld[1].stages[2].commit_precondition == identity[1].stages[2].commit_precondition
    assert (
        withheld[1].stages[2].commit_precondition
        == _pair(source_root, "full-source")[1].stages[2].commit_precondition
    )


class _OfflineReference:
    """Scripted construction witness; its phrase test is not reader evidence."""

    def __init__(self, state: dict[str, object], fixed_plan: str | None = None) -> None:
        self.state = state
        self.fixed_plan = fixed_plan

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.stage_id == "source-survey":
            source = stage.documents[0].text
            if self.fixed_plan is None:
                if "does not embed custom metadata" in source:
                    plan = "drain-then-migrate"
                elif "online conversion also works" in source.casefold():
                    plan = "rolling-migration"
                else:
                    plan = "unknown"
            else:
                plan = self.fixed_plan
            self.state["carry"] = {"plan": plan}
            return StageResponse("[[doc:reference-source]] reviewed")
        if stage.stage_id == "review-source":
            if not stage.receipts:
                return StageResponse(
                    "request review",
                    (
                        Action(
                            "request_verification",
                            "prior-review",
                            {"check": "review-complete", "subject": "reviewed"},
                        ),
                    ),
                )
            return StageResponse(
                "commit review",
                (
                    Action("create_record", "source_review", {"plan": "reviewed"}),
                    Action("finalize", "source_review", {"status": "final"}, ("prior-review",)),
                ),
            )
        if stage.stage_id == "decide-migration":
            carry = self.state.get("carry")
            selected: object = carry.get("plan") if isinstance(carry, dict) else None
            if not isinstance(selected, str) or selected == "unknown":
                return StageResponse("no source-supported plan")
            if not stage.receipts:
                return StageResponse(
                    "request procedural review",
                    (
                        Action(
                            "request_verification",
                            "later-review",
                            {"check": "plan-reviewed", "subject": selected},
                        ),
                    ),
                )
            return StageResponse(
                "commit plan",
                (
                    Action("create_record", "migration_plan", {"plan": selected}),
                    Action("finalize", "migration_plan", {"status": "final"}, ("later-review",)),
                ),
            )
        return StageResponse("observed")


def _run(
    pair: tuple[LifecycleInstance, LifecycleInstance], fixed_plan: str | None = None
) -> list[bool]:
    env = ProjectState()
    result = run_session_sequence(
        list(pair),
        lambda state: _OfflineReference(state, fixed_plan),
        envs=[env, env],
        max_turns_per_stage=2,
    )
    return [session.passed for session in result.sessions]


def test_offline_reference_and_fixed_source_free_choice(source_root: Path) -> None:
    full = _pair(source_root, "full-source")
    altered = _pair(source_root, "constructed-online-rule")
    assert _run(full) == [True, True]
    assert _run(altered) == [True, True]
    assert _run(_pair(source_root, "source-free")) == [True, False]
    assert _run(_pair(source_root, "identity-only")) == [True, False]
    assert _run(full, "drain-then-migrate") == [True, True]
    assert _run(altered, "drain-then-migrate") == [True, False]
    assert _run(full, "rolling-migration") == [True, False]
    assert _run(altered, "rolling-migration") == [True, True]


def test_source_or_license_drift_rejected_before_world_build(
    source_root: Path, tmp_path: Path
) -> None:
    copied = tmp_path / SOURCE_RELATIVE
    copied.parent.mkdir(parents=True)
    copied.write_bytes((source_root / SOURCE_RELATIVE).read_bytes() + b"drift")
    (tmp_path / "LICENSE").write_bytes((source_root / "LICENSE").read_bytes())
    with pytest.raises(ValueError, match="source mismatch"):
        _pair(tmp_path, "full-source")
    copied.write_bytes((source_root / SOURCE_RELATIVE).read_bytes())
    (tmp_path / "LICENSE").write_bytes(b"wrong license")
    with pytest.raises(ValueError, match="license mismatch"):
        _pair(tmp_path, "full-source")
