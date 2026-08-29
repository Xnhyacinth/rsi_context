#!/usr/bin/env python3
"""Build the reviewed private HF schema-smoke package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rsicontext.release import build_dataset_release


def parse_args() -> argparse.Namespace:
    """Parse release builder arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=Path("configs/hf_dataset_release.json"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/hf-release/rsibench-context-prepared-visible"),
    )
    parser.add_argument("--source-revision", required=True)
    return parser.parse_args()


def main() -> int:
    """Build the package and print its non-secret manifest."""
    args = parse_args()
    manifest = build_dataset_release(
        spec_path=args.spec,
        repo_root=args.repo_root,
        output_dir=args.output,
        source_revision=args.source_revision,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
