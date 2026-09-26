#!/usr/bin/env python3
"""Run the OTel 1.24/1.43 fake-worker causal screen without API calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rsicontext.analysis.otel_model_screen import run_screen  # noqa: E402
from rsicontext.experiment.offline_provenance import (  # noqa: E402
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.lifecycle.material_otel_source_contrast import (  # noqa: E402
    SOURCE_FILES,
    SOURCE_REVISIONS,
    SOURCE_SHA256,
    build_otel_source_contrast_sessions,
)

_INPUTS = {
    "1.24": "RSICONTEXT_OTEL124_SOURCE_ROOT",
    "1.43": "RSICONTEXT_OTEL_SOURCE_ROOT",
}
_PRODUCER_FILES = tuple(
    Path(name)
    for name in (
        "src/rsicontext/analysis/otel_model_screen.py",
        "src/rsicontext/experiment/offline_provenance.py",
        "src/rsicontext/lifecycle/otel_model_fixed.py",
        "src/rsicontext/lifecycle/material_otel_source_contrast.py",
        "src/rsicontext/lifecycle/env.py",
        "src/rsicontext/lifecycle/policy.py",
        "src/rsicontext/lifecycle/runner.py",
        "src/rsicontext/lifecycle/session_sequence.py",
        "src/rsicontext/lifecycle/tools.py",
        "scripts/r11_otel_model_screen.py",
        "uv.lock",
        "configs/registry.json",
        "configs/r10_otel_source_contrast_manifest_v1.json",
    )
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _source_identity(revision: str, root: Path) -> dict[str, object]:
    if _git(root, "rev-parse", "HEAD") != SOURCE_REVISIONS[revision]:
        raise RuntimeError(f"OTel {revision}: checkout HEAD differs from pinned revision")
    if _git(root, "status", "--porcelain"):
        raise RuntimeError(f"OTel {revision}: source checkout has local changes")
    symbolic = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if symbolic.returncode != 1:
        raise RuntimeError(f"OTel {revision}: source checkout is not detached")
    relative = SOURCE_FILES[revision]
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    if digest != SOURCE_SHA256[revision]:
        raise RuntimeError(f"OTel {revision}: source bytes differ from pin")
    return {
        "revision": SOURCE_REVISIONS[revision],
        "relative_path": relative,
        "selected_file_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    before = producer_attestation(ROOT, _PRODUCER_FILES, package_names=("rsibench-context",))
    require_clean_producer(before)
    roots = {}
    for revision, variable in _INPUTS.items():
        configured = os.environ.get(variable)
        if not configured:
            parser.error(f"set {variable} to the pinned detached source checkout")
        roots[revision] = Path(configured)
    identities = {revision: _source_identity(revision, root) for revision, root in roots.items()}
    sessions = {
        revision: build_otel_source_contrast_sessions(root, revision=revision)
        for revision, root in roots.items()
    }
    output = run_screen(sessions["1.24"], sessions["1.43"])
    output["source_identities"] = identities
    output["world_sha256"] = {
        revision: [
            hashlib.sha256(
                json.dumps(
                    session.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest()
            for session in pair
        ]
        for revision, pair in sessions.items()
    }
    output["code_identity"] = {"producer_attestation": before}
    after = producer_attestation(ROOT, _PRODUCER_FILES, package_names=("rsibench-context",))
    require_stable_attestation(before, after)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"{output['status']}: {output['screen_case_count']} cases; {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
