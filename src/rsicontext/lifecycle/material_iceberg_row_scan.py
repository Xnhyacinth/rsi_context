"""Unqualified Iceberg two-session row-scan source-contrast candidate.

An exact contiguous slice of the pinned specification is upstream. Table rows, delete files,
review receipts and the alternative sequence rule are constructed. The
alternative is never an authentic Iceberg revision.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from rsicontext.lifecycle.spec import DescriptionAxes, DocumentRef, LifecycleInstance, StageSpec

SOURCE_REVISION = "071d5606bc6199a0be9b3f274ec7fbf111d88821"
SOURCE_RELATIVE = "format/spec.md"
SOURCE_SHA256 = "e68cd90f7e243f33996717f877077e40773a8ffb57978232458b9e5bf2b9c5cb"
LICENSE_SHA256 = "2c0e4b3b8c7a873194c6517058f9a62c59fa00a37d1e24bf80a538e1c885b9b2"
PACK_START = 6608  # inclusive line 90 of format/spec.md
PACK_END = 125333  # inclusive line 1179, half-open byte end
PACK_SHA256 = "51863fe50379b9fe460206cf0ecb58d9c238239058604f87e209497de548dc45"
AUTHENTIC_URL = "https://github.com/apache/iceberg/blob/" + SOURCE_REVISION + "/" + SOURCE_RELATIVE

Case = Literal["authentic-pack", "source-free", "identity-only", "constructed-file-sequence"]
CASES: tuple[Case, ...] = (
    "authentic-pack",
    "source-free",
    "identity-only",
    "constructed-file-sequence",
)
_MARKER = "[[doc:reference-source]]\n"
_WITHHELD = "[SOURCE WITHHELD]"
_IDENTITY = (
    "Corpus: Apache Iceberg table format specification, release 1.9.2.\n"
    f"Path: {SOURCE_RELATIVE}; commit: {SOURCE_REVISION}.\n"
    f"URL: {AUTHENTIC_URL}\n"
    "Selected reference body: contiguous source lines 90-1179.\n"
)
_DATE = "2026-09-27"
_PRIOR = "source_review"
_LATER = "row_scan_decision"
_EMIT = "emit-row"
_SUPPRESS = "suppress-row"
_REVIEW = "review-complete"
_SCAN_REVIEW = "scan-reviewed"

# Every relevant generic older-file cue is made type-specific, and both
# explicit data/file-vs-equality statements change together. The remote
# equality-column value matching rule at line 1136 stays exact in both arms.
# The 90-96 sequence-number overview and 700-703 inheritance remain true in
# both arms: neither defines which counter equality deletes compare.
_EDITS: tuple[tuple[int, int, str, str], ...] = (
    (
        8154,
        8468,
        "3ab428d0c30b10462da01c939aa6b9d01e1982f6421bb0f38a685eb4eaf20598",
        "Like data files, delete files are tracked by partition. In general, a delete file "
        "must be applied according to the delete type's sequence and partition scope; "
        "see [Scan Planning](#scan-planning) for details. Column metrics can be used "
        "to determine whether a delete file's rows overlap the contents of a data "
        "file or a scan range.\n",
    ),
    (
        69879,
        70437,
        "c26e375bb51ac761e673c8f6b9ff95454a1df5ac84244cae2455416db3d3bb9a",
        "The `sequence_number` field represents the data sequence number and must never "
        "change after a file is added to the dataset. The data sequence number represents "
        "the relative age of file content and is used for planning position deletes and "
        "deletion vectors; equality deletes instead compare the file sequence number.\n"
        "The `file_sequence_number` field represents the sequence number of the snapshot "
        "that added the file and must also remain unchanged upon assigning at commit. "
        "It is used to prune equality delete files, even when the data within a file "
        "has an older data sequence number. \n",
    ),
    (
        89745,
        89846,
        "15ca68c6fb5aaf6d62d8af08ea0e55d98dc46cb610ab86bf6ede8b9f3576687d",
        "    - The data file's file sequence number is _strictly less than_ the "
        "equality delete's data sequence number\n",
    ),
    (
        90014,
        90137,
        "f4ff4b27425c449351999c44aa4f30dd95cc9f9129b6e08f9ba093d6593bb4c5",
        "In general, deletes are applied only to data files that precede them under the "
        "applicable delete-type sequence rule and share a partition, except for two "
        "special cases:\n",
    ),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _pinned_source(source_root: Path) -> bytes:
    raw = (source_root / SOURCE_RELATIVE).read_bytes()
    if _sha(raw) != SOURCE_SHA256:
        raise ValueError("pinned Iceberg spec source mismatch")
    if _sha((source_root / "LICENSE").read_bytes()) != LICENSE_SHA256:
        raise ValueError("pinned Iceberg license mismatch")
    if _sha(raw[PACK_START:PACK_END]) != PACK_SHA256:
        raise ValueError("pinned Iceberg contiguous pack mismatch")
    for start, end, expected, _replacement in _EDITS:
        if _sha(raw[start:end]) != expected:
            raise ValueError(f"pinned Iceberg rule span mismatch at {start}:{end}")
    return raw


def _transplant(pack: bytes) -> bytes:
    changed = pack
    for start, end, _expected, replacement in reversed(_EDITS):
        local_start, local_end = start - PACK_START, end - PACK_START
        changed = changed[:local_start] + replacement.encode("utf-8") + changed[local_end:]
    source_cursor = changed_cursor = 0
    for start, end, _expected, replacement in _EDITS:
        local_start, local_end = start - PACK_START, end - PACK_START
        untouched = pack[source_cursor:local_start]
        if changed[changed_cursor : changed_cursor + len(untouched)] != untouched:
            raise ValueError("Iceberg rule transplant changed unregistered bytes")
        source_cursor = local_end
        changed_cursor += len(untouched) + len(replacement.encode("utf-8"))
    if changed[changed_cursor:] != pack[source_cursor:]:
        raise ValueError("Iceberg rule transplant changed unregistered suffix")
    if any(
        phrase in changed
        for phrase in (
            b"The file sequence number can't be used for pruning delete files",
            b"The data file's data sequence number is _strictly less than_",
            b"delete file must be applied to older data files",
            b"deletes are applied only to data files that are older",
        )
    ):
        raise ValueError("Iceberg authentic equality-delete rule remains in constructed pack")
    return changed


def iceberg_source_ledger(source_root: Path) -> dict[str, object]:
    """Evaluator-only source identity and four exact counterfactual edits."""

    raw = _pinned_source(source_root)
    pack = raw[PACK_START:PACK_END]
    changed = _transplant(pack)
    return {
        "revision": SOURCE_REVISION,
        "source_url": AUTHENTIC_URL,
        "source_sha256": _sha(raw),
        "source_bytes": len(raw),
        "pack_byte_interval": [PACK_START, PACK_END],
        "pack_sha256": _sha(raw[PACK_START:PACK_END]),
        "pack_bytes": PACK_END - PACK_START,
        "license_sha256": LICENSE_SHA256,
        "constructed_pack_sha256": _sha(changed),
        "constructed_not_upstream": True,
        "untouched_segments_exact": True,
        "spans": [
            {
                "start_byte": start,
                "end_byte": end,
                "original_sha256": expected,
                "replacement_sha256": _sha(replacement.encode("utf-8")),
                "replacement_bytes": len(replacement.encode("utf-8")),
            }
            for start, end, expected, replacement in _EDITS
        ],
    }


def _constructed(doc_id: str, title: str, body: str) -> DocumentRef:
    return DocumentRef(
        doc_id=doc_id,
        title=title,
        text=f"[[doc:{doc_id}]] {title}\nBENCHMARK SANDBOX ONLY. {body}",
        source_url="benchmark:constructed/table-row-scan-v1",
        retrieved_date=_DATE,
    )


def build_iceberg_row_scan_sessions(
    source_root: Path, *, case: Case
) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build one two-session source arm without model or GPU access."""

    if case not in CASES:
        raise ValueError(f"unknown Iceberg source case: {case}")
    raw = _pinned_source(source_root)
    pack = raw[PACK_START:PACK_END]
    if case == "authentic-pack":
        source_text = _IDENTITY + pack.decode("utf-8")
    elif case == "constructed-file-sequence":
        source_text = _IDENTITY + _transplant(pack).decode("utf-8")
    elif case == "identity-only":
        source_text = _IDENTITY + _WITHHELD
    else:
        source_text = _WITHHELD
    source = DocumentRef(
        doc_id="reference-source",
        title="Reference material",
        text=_MARKER + source_text,
        source_url="benchmark:source-slot/table-row-scan-v1",
        retrieved_date=_DATE,
    )
    request = _constructed(
        "row-scan-request",
        "Constructed row scan request",
        "A format-version 2 table scan reads one existing data file in partition spec 2, "
        "partition region=A. The file contains a row whose field id 1 has value 42. "
        "The data-content sequence number is 7 and the file-addition sequence "
        "number is 12; its status=0 (EXISTING) entry explicitly stores both numbers. "
        "Two equality delete files pass all query and metric filters. E1 has data "
        "sequence number 8, an unpartitioned partition spec, equality_ids=[1], "
        "and delete value 42. E2 has data sequence number 13, partition spec 2 "
        "region=A, equality_ids=[1], and delete value 99. There are no other "
        "delete files or deletion vectors. Decide whether the row with field id 1 "
        "equal to 42 is emitted or suppressed under the supplied reference. Use "
        "plan emit-row or suppress-row. Request a current scan-reviewed receipt "
        "before finalizing row_scan_decision. The receipt confirms local process "
        "review only, not which row result is technically correct.",
    )
    axes = DescriptionAxes(
        # Nominal task size is frozen across arms for StageView equality.
        # Actual final-chat tokens must be measured separately per arm.
        information_scale_tokens=len(pack.decode("utf-8").split()),
        dependency_distance_stages=2,
        persistence_span_resets=1,
        action_dependency="strong",
        environment_changes=0,
    )
    sandbox = {
        "records": [_PRIOR, _LATER],
        "action_kinds": ["create_record", "finalize", "request_verification"],
    }
    first = LifecycleInstance(
        instance_id="research-v5-iceberg-row-scan-s1-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="source-survey",
                kind="survey",
                prompt_text="Review the supplied reference excerpt for a later row-scan decision.",
                documents=(source,),
                gold_evidence_ids=(source.doc_id,),
            ),
            StageSpec(
                stage_id="review-source",
                kind="act_verify",
                prompt_text=(
                    "Request review-complete for plan reviewed, then finalize "
                    "source_review with that environment-issued receipt."
                ),
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_PRIOR: {"status": "final"}},
                commit_precondition={
                    "record_id": _PRIOR,
                    "plan_field": "plan",
                    "legal_plans": ["reviewed"],
                    "plan_requirements": {"reviewed": {"requires_check": _REVIEW}},
                },
                verification_oracle={_REVIEW: {"reviewed": True}},
            ),
            StageSpec(
                stage_id="pause-project",
                kind="session_end",
                prompt_text="Session ends; bounded carry and project records persist.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="source-conditional-row-scan",
        sandbox_spec=sandbox,
    )
    legal = _EMIT if case == "constructed-file-sequence" else _SUPPRESS
    second = LifecycleInstance(
        instance_id="research-v5-iceberg-row-scan-s2-dev-0001",
        family="research-v5",
        stages=(
            StageSpec(
                stage_id="resume-project",
                kind="session_start",
                prompt_text="Resume the same project after a process reset.",
                documents=(),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="row-request-stage",
                kind="constraint_injection",
                prompt_text="Apply the fixed row request to the retained reference.",
                documents=(request,),
                gold_evidence_ids=(),
            ),
            StageSpec(
                stage_id="decide-row-scan",
                kind="act_verify",
                prompt_text="Commit the row result with a current procedural review receipt.",
                documents=(),
                gold_evidence_ids=(),
                expected_state_delta={_LATER: {"status": "final"}},
                commit_precondition={
                    "record_id": _LATER,
                    "prior_finalized_record": _PRIOR,
                    "prior_verification": {
                        "check": _REVIEW,
                        "plan_field": "plan",
                        "allowed_later_plans": {"reviewed": [_EMIT, _SUPPRESS]},
                    },
                    "plan_field": "plan",
                    "legal_plans": [legal],
                    "plan_requirements": {
                        _EMIT: {"requires_check": _SCAN_REVIEW},
                        _SUPPRESS: {"requires_check": _SCAN_REVIEW},
                    },
                },
                verification_oracle={_SCAN_REVIEW: {_EMIT: True, _SUPPRESS: True}},
            ),
            StageSpec(
                stage_id="end-project",
                kind="session_end",
                prompt_text="Session ends.",
                documents=(),
                gold_evidence_ids=(),
            ),
        ),
        axes=axes,
        answer_norm="source-conditional-row-scan",
        sandbox_spec=sandbox,
    )
    return first, second


__all__ = [
    "AUTHENTIC_URL",
    "CASES",
    "LICENSE_SHA256",
    "PACK_END",
    "PACK_SHA256",
    "PACK_START",
    "SOURCE_RELATIVE",
    "SOURCE_REVISION",
    "SOURCE_SHA256",
    "build_iceberg_row_scan_sessions",
    "iceberg_source_ledger",
]
