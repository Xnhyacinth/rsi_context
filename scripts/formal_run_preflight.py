#!/usr/bin/env python3
"""Emit a non-formal preflight descriptor from live endpoint and Linux observations."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from rsicontext.experiment import (
    ModelContentEvidence,
    RunSpec,
    attest_run,
    fingerprint_model_directory,
    load_api_profiles,
    observe_runtime_endpoint,
    observe_runtime_process,
    write_formal_run_descriptor,
)
from rsicontext.registry import load_registry, load_serving_profiles
from rsicontext.security import observe_linux_isolation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--serving-profile", required=True)
    parser.add_argument("--api-profile", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--runtime-pid", type=int, required=True)
    parser.add_argument("--evaluator-pid", type=int)
    parser.add_argument("--researcher-pid", type=int)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    parser.add_argument("--read-only-mount", action="append", default=[])
    parser.add_argument("--qualification-only", action="store_true")
    parser.add_argument("--registry", type=Path, default=Path("configs/registry.json"))
    parser.add_argument(
        "--serving-profiles",
        type=Path,
        default=Path("configs/serving_profiles.json"),
    )
    parser.add_argument("--api-profiles", type=Path, default=Path("configs/api_profiles.json"))
    parser.add_argument("--output", type=Path, required=True)
    content = parser.add_mutually_exclusive_group(required=True)
    content.add_argument("--model-directory", type=Path)
    content.add_argument("--model-content-sha256")
    parser.add_argument("--model-content-locator")
    return parser


def _load_run_spec(path: Path) -> RunSpec:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load run spec {path}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError("run spec must be a string-keyed JSON object")
    return RunSpec.from_dict(cast(dict[str, Any], raw))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    run_spec = _load_run_spec(args.run_spec)
    registry = load_registry(args.registry)
    serving_profiles = load_serving_profiles(args.serving_profiles, registry)
    serving_profile = serving_profiles.get(args.serving_profile)
    reader_profile = load_api_profiles(args.api_profiles).get(args.api_profile)
    registry_model = registry.select([serving_profile.model_id])[0]
    if args.model_directory is not None:
        model_content = fingerprint_model_directory(args.model_directory)
    else:
        if args.model_content_locator is None:
            raise ValueError("--model-content-locator is required with a declared digest")
        model_content = ModelContentEvidence(
            evidence_source="declared-content-digest",
            sha256=args.model_content_sha256,
            locator=args.model_content_locator,
        )
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    endpoint_observation = observe_runtime_endpoint(args.endpoint, observed_at=timestamp)
    runtime_command = observe_runtime_process(args.runtime_pid, proc_root=args.proc_root)
    isolation = None
    if not args.qualification_only and args.evaluator_pid is None:
        raise ValueError("--evaluator-pid is required for a formal run")
    if args.researcher_pid is not None:
        isolation = observe_linux_isolation(
            researcher_pid=args.researcher_pid,
            evaluator_pid=args.evaluator_pid,
            required_read_only_mounts=tuple(args.read_only_mount),
            observed_at=timestamp,
            proc_root=args.proc_root,
        )
    elif not args.qualification_only:
        raise ValueError("--researcher-pid is required for a formal run")
    descriptor = attest_run(
        run_spec=run_spec,
        serving_profile=serving_profile,
        reader_profile=reader_profile,
        registry_model=registry_model,
        endpoint=args.endpoint,
        endpoint_observation=endpoint_observation,
        model_content=model_content,
        runtime_command=runtime_command,
        isolation=isolation,
        qualification_only=args.qualification_only,
    )
    write_formal_run_descriptor(descriptor, args.output)
    print(
        json.dumps(
            {
                "descriptor_sha256": descriptor.descriptor_sha256,
                "formal_eligible": descriptor.formal_eligible,
                "ineligibility_reasons": descriptor.ineligibility_reasons,
                "output": str(args.output),
                "run_id": descriptor.run_id,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if descriptor.formal_eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
