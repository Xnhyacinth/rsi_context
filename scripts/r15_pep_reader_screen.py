#!/usr/bin/env python3
"""Freeze local PEP reader requests; paid execution awaits R15 prereg gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rsicontext.analysis.chat_geometry import ChatTokenizer  # noqa: E402
from rsicontext.analysis.pep_fixed_reader_r15 import (  # noqa: E402
    build_geometry_report,
    build_pep_cases,
)
from rsicontext.experiment.api import load_api_profiles  # noqa: E402
from rsicontext.experiment.offline_provenance import (  # noqa: E402
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.lifecycle.material_pep_r14 import SOURCE_FILES, SOURCE_REVISION  # noqa: E402
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot  # noqa: E402

_PROFILE_PATH = ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json"
_PROFILE_ID = "siflow-qwen3.6-27b-r15-bc-dev-2048"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    ("tokenizer_config.json", "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02"),
)
_PRODUCER_FILES = tuple(
    Path(name)
    for name in (
        "configs/r15_siflow_fixed_reader_profile_v1.json",
        "configs/r7_pep_source_manifest_v1.json",
        "configs/registry.json",
        "docs/reviews/r15-pep-reader-prereg-20260926.md",
        "scripts/r15_pep_reader_screen.py",
        "src/rsicontext/analysis/chat_geometry.py",
        "src/rsicontext/analysis/otel_siflow_pilot.py",
        "src/rsicontext/analysis/pep_fixed_reader_r15.py",
        "src/rsicontext/eval/openai_compatible.py",
        "src/rsicontext/experiment/api.py",
        "src/rsicontext/experiment/offline_provenance.py",
        "src/rsicontext/lifecycle/env.py",
        "src/rsicontext/lifecycle/material_pep_r14.py",
        "src/rsicontext/lifecycle/pep_model_fixed_r15.py",
        "src/rsicontext/lifecycle/policy.py",
        "src/rsicontext/lifecycle/runner.py",
        "src/rsicontext/lifecycle/session_sequence.py",
        "src/rsicontext/lifecycle/spec.py",
        "src/rsicontext/lifecycle/tools.py",
        "uv.lock",
    )
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


def _source_identity(root: Path) -> dict[str, object]:
    if _git(root, "rev-parse", "HEAD") != SOURCE_REVISION:
        raise ValueError("PEP source revision differs from pin")
    if _git(root, "status", "--porcelain"):
        raise ValueError("PEP source checkout is dirty")
    detached = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if detached.returncode != 1:
        raise ValueError("PEP source checkout must be detached")
    selected: dict[str, str] = {}
    for relative, expected in SOURCE_FILES.values():
        observed = _sha((root / relative).read_bytes())
        if observed != expected:
            raise ValueError(f"PEP source bytes differ from pin: {relative}")
        selected[relative] = observed
    return {"revision": SOURCE_REVISION, "selected_file_sha256": selected}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--tokenizer-path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.execute:
        parser.error(
            "R15 PEP paid execution is closed until preregistration and canaries are frozen"
        )
    if args.source_root is None or args.tokenizer_path is None or args.output is None:
        parser.error("--dry-run requires --source-root, --tokenizer-path, and --output")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    tokenizer_hash = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    try:
        import jinja2  # type: ignore[import-not-found]
        import tokenizers  # type: ignore[import-not-found]
        import transformers  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pinned optional tokenizer runtime is required") from exc
    if (
        transformers.__version__ != "5.15.0"
        or tokenizers.__version__ != "0.22.2"
        or jinja2.__version__ != "3.1.6"
    ):
        raise RuntimeError("tokenizer runtime differs from pinned R15 geometry")
    before = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_clean_producer(before)
    source_identity = _source_identity(args.source_root)
    profile = load_api_profiles(_PROFILE_PATH).get(_PROFILE_ID)
    tokenizer = cast(
        ChatTokenizer,
        transformers.AutoTokenizer.from_pretrained(
            str(args.tokenizer_path), local_files_only=True  # nosec B615
        ),
    )
    cases = build_pep_cases(args.source_root)
    report = build_geometry_report(tokenizer, profile, cases)
    report.update(
        source_identity=source_identity,
        tokenizer={
            "revision": "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b",
            "manifest_sha256": tokenizer_hash,
            "runtime": "transformers==5.15.0 tokenizers==0.22.2 jinja2==3.1.6",
        },
        profile_file_sha256=_sha(_PROFILE_PATH.read_bytes()),
        producer_attestation=before,
    )
    after = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_stable_attestation(before, after)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    registered = report["registered_requests"]
    if not isinstance(registered, dict):
        raise TypeError("geometry report lacks registered requests")
    print(
        json.dumps(
            {
                "status": "offline-geometry-only",
                "output": str(args.output),
                "sha256": _sha(args.output.read_bytes()),
                "registered_cases": len(cases),
                "registered_unique_requests": len(registered),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
