#!/usr/bin/env python3
"""Dry-run the pinned KEP fixed reader; paid execution remains closed."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rsicontext.analysis.chat_geometry import ChatTokenizer  # noqa: E402
from rsicontext.analysis.k8s_fixed_reader_r15 import (  # noqa: E402
    PROFILE_ID,
    PROFILE_SHA256,
    enumerate_allowed_prompt_geometry,
    make_synthetic_transport,
    require_paid_gate,
    run_offline_screen,
)
from rsicontext.experiment.api import (  # noqa: E402
    ResolvedAPIEndpoint,
    load_api_profiles,
)
from rsicontext.experiment.offline_provenance import (  # noqa: E402
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.lifecycle.material_k8s_r14 import (  # noqa: E402
    SOURCE_REVISION,
    build_k8s_resource_order_sessions,
)
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot  # noqa: E402

_PROFILE_PATH = ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    ("tokenizer_config.json", "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02"),
)
_PRODUCER_FILES = tuple(
    Path(name)
    for name in (
        "configs/r15_siflow_fixed_reader_profile_v1.json",
        "configs/r4_parent_source_manifest_v1.json",
        "configs/registry.json",
        "docs/reviews/r15-k8s-reader-prereg-20260926.md",
        "scripts/r15_k8s_reader_screen.py",
        "src/rsicontext/analysis/chat_geometry.py",
        "src/rsicontext/analysis/k8s_fixed_reader_r15.py",
        "src/rsicontext/analysis/otel_siflow_pilot.py",
        "src/rsicontext/eval/openai_compatible.py",
        "src/rsicontext/experiment/api.py",
        "src/rsicontext/experiment/offline_provenance.py",
        "src/rsicontext/lifecycle/env.py",
        "src/rsicontext/lifecycle/k8s_model_fixed_r15.py",
        "src/rsicontext/lifecycle/material_k8s_r14.py",
        "src/rsicontext/lifecycle/policy.py",
        "src/rsicontext/lifecycle/runner.py",
        "src/rsicontext/lifecycle/session_sequence.py",
        "src/rsicontext/lifecycle/tools.py",
        "src/rsicontext/registry/tokenizer.py",
        "uv.lock",
    )
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source_identity(root: Path) -> dict[str, str]:
    def git(*args: str) -> str:
        return subprocess.run(  # nosec B603, B607
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    revision = git("rev-parse", "HEAD")
    if revision != SOURCE_REVISION or git("status", "--porcelain"):
        raise RuntimeError("KEP source revision or cleanliness differs from registry")
    detached = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if detached.returncode != 1:
        raise RuntimeError("KEP source checkout must be detached")
    build_k8s_resource_order_sessions(root)
    return {"revision": revision, "checkout": "detached-clean"}


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
        try:
            require_paid_gate()
        except RuntimeError as exc:
            print(
                json.dumps({"live_ready": False, "status": "refused", "cause": str(exc)}),
                file=sys.stderr,
            )
            return 2
        raise AssertionError("paid gate returned unexpectedly")
    if args.source_root is None or args.tokenizer_path is None or args.output is None:
        parser.error("--dry-run requires --source-root, --tokenizer-path, and --output")
    if args.output.exists() or args.output.is_symlink():
        parser.error(f"output already exists: {args.output}")
    identity = _source_identity(args.source_root)
    tokenizer_manifest = verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
    before = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_clean_producer(before)
    try:
        versions = {
            package: importlib.metadata.version(package)
            for package in ("transformers", "tokenizers", "jinja2")
        }
        transformers = importlib.import_module("transformers")
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        raise RuntimeError("pinned optional tokenizer runtime is required") from exc
    if versions != {"transformers": "5.15.0", "tokenizers": "0.22.2", "jinja2": "3.1.6"}:
        raise RuntimeError("tokenizer runtime differs from registered geometry runtime")
    profile = load_api_profiles(_PROFILE_PATH).get(PROFILE_ID)
    if profile.profile_hash != PROFILE_SHA256:
        raise RuntimeError("R15 shared Qwen profile differs from registered fields")
    tokenizer = cast(
        ChatTokenizer,
        transformers.AutoTokenizer.from_pretrained(
            str(args.tokenizer_path),
            local_files_only=True,  # nosec B615
        ),
    )
    geometry = enumerate_allowed_prompt_geometry(
        args.source_root, profile=profile, tokenizer=tokenizer
    )
    result = run_offline_screen(
        args.source_root,
        profile=profile,
        endpoint=ResolvedAPIEndpoint(
            endpoint="https://api.siflow.cn/model-api/chat/completions",
            api_key="offline-synthetic-key",
        ),
        tokenizer=tokenizer,
        transport=make_synthetic_transport(tokenizer, profile),
        geometry_registry=geometry,
    )
    result["tokenizer_manifest_sha256"] = tokenizer_manifest
    result["profile_file_sha256"] = _sha(_PROFILE_PATH.read_bytes())
    result["source_identity"] = identity
    result["allowed_prompt_geometry"] = geometry
    result["runtime_versions"] = versions
    after = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_stable_attestation(before, after)
    result["code_identity"] = {"producer_attestation": before}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(args.output),
                "geometry_variants": len(geometry),
                "worker_attempt_count": result["worker_attempt_count"],
                "artifact_sha256": _sha(args.output.read_bytes()),
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "completed-offline-screen" else 2


if __name__ == "__main__":
    raise SystemExit(main())
