"""Command-line entry points for reproducible local qualification runs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from rsicontext.campaign import run_toy_campaign
from rsicontext.experiment import RunSpec
from rsicontext.registry import build_download_plan, load_registry, run_preflight


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rsicontext", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    toy = commands.add_parser("toy-campaign", help="run the deterministic harness qualification")
    toy.add_argument("--output", type=Path, required=True)

    plan = commands.add_parser(
        "registry-plan", help="print acquisition commands without running them"
    )
    plan.add_argument("ids", nargs="*")
    plan.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    plan.add_argument("--destination", type=Path, default=Path.cwd())

    doctor = commands.add_parser("doctor", help="run read-only host and acquisition preflight")
    doctor.add_argument("ids", nargs="*")
    doctor.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    doctor.add_argument("--destination", type=Path, default=Path.cwd())
    doctor.add_argument("--expected-gpus", type=int, default=8)
    doctor.add_argument("--reserve-bytes", type=int, default=0)

    run_id = commands.add_parser("run-id", help="validate a JSON run spec and print its stable id")
    run_id.add_argument("config", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "toy-campaign":
        print(json.dumps(run_toy_campaign(args.output).to_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "registry-plan":
        registry = load_registry(args.registry)
        plan = build_download_plan(registry.select(args.ids or None), args.destination)
        print(json.dumps(plan.as_dict(), indent=2, sort_keys=True))
        return 0
    if args.command == "doctor":
        registry = load_registry(args.registry)
        selected = registry.select(args.ids or None)
        plan = build_download_plan(selected, args.destination)
        report = run_preflight(
            args.destination,
            required_bytes=plan.known_size_bytes + args.reserve_bytes,
            expected_gpus=args.expected_gpus,
            hf_auth_required=any(entry.access == "gated" for entry in selected),
        )
        output = report.as_dict()
        output["unknown_size_count"] = plan.unknown_size_count
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if report.ready else 1
    if args.command == "run-id":
        raw = json.loads(args.config.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("run spec root must be an object")
        print(RunSpec.from_dict(raw).run_id)
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
