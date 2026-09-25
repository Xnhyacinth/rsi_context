#!/usr/bin/env python3
"""Run the PostgreSQL 16/17 fake-worker stop-early causal screen.

This command makes no API or GPU calls. It writes public development
evidence only after all eleven structural expectations pass.
"""

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

from rsicontext.analysis.postgresql_model_screen import run_screen  # noqa: E402
from rsicontext.lifecycle.material_postgresql_source_contrast import (  # noqa: E402
    SOURCE_REVISIONS,
    SOURCE_SHA256,
    build_postgresql_source_contrast_sessions,
)

_INPUTS = {
    "16": "RSICONTEXT_POSTGRESQL16_SOURCE_ROOT",
    "17": "RSICONTEXT_POSTGRESQL_SOURCE_ROOT",
}
_CODE_FILES = (
    "src/rsicontext/analysis/postgresql_model_screen.py",
    "src/rsicontext/lifecycle/postgresql_model_fixed.py",
    "src/rsicontext/lifecycle/material_postgresql_source_contrast.py",
    "src/rsicontext/lifecycle/policy.py",
    "src/rsicontext/lifecycle/runner.py",
    "src/rsicontext/lifecycle/session_sequence.py",
    "scripts/r10_pg_model_screen.py",
    "uv.lock",
    "configs/registry.json",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _source_identity(revision: str, root: Path) -> dict[str, object]:
    if _git(root, "rev-parse", "HEAD") != SOURCE_REVISIONS[revision]:
        raise RuntimeError(f"PostgreSQL {revision}: checkout HEAD differs from pinned revision")
    if _git(root, "status", "--porcelain"):
        raise RuntimeError(f"PostgreSQL {revision}: source checkout has local changes")
    symbolic = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if symbolic.returncode != 1:
        raise RuntimeError(f"PostgreSQL {revision}: source checkout is not detached")
    return {
        "revision": SOURCE_REVISIONS[revision],
        "selected_file_sha256": SOURCE_SHA256[revision],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    roots = {}
    for revision, variable in _INPUTS.items():
        configured = os.environ.get(variable)
        if not configured:
            parser.error(f"set {variable} to the pinned detached source checkout")
        roots[revision] = Path(configured)
    identities = {revision: _source_identity(revision, root) for revision, root in roots.items()}
    older = build_postgresql_source_contrast_sessions(roots["16"], revision="16")
    newer = build_postgresql_source_contrast_sessions(roots["17"], revision="17")
    output = run_screen(older, newer)
    output["source_identities"] = identities
    output["world_sha256"] = {
        revision: [
            _sha(
                json.dumps(
                    session.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
            )
            for session in sessions
        ]
        for revision, sessions in (("16", older), ("17", newer))
    }
    output["code_identity"] = {
        "head": _git(ROOT, "rev-parse", "HEAD"),
        "files_sha256": {
            relative: _sha((ROOT / relative).read_bytes()) for relative in _CODE_FILES
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{output['status']}: {output['screen_case_count']} cases; {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
