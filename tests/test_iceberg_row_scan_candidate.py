"""Offline source, contrast and action gates for the Iceberg intake world."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_iceberg_row_scan import (
    AUTHENTIC_URL,
    CASES,
    LICENSE_SHA256,
    PACK_END,
    PACK_SHA256,
    PACK_START,
    SOURCE_RELATIVE,
    SOURCE_REVISION,
    SOURCE_SHA256,
    Case,
    build_iceberg_row_scan_sessions,
    iceberg_source_ledger,
)
from rsicontext.lifecycle.runner import StageResponse, StageView
from rsicontext.lifecycle.session_sequence import run_session_sequence
from rsicontext.lifecycle.spec import LifecycleInstance

_SOURCE = Path("/volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake")


@pytest.fixture(scope="module")
def source_root() -> Path:
    if not _SOURCE.is_dir():
        pytest.skip("pinned Iceberg checkout unavailable")
    return _SOURCE


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pair(source_root: Path, case: Case) -> tuple[LifecycleInstance, LifecycleInstance]:
    assert case in CASES
    return build_iceberg_row_scan_sessions(source_root, case=case)


def test_pinned_full_file_pack_and_four_rule_edits(source_root: Path) -> None:
    raw = (source_root / SOURCE_RELATIVE).read_bytes()
    ledger = iceberg_source_ledger(source_root)
    assert ledger["source_url"] == AUTHENTIC_URL
    assert ledger["source_sha256"] == _sha(raw) == SOURCE_SHA256
    assert ledger["license_sha256"] == _sha((source_root / "LICENSE").read_bytes())
    assert ledger["license_sha256"] == LICENSE_SHA256
    assert ledger["pack_byte_interval"] == [PACK_START, PACK_END]
    assert ledger["pack_sha256"] == _sha(raw[PACK_START:PACK_END]) == PACK_SHA256
    assert ledger["pack_bytes"] == 118725
    assert ledger["constructed_not_upstream"] is True
    spans = ledger["spans"]
    assert isinstance(spans, list)
    assert [(item["start_byte"], item["end_byte"]) for item in spans] == [
        (8154, 8468),
        (69879, 70437),
        (89745, 89846),
        (90014, 90137),
    ]
    for item in spans:
        assert item["original_sha256"] == _sha(raw[item["start_byte"] : item["end_byte"]])

    source = _pair(source_root, "authentic-pack")[0].stages[0].documents[0].text
    altered = _pair(source_root, "constructed-file-sequence")[0].stages[0].documents[0].text
    pack = raw[PACK_START:PACK_END].decode()
    assert source.endswith(pack)
    assert _sha(pack.encode()) == PACK_SHA256
    identity_wrapper = source[: -len(pack)]
    assert altered.startswith(identity_wrapper)
    changed_pack = altered[len(identity_wrapper) :].encode()
    assert _sha(changed_pack) == ledger["constructed_pack_sha256"]
    assert b"The file sequence number can't be used for pruning" in pack.encode()
    assert b"The file sequence number can't be used for pruning" not in changed_pack
    assert b"file sequence number is _strictly less than_" in changed_pack
    assert b"data sequence number is _strictly less than_" not in changed_pack
    assert b"A data row is deleted if its values are equal to all delete columns" in changed_pack


def test_non_source_fields_and_receipts_are_matched(source_root: Path) -> None:
    authentic = _pair(source_root, "authentic-pack")
    altered = _pair(source_root, "constructed-file-sequence")
    for left_session, right_session in zip(authentic, altered, strict=True):
        assert left_session.instance_id == right_session.instance_id
        assert left_session.axes == right_session.axes
        assert left_session.sandbox_spec == right_session.sandbox_spec
        for left, right in zip(left_session.stages, right_session.stages, strict=True):
            assert left.stage_id == right.stage_id
            assert left.kind == right.kind
            assert left.prompt_text == right.prompt_text
            assert len(left.documents) == len(right.documents)
            for left_doc, right_doc in zip(left.documents, right.documents, strict=True):
                assert (
                    left_doc.doc_id,
                    left_doc.title,
                    left_doc.source_url,
                    left_doc.retrieved_date,
                ) == (
                    right_doc.doc_id,
                    right_doc.title,
                    right_doc.source_url,
                    right_doc.retrieved_date,
                )
                if left.stage_id != "source-survey":
                    assert left_doc.text == right_doc.text
            if left.stage_id != "decide-row-scan":
                assert left.commit_precondition == right.commit_precondition
                assert left.verification_oracle == right.verification_oracle
    left_gate = authentic[1].stages[2].commit_precondition
    right_gate = altered[1].stages[2].commit_precondition
    assert left_gate is not None and right_gate is not None
    assert left_gate["legal_plans"] == ["suppress-row"]
    assert right_gate["legal_plans"] == ["emit-row"]
    assert authentic[1].stages[2].verification_oracle == altered[1].stages[2].verification_oracle
    assert authentic[1].stages[1].documents == altered[1].stages[1].documents


def test_deidentified_and_identity_only_controls(source_root: Path) -> None:
    full = _pair(source_root, "authentic-pack")
    source_free = _pair(source_root, "source-free")
    identity_only = _pair(source_root, "identity-only")
    pack = (source_root / SOURCE_RELATIVE).read_bytes()[PACK_START:PACK_END].decode()
    full_source = full[0].stages[0].documents[0].text
    free_source = source_free[0].stages[0].documents[0].text
    identity_source = identity_only[0].stages[0].documents[0].text
    assert free_source == "[[doc:reference-source]]\n[SOURCE WITHHELD]"
    assert identity_source == full_source[: -len(pack)] + "[SOURCE WITHHELD]"
    assert full_source.count("[SOURCE WITHHELD]") == 0
    assert identity_source.count("[SOURCE WITHHELD]") == 1
    assert "Iceberg" in identity_source and SOURCE_RELATIVE in identity_source
    assert AUTHENTIC_URL in identity_source and SOURCE_SHA256 not in identity_source
    visible_parts = [stage.prompt_text for session in source_free for stage in session.stages]
    visible_parts.extend(
        item
        for session in source_free
        for stage in session.stages
        for doc in stage.documents
        for item in (doc.title, doc.text, doc.source_url)
    )
    assert "iceberg" not in "\n".join(visible_parts).casefold()
    assert source_free[1].stages[1].documents == identity_only[1].stages[1].documents
    assert source_free[1].stages[1].documents == full[1].stages[1].documents
    assert source_free[1].stages[2].commit_precondition == full[1].stages[2].commit_precondition


class _OfflineReference:
    """Scripted wiring witness; no frozen reader or model is invoked."""

    def __init__(self, state: dict[str, object], fixed_plan: str | None = None) -> None:
        self.state = state
        self.fixed_plan = fixed_plan

    def on_stage(self, stage: StageView) -> StageResponse:
        if stage.stage_id == "source-survey":
            source = stage.documents[0].text
            if self.fixed_plan is not None:
                counter = "fixed"
            elif "file sequence number is _strictly less than_" in source:
                counter = "file"
            elif "data sequence number is _strictly less than_" in source:
                counter = "data"
            else:
                counter = "unknown"
            self.state["carry"] = {"counter": counter}
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
        if stage.stage_id == "row-request-stage":
            facts = stage.documents[0].text
            required = (
                "format-version 2",
                "status=0 (EXISTING)",
                "sequence number is 7",
                "number is 12",
                "sequence number 8",
                "sequence number 13",
                "unpartitioned partition spec",
                "region=A",
                "equality_ids=[1]",
                "delete value 42",
                "delete value 99",
                "pass all query and metric filters",
            )
            carry = self.state.get("carry")
            retained_counter: object = carry.get("counter") if isinstance(carry, dict) else None
            if not all(fragment in facts for fragment in required):
                plan = "unknown"
            elif self.fixed_plan is not None:
                plan = self.fixed_plan
            elif retained_counter == "data":
                plan = "suppress-row"  # E1: 7 < 8, global partition, id 42 matches.
            elif retained_counter == "file":
                plan = "emit-row"  # E1: 12 < 8 false; E2 id 99 mismatches.
            else:
                plan = "unknown"
            self.state["plan"] = plan
            return StageResponse("request facts read")
        if stage.stage_id == "decide-row-scan":
            selected: object = self.state.get("plan")
            if not isinstance(selected, str) or selected == "unknown":
                return StageResponse("no source-supported row choice")
            if not stage.receipts:
                return StageResponse(
                    "request scan review",
                    (
                        Action(
                            "request_verification",
                            "later-review",
                            {"check": "scan-reviewed", "subject": selected},
                        ),
                    ),
                )
            return StageResponse(
                "commit row result",
                (
                    Action("create_record", "row_scan_decision", {"plan": selected}),
                    Action("finalize", "row_scan_decision", {"status": "final"}, ("later-review",)),
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


def test_scripted_reference_and_fixed_default(source_root: Path) -> None:
    authentic = _pair(source_root, "authentic-pack")
    altered = _pair(source_root, "constructed-file-sequence")
    assert _run(authentic) == [True, True]
    assert _run(altered) == [True, True]
    assert _run(_pair(source_root, "source-free")) == [True, False]
    assert _run(_pair(source_root, "identity-only")) == [True, False]
    assert _run(authentic, "suppress-row") == [True, True]
    assert _run(altered, "suppress-row") == [True, False]
    assert _run(authentic, "emit-row") == [True, False]
    assert _run(altered, "emit-row") == [True, True]


def test_source_and_license_drift_fail_before_world_build(
    source_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / SOURCE_RELATIVE
    copy.parent.mkdir(parents=True)
    copy.write_bytes((source_root / SOURCE_RELATIVE).read_bytes() + b"changed")
    (tmp_path / "LICENSE").write_bytes((source_root / "LICENSE").read_bytes())
    with pytest.raises(ValueError, match="source mismatch"):
        _pair(tmp_path, "authentic-pack")
    copy.write_bytes((source_root / SOURCE_RELATIVE).read_bytes())
    (tmp_path / "LICENSE").write_bytes(b"changed")
    with pytest.raises(ValueError, match="license mismatch"):
        _pair(tmp_path, "authentic-pack")


def test_geometry_artifact_binds_current_source_and_request(source_root: Path) -> None:
    path = Path(__file__).resolve().parents[1] / "docs/reviews/r18-iceberg-geometry.json"
    audit = json.loads(path.read_text())
    assert audit["source_git"]["head"] == SOURCE_REVISION
    assert audit["source"]["source_sha256"] == SOURCE_SHA256
    assert audit["source"]["pack_sha256"] == PACK_SHA256
    for case in CASES:
        source = _pair(source_root, case)[0].stages[0].documents[0].text
        row = audit["session_1"][case]
        assert row["source_document_utf8_sha256"] == _sha(source.encode("utf-8"))
        assert row["fits_32k"] is True
    request = _pair(source_root, "authentic-pack")[1].stages[1].documents[0].text
    assert audit["fixed_later_request_utf8_sha256"] == _sha(request.encode("utf-8"))
    assert audit["full_file_survey"]["fits_32k"] is False
