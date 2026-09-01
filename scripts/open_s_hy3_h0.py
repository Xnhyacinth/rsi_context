#!/usr/bin/env python3
"""One-item hy3 H0 canary for the open-S seed. Qualification only, not A2."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rsicontext.experiment.api import load_api_profiles, resolve_api_endpoint
from rsicontext.open_s.hy3 import run_open_s_h0_hy3, skipped_hy3_summary, write_open_s_hy3_summary

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--profiles",
        type=Path,
        default=_REPO_ROOT / "configs" / "api_profiles.json",
    )
    parser.add_argument("--profile", default="tencent-copilot-hy3-ioa")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not os.environ.get("COPILOT_API_KEY") or not os.environ.get("COPILOT_BASE_URL"):
        write_open_s_hy3_summary(args.output, skipped_hy3_summary(reason="credentials_missing"))
        return 0
    profiles = load_api_profiles(args.profiles)
    profile = profiles.get(args.profile)
    endpoint = resolve_api_endpoint(profile)
    payload = run_open_s_h0_hy3(profile=profile, endpoint=endpoint)
    write_open_s_hy3_summary(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
