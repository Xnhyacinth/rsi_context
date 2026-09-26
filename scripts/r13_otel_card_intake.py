"""Print the pinned-source, source-span-hashed R13 OTel card intake ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rsicontext.lifecycle.material_otel_source_contrast import (
    SOURCE_FILES,
    SOURCE_REVISIONS,
    SOURCE_SHA256,
)
from rsicontext.lifecycle.material_otel_task_cards import (
    SYSTEM_ROW,
    build_otel_dbms_system_card_sessions,
)
from rsicontext.lifecycle.spec import canonical_instance_json

_SPANS = {
    "dbms-system-key": {
        "1.24": [(68, 68, SYSTEM_ROW["1.24"][1])],
        "1.43": [(116, 116, SYSTEM_ROW["1.43"][1])],
    },
    "operation-name-key": {
        "1.24": [(191, 197, "dfb1ab0e8dac6246f3721fb8d77738546ecf822ebb006e29e3a4b912e35655bb")],
        "1.43": [
            (119, 119, "69c6ff4b97c90e224b3ca727ee62034e2c1eb7d932a578bb4fc6834501570ef5"),
            (151, 156, "54771ffbf67e6f2634804daa6c7a55a0576d90dd6c8a02a97574430edbaad2e1"),
        ],
    },
    "database-namespace-key": {
        "1.24": [(191, 195, "5034dd3f804a6f61e52d8b71af8251afa43e3ab189080c47e5d78fe790c2e776")],
        "1.43": [
            (118, 118, "c59604b555370cc89ddf3a879af00391d9ab0c26c94cc3acf3be62e206520d2b"),
            (147, 149, "c9b492cba6bda4b09042d70bf2cfed8797ecab2447de1ef95ff01ef1f15840b5"),
        ],
    },
}
_DECISIONS = {
    "dbms-system-key": {
        "status": "admitted_offline_development_card",
        "reason": (
            "Both versions require the DBMS product field; PostgreSQL client and server agree."
        ),
    },
    "operation-name-key": {
        "status": "deferred_no_matched_required_action",
        "reason": (
            "The 1.24 field is required only when db.statement is not applicable; "
            "the 1.43 field is required when one operation name is readily available. "
            "A matched project request and source oracle need separate adjudication."
        ),
    },
    "database-namespace-key": {
        "status": "deferred_semantic_scope_mismatch",
        "reason": (
            "The 1.24 db.name rule selects a specific database-name layer, whereas "
            "the 1.43 db.namespace rule can combine multiple namespace components. "
            "The current proposal does not freeze an identical semantic target."
        ),
    },
}


def build_ledger(roots: dict[str, Path]) -> dict[str, object]:
    """Fail closed if either pinned source file or nominated line drifts."""

    sources: dict[str, dict[str, str]] = {}
    lines: dict[str, list[bytes]] = {}
    for revision in ("1.24", "1.43"):
        root = roots[revision]
        relative = SOURCE_FILES[revision]
        raw = (root / relative).read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != SOURCE_SHA256[revision]:
            raise ValueError(f"OpenTelemetry {revision} selected source hash drift")
        sources[revision] = {
            "registered_revision": SOURCE_REVISIONS[revision],
            "file": relative,
            "sha256": actual_sha,
        }
        lines[revision] = raw.splitlines(keepends=True)
    cards: dict[str, dict[str, object]] = {}
    for card_id, per_revision in _SPANS.items():
        spans: dict[str, list[dict[str, str | int]]] = {}
        for revision, entries in per_revision.items():
            spans[revision] = []
            for start, end, expected in entries:
                excerpt = b"".join(lines[revision][start - 1 : end])
                actual = hashlib.sha256(excerpt).hexdigest()
                if actual != expected:
                    raise ValueError(f"OpenTelemetry {revision} {card_id} source span drift")
                spans[revision].append({"start_line": start, "end_line": end, "sha256": actual})
        cards[card_id] = {**_DECISIONS[card_id], "spans": spans}
    admitted_materials: dict[str, dict[str, str]] = {}
    for revision in ("1.24", "1.43"):
        first, second = build_otel_dbms_system_card_sessions(roots[revision], revision=revision)
        admitted_materials[revision] = {
            "first_session_sha256": hashlib.sha256(
                canonical_instance_json(first).encode("utf-8")
            ).hexdigest(),
            "second_session_sha256": hashlib.sha256(
                canonical_instance_json(second).encode("utf-8")
            ).hexdigest(),
            "request_sha256": hashlib.sha256(
                second.stages[1].documents[0].text.encode("utf-8")
            ).hexdigest(),
        }
    cards["dbms-system-key"]["materials"] = admitted_materials
    return {
        "schema_version": 1,
        "lineage": "open-telemetry/semantic-conventions",
        "source_revisions": sources,
        "cards": cards,
        "qualification": "development_intake_only; zero qualified independent parents",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--otel124-root", type=Path, required=True)
    parser.add_argument("--otel143-root", type=Path, required=True)
    args = parser.parse_args()
    ledger = build_ledger({"1.24": args.otel124_root, "1.43": args.otel143_root})
    print(json.dumps(ledger, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
