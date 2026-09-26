#!/usr/bin/env python3
"""Record local Qwen geometry for exact OTel 1.24/1.43 frozen worker calls.

This offline fake-worker replay does not attest Siflow template parity, usage,
or reader difficulty. The row deletion is a separately marked intervention.
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
from rsicontext.analysis.otel_chat_geometry import (  # noqa: E402
    PROFILE_ID,
    measure_otel_worker_prompt,
    remove_otel_decisive_row,
)
from rsicontext.analysis.otel_model_screen import run_case  # noqa: E402
from rsicontext.experiment.api import APIProfile, load_api_profiles  # noqa: E402
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
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot  # noqa: E402

_PROFILE_PATH = ROOT / "configs/r12_otel_siflow_worker_profile_v1.json"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
)
_SOURCE_ROOT_ENVS = {
    "1.24": "RSICONTEXT_OTEL124_SOURCE_ROOT",
    "1.43": "RSICONTEXT_OTEL_SOURCE_ROOT",
}
_PRODUCER_FILES = tuple(
    Path(name)
    for name in (
        "configs/r12_otel_siflow_worker_profile_v1.json",
        "configs/r10_otel_source_contrast_manifest_v1.json",
        "configs/registry.json",
        "scripts/r12_otel_prompt_geometry.py",
        "src/rsicontext/analysis/chat_geometry.py",
        "src/rsicontext/analysis/otel_chat_geometry.py",
        "src/rsicontext/analysis/otel_model_screen.py",
        "src/rsicontext/experiment/api.py",
        "src/rsicontext/experiment/offline_provenance.py",
        "src/rsicontext/lifecycle/otel_model_fixed.py",
        "src/rsicontext/lifecycle/material_otel_source_contrast.py",
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


def _git(root: Path, *args: str) -> str:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _source_identity(revision: str, root: Path) -> dict[str, object]:
    if _git(root, "rev-parse", "HEAD") != SOURCE_REVISIONS[revision]:
        raise ValueError(f"OTel {revision} source HEAD differs from pin")
    if _git(root, "status", "--porcelain"):
        raise ValueError(f"OTel {revision} source has local changes")
    detached = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if detached.returncode != 1:
        raise ValueError(f"OTel {revision} source is not detached")
    relative = SOURCE_FILES[revision]
    digest = _sha((root / relative).read_bytes())
    if digest != SOURCE_SHA256[revision]:
        raise ValueError(f"OTel {revision} source bytes differ from pin")
    return {
        "revision": SOURCE_REVISIONS[revision],
        "relative_path": relative,
        "selected_file_sha256": digest,
    }


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
    for revision in ("1.24", "1.43"):
        root = roots[revision]
        identities[revision] = _source_identity(revision, root)
        sessions = build_otel_source_contrast_sessions(root, revision=revision)
        case = run_case(f"full-{revision}", sessions)
        if len(case.worker.prompts) != 2:
            raise ValueError("full OTel case must have exactly two worker requests")
        calls = [
            measure_otel_worker_prompt(tokenizer, profile, prompt) for prompt in case.worker.prompts
        ]
        if [call["stage"] for call in calls] != ["source-survey", "project-request-stage"]:
            raise ValueError("OTel worker call order changed")
        source = sessions[0].stages[0].documents[0].text
        if source not in case.worker.prompts[0] or source in case.worker.prompts[1]:
            raise ValueError("survey and resumed request boundary changed")
        cases[revision] = {
            "world_sha256": [
                _sha(
                    json.dumps(
                        session.to_dict(),
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                )
                for session in sessions
            ],
            "fake_worker_only": case.summary(),
            "calls": calls,
        }
    newer = build_otel_source_contrast_sessions(roots["1.43"], revision="1.43")
    deleted = remove_otel_decisive_row(newer[0].stages[0].documents[0].text)
    deletion_case = run_case("row-deleted-143", newer, source_text=deleted)
    if len(deletion_case.worker.prompts) != 2 or len(set(deletion_case.worker.prompts)) != 1:
        raise ValueError("registered row deletion must survey the same source twice")
    deleted_calls = [
        measure_otel_worker_prompt(tokenizer, profile, prompt)
        for prompt in deletion_case.worker.prompts
    ]
    if any(call["decisive_row_status"] != "removed" for call in deleted_calls):
        raise ValueError("registered deletion was not recognized")
    return {
        "schema_version": 1,
        "scope": "otel124_143_full_source_fixed_policy_local_geometry_only",
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
        "registered_row_deletion_143": {
            "visible_source_sha256": _sha(deleted.encode("utf-8")),
            "fake_worker_only": deletion_case.summary(),
            "calls": deleted_calls,
        },
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
    profile = load_api_profiles(_PROFILE_PATH).get(PROFILE_ID)
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
