#!/usr/bin/env python3
"""Record exact local Qwen request geometry for the PG16/17 fixed-policy calls.

This is an offline replay with a fake worker. It does not attest Siflow's
template or usage and cannot establish reader difficulty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rsicontext.analysis.chat_geometry import ChatTokenizer  # noqa: E402
from rsicontext.analysis.postgresql_chat_geometry import measure_pg_worker_prompt  # noqa: E402
from rsicontext.analysis.postgresql_model_screen import run_case  # noqa: E402
from rsicontext.experiment.api import APIProfile, load_api_profiles  # noqa: E402
from rsicontext.experiment.offline_provenance import (  # noqa: E402
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.lifecycle.material_postgresql_source_contrast import (  # noqa: E402
    SOURCE_REVISIONS,
    SOURCE_SHA256,
    build_postgresql_source_contrast_sessions,
)
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot  # noqa: E402

_PROFILE_PATH = ROOT / "configs/r11_pg_siflow_worker_profile_v1.json"
_PROFILE_ID = "siflow-qwen3.6-27b-r11-pg-dev-2048"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
)
_SOURCE_ROOT_ENVS = {
    "16": "RSICONTEXT_POSTGRESQL16_SOURCE_ROOT",
    "17": "RSICONTEXT_POSTGRESQL_SOURCE_ROOT",
}
_PRODUCER_FILES = tuple(
    Path(name)
    for name in (
        "configs/r11_pg_siflow_worker_profile_v1.json",
        "configs/registry.json",
        "scripts/r11_pg_prompt_geometry.py",
        "src/rsicontext/analysis/chat_geometry.py",
        "src/rsicontext/analysis/postgresql_chat_geometry.py",
        "src/rsicontext/analysis/postgresql_model_screen.py",
        "src/rsicontext/experiment/api.py",
        "src/rsicontext/experiment/offline_provenance.py",
        "src/rsicontext/lifecycle/postgresql_model_fixed.py",
        "src/rsicontext/lifecycle/material_postgresql_source_contrast.py",
        "src/rsicontext/lifecycle/env.py",
        "src/rsicontext/lifecycle/policy.py",
        "src/rsicontext/lifecycle/runner.py",
        "src/rsicontext/lifecycle/session_sequence.py",
        "src/rsicontext/lifecycle/tools.py",
        "uv.lock",
    )
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source_identity(revision: str, root: Path) -> dict[str, object]:
    head = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    symbolic = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if head != SOURCE_REVISIONS[revision] or status or symbolic.returncode != 1:
        raise ValueError(f"PostgreSQL {revision} source is not the clean detached pin")
    return {"revision": head, "selected_file_sha256": SOURCE_SHA256[revision]}


def build_report(
    tokenizer: ChatTokenizer,
    profile: APIProfile,
    roots: dict[str, Path],
    *,
    tokenizer_path: Path,
) -> dict[str, object]:
    snapshot = verify_tokenizer_snapshot(tokenizer_path, _TOKENIZER_FILES)
    cases: dict[str, object] = {}
    identities: dict[str, object] = {}
    for revision in ("16", "17"):
        root = roots[revision]
        identities[revision] = _source_identity(revision, root)
        sessions = build_postgresql_source_contrast_sessions(root, revision=revision)
        case = run_case(f"full-{revision}", sessions)
        if len(case.worker.prompts) != 2:
            raise ValueError("full PostgreSQL case must have exactly two worker requests")
        calls = [
            measure_pg_worker_prompt(tokenizer, profile, prompt) for prompt in case.worker.prompts
        ]
        if [call["stage"] for call in calls] != ["source-survey", "project-request-stage"]:
            raise ValueError("PostgreSQL worker call order changed")
        source = sessions[0].stages[0].documents[0].text
        if source not in case.worker.prompts[0] or source in case.worker.prompts[1]:
            raise ValueError("survey and resumed request boundary changed")
        cases[revision] = {
            "world_sha256": [
                _sha(
                    json.dumps(
                        session.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    ).encode("utf-8")
                )
                for session in sessions
            ],
            "material_sha256": case.material_sha256,
            "notice_sha256": case.notice_sha256,
            "fake_worker_only": case.summary(),
            "calls": calls,
        }
    return {
        "schema_version": 1,
        "scope": "pg16_17_full_source_fixed_policy_local_geometry_only",
        "profile_id": profile.id,
        "profile_hash": profile.profile_hash,
        "profile_file_sha256": _sha(_PROFILE_PATH.read_bytes()),
        "tokenizer": {
            "revision": "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b",
            "files_sha256": snapshot,
            "runtime": "transformers==5.15.0 tokenizers==0.22.2 jinja2==3.1.6",
        },
        "source_identities": identities,
        "source_sha256": {str(path): _sha((ROOT / path).read_bytes()) for path in _PRODUCER_FILES},
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    roots = {}
    for revision, variable in _SOURCE_ROOT_ENVS.items():
        configured = os.environ.get(variable)
        if not configured:
            parser.error(f"set {variable} to the clean detached source checkout")
        roots[revision] = Path(configured)
    verify_tokenizer_snapshot(args.tokenizer_path, _TOKENIZER_FILES)
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
        raise ValueError("tokenizer runtime versions differ from uv.lock")
    before = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_clean_producer(before)
    tokenizer = cast(
        ChatTokenizer,
        transformers.AutoTokenizer.from_pretrained(
            str(args.tokenizer_path),
            local_files_only=True,  # nosec B615
        ),
    )
    profile = load_api_profiles(_PROFILE_PATH).get(_PROFILE_ID)
    report = build_report(tokenizer, profile, roots, tokenizer_path=args.tokenizer_path)
    after = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_stable_attestation(before, after)
    report["producer_attestation"] = before
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    print(f"{args.output} sha256={_sha(args.output.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
