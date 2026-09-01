"""hy3-ioa H0 micro-trial for the open-S seed. Qualification only."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rsicontext.eval import (
    AuditedPolicyBundle,
    EvaluationItem,
    FreshProcessPolicyFactory,
    evaluate,
    exact_match,
)
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint, build_profile_reader
from rsicontext.open_s.contract import OPEN_S_TRACK_ID, repository_open_s_seed, seed_tree_digest
from rsicontext.policy import Artifact, Budget, DocumentChunk

_CANARY_QUERY = "What is the canary code?"
_CANARY_TEXT = "The canary code is amber."
_CANARY_ANSWER = "amber"


def open_s_canary_item() -> EvaluationItem:
    chunk = DocumentChunk("api-canary-1", "api-canary", 0, len(_CANARY_TEXT), _CANARY_TEXT, 6)
    return EvaluationItem(
        item_id="open-s-h0-canary",
        query=_CANARY_QUERY,
        answer=_CANARY_ANSWER,
        artifact=Artifact("api-canary", (chunk,)),
        gold_chunk_ids=frozenset({"api-canary-1"}),
    )


def skipped_hy3_summary(*, reason: str) -> dict[str, Any]:
    return {
        "track": OPEN_S_TRACK_ID,
        "status": reason,
        "claim_boundary": "qualification_only",
        "rsi_launch_eligible": False,
        "discovery_gain": 0,
        "note": "Missing credentials skip the hy3 reader call; local seed tests remain valid.",
    }


def run_open_s_h0_hy3(
    *,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    seed_root: Path | None = None,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Evaluate the byte-identical open-S seed on one public canary item."""

    root = seed_root or repository_open_s_seed()
    digest = seed_tree_digest(root)
    started_at = datetime.now(UTC).isoformat()
    bundle = AuditedPolicyBundle.from_directory(root, entrypoint="seed.py")
    factory = FreshProcessPolicyFactory(bundle, timeout_seconds=10.0)
    item = open_s_canary_item()
    reader = build_profile_reader(profile, endpoint, max_tokens=min(8, profile.max_output_tokens))
    result = evaluate(
        factory,
        (item,),
        reader,
        budget or Budget(max_tokens=32),
        exact_match,
    )
    return {
        "track": OPEN_S_TRACK_ID,
        "status": "completed",
        "claim_boundary": "qualification_only",
        "rsi_launch_eligible": False,
        "seed_digest": digest,
        "profile_id": profile.id,
        "model": profile.model,
        "score": result.score,
        "prediction": result.predictions[0],
        "reader_input_tokens": result.reader_input_tokens[0],
        "reader_output_tokens": result.reader_output_tokens[0],
        "started_at": started_at,
        "note": "H0 canary only. Not researcher discovery and not a paper A2 cell.",
    }


def write_open_s_hy3_summary(output: Path, payload: dict[str, Any]) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    path = output / "summary.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
