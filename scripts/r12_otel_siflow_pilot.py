#!/usr/bin/env python3
"""Run the capped Siflow OTel fixed-reader development screen after preflight."""

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
    measure_otel_worker_prompt,
    remove_otel_decisive_row,
)
from rsicontext.analysis.otel_siflow_pilot import run_development_pilot  # noqa: E402
from rsicontext.eval.openai_compatible import _urlopen_transport  # noqa: E402
from rsicontext.experiment.api import (  # noqa: E402
    build_profile_reader,
    load_api_profiles,
    resolve_api_endpoint,
)
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
_PROFILE_ID = "siflow-qwen3.6-27b-r12-otel-dev-2048"
_TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    ("tokenizer_config.json", "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02"),
)
_SOURCE_ENVS = {
    "1.24": "RSICONTEXT_OTEL124_SOURCE_ROOT",
    "1.43": "RSICONTEXT_OTEL_SOURCE_ROOT",
}
_PRODUCER_FILES = tuple(
    Path(name)
    for name in (
        "configs/r12_otel_siflow_worker_profile_v1.json",
        "configs/r10_otel_source_contrast_manifest_v1.json",
        "configs/registry.json",
        "docs/reviews/r12-otel-fixed-reader-prereg-20260926.md",
        "scripts/r12_otel_siflow_pilot.py",
        "src/rsicontext/analysis/chat_geometry.py",
        "src/rsicontext/analysis/otel_chat_geometry.py",
        "src/rsicontext/analysis/otel_siflow_pilot.py",
        "src/rsicontext/eval/openai_compatible.py",
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


def _source_identity(revision: str, root: Path) -> dict[str, object]:
    def git(*args: str) -> str:
        return subprocess.run(  # nosec B603, B607
            ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    if git("rev-parse", "HEAD") != SOURCE_REVISIONS[revision]:
        raise RuntimeError(f"OTel {revision}: source revision changed")
    if git("status", "--porcelain"):
        raise RuntimeError(f"OTel {revision}: source checkout is dirty")
    symbolic = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(root), "symbolic-ref", "-q", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if symbolic.returncode != 1:
        raise RuntimeError(f"OTel {revision}: source checkout must be detached")
    relative = SOURCE_FILES[revision]
    digest = _sha((root / relative).read_bytes())
    if digest != SOURCE_SHA256[revision]:
        raise RuntimeError(f"OTel {revision}: source file bytes changed")
    return {
        "revision": SOURCE_REVISIONS[revision],
        "relative_path": relative,
        "selected_file_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--geometry-reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
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
        raise RuntimeError("tokenizer runtime differs from frozen geometry")
    before = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_clean_producer(before)
    profile = load_api_profiles(_PROFILE_PATH).get(_PROFILE_ID)
    endpoint = resolve_api_endpoint(profile)
    build_profile_reader(profile, endpoint)
    reference = json.loads(args.geometry_reference.read_text(encoding="utf-8"))
    if (
        not isinstance(reference, dict)
        or reference.get("profile_id") != profile.id
        or reference.get("profile_hash") != profile.profile_hash
        or reference.get("profile_file_sha256") != _sha(_PROFILE_PATH.read_bytes())
        or reference.get("scope") != "otel124_143_full_source_fixed_policy_local_geometry_only"
    ):
        raise RuntimeError("geometry reference does not match frozen OTel worker profile")
    roots: dict[str, Path] = {}
    for revision, variable in _SOURCE_ENVS.items():
        configured = os.environ.get(variable)
        if not configured:
            parser.error(f"set {variable} to the pinned detached source checkout")
        roots[revision] = Path(configured)
    identities = {revision: _source_identity(revision, root) for revision, root in roots.items()}
    if reference.get("source_identities") != identities:
        raise RuntimeError("geometry reference source revisions differ from pilot sources")
    reference_cases = reference.get("cases")
    deletion_reference = reference.get("registered_row_deletion_143")
    if not isinstance(reference_cases, dict) or not isinstance(deletion_reference, dict):
        raise RuntimeError("geometry reference lacks registered source cases")
    approved_survey_hashes: dict[tuple[str, str], str] = {}
    for revision in ("1.24", "1.43"):
        case = reference_cases.get(revision)
        if not isinstance(case, dict):
            raise RuntimeError("geometry reference lacks a full source case")
        calls = case.get("calls")
        if not isinstance(calls, list) or len(calls) != 2 or not isinstance(calls[0], dict):
            raise RuntimeError("geometry reference lacks full source calls")
        survey = calls[0]
        digest = survey.get("request_sha256")
        if (
            survey.get("stage") != "source-survey"
            or survey.get("source_revision") != revision
            or survey.get("decisive_row_status") != "unique"
            or not isinstance(digest, str)
        ):
            raise RuntimeError("geometry reference has invalid full source survey")
        approved_survey_hashes[(revision, "unique")] = digest
    deleted_calls = deletion_reference.get("calls")
    if not isinstance(deleted_calls, list) or len(deleted_calls) != 2:
        raise RuntimeError("geometry reference lacks two registered deletion calls")
    if any(
        not isinstance(call, dict)
        or call.get("stage") != "source-survey"
        or call.get("source_revision") != "1.43"
        or call.get("decisive_row_status") != "removed"
        or not isinstance(call.get("request_sha256"), str)
        for call in deleted_calls
    ):
        raise RuntimeError("geometry reference has invalid deletion survey")
    deleted_hash = deleted_calls[0]["request_sha256"]
    if deleted_calls[1]["request_sha256"] != deleted_hash:
        raise RuntimeError("geometry reference deletion reread changed the request")
    approved_survey_hashes[("1.43", "removed")] = deleted_hash
    tokenizer = cast(
        ChatTokenizer,
        transformers.AutoTokenizer.from_pretrained(
            str(args.tokenizer_path),
            local_files_only=True,  # nosec B615
        ),
    )
    sessions = {
        revision: build_otel_source_contrast_sessions(root, revision=revision)
        for revision, root in roots.items()
    }
    world_sha256 = {
        revision: [
            _sha(
                json.dumps(
                    session.to_dict(),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            )
            for session in pair
        ]
        for revision, pair in sessions.items()
    }
    for revision, digests in world_sha256.items():
        case = reference_cases[revision]
        if not isinstance(case, dict) or case.get("world_sha256") != digests:
            raise RuntimeError("geometry reference world bytes differ from pilot world")
    deleted_source = remove_otel_decisive_row(sessions["1.43"][0].stages[0].documents[0].text)
    if deletion_reference.get("visible_source_sha256") != _sha(deleted_source.encode("utf-8")):
        raise RuntimeError("geometry reference deletion source differs from preregistered bytes")

    def preflight(prompt: str) -> dict[str, object]:
        measured = measure_otel_worker_prompt(tokenizer, profile, prompt)
        if measured["stage"] == "source-survey":
            revision = measured.get("source_revision")
            row_status = measured.get("decisive_row_status")
            if not isinstance(revision, str) or not isinstance(row_status, str):
                raise ValueError("survey preflight lacks source identity")
            key = (revision, row_status)
            if measured["request_sha256"] != approved_survey_hashes.get(key):
                raise ValueError("actual survey request differs from registered geometry")
        return measured

    result = run_development_pilot(
        sessions["1.24"],
        sessions["1.43"],
        profile=profile,
        endpoint=endpoint,
        preflight=preflight,
        transport=_urlopen_transport,
    )
    result["source_identities"] = identities
    result["world_sha256"] = world_sha256
    result["geometry_reference_sha256"] = _sha(args.geometry_reference.read_bytes())
    result["profile_file_sha256"] = _sha(_PROFILE_PATH.read_bytes())
    result["tokenizer_file_sha256"] = verify_tokenizer_snapshot(
        args.tokenizer_path, _TOKENIZER_FILES
    )
    result["code_identity"] = {"producer_attestation": before}
    after = producer_attestation(
        ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
    )
    require_stable_attestation(before, after)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(args.output),
                "worker_attempt_count": result["worker_attempt_count"],
                "provider_usage_total": result["provider_usage_total"],
                "artifact_sha256": _sha(args.output.read_bytes()),
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "completed-development-screen" else 2


if __name__ == "__main__":
    raise SystemExit(main())
