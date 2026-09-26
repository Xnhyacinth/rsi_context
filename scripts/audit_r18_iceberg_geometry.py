"""Exact local final-chat geometry for the R18 Iceberg prospective reader asks.

This is an offline tokenization audit, not a model call or provider parity
claim. The prompts below are the frozen candidate worker messages for a later
fixed-reader screen; a live runner must consume these functions unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import shutil
import subprocess  # nosec B404
from pathlib import Path
from typing import cast

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry
from rsicontext.experiment.api import APIProfile, load_api_profiles
from rsicontext.lifecycle.material_iceberg_row_scan import (
    CASES,
    PACK_END,
    PACK_START,
    SOURCE_RELATIVE,
    SOURCE_REVISION,
    SOURCE_SHA256,
    build_iceberg_row_scan_sessions,
    iceberg_source_ledger,
)

_ROOT = Path(__file__).resolve().parent.parent
_SOURCE = Path("/volume/pt-dev/qjiu/rsi_context_external/data/apache-iceberg-spec-1.9.2-intake")
_TOKENIZER = Path("/volume/pt-dev/qjiu/rsi_context/models/qwen3.6-27b")
_PROFILE = _ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json"
_PROFILE_ID = "siflow-qwen3.6-27b-r15-bc-dev-2048"
_PROFILE_SHA256 = "b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69"
_TOKENIZER_FILES = {
    "tokenizer.json": "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42",
    "tokenizer_config.json": "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    "chat_template.jinja": "e84f32a23fdda27689f868aa4a1a5621f41133e51a48d7f3efcbea2839574259",
}
_RUNTIME = {"transformers": "5.15.0", "tokenizers": "0.22.2", "jinja2": "3.1.6"}
_BENCHMARK_WINDOW = 32768
_SURVEY_QUERY = (
    "Using only the supplied reference, summarize the equality-delete rule "
    "without deciding a row. Return exactly four semicolon-separated fields: "
    "counter={data|file|unknown}; bound={strict|nonstrict|unknown}; "
    "partition={same-or-global|same-only|unknown}; "
    "row={all-equality-ids|any-equality-id|unknown}. Choose one value per field."
)
_DECISION_QUERY = (
    "Apply every retained source-rule field to the visible constructed facts. "
    "Return exactly plan=emit-row or plan=suppress-row."
)
_RULES = (
    "counter=data; bound=strict; partition=same-or-global; row=all-equality-ids",
    "counter=file; bound=strict; partition=same-or-global; row=all-equality-ids",
    "counter=unknown; bound=unknown; partition=unknown; row=unknown",
)
_GLOBAL_EVIDENCE = (
    "Equality delete files stored with an unpartitioned spec are applied as global deletes."
)
_EVIDENCE = {
    "authentic-pack": {
        "counter": "The file sequence number can't be used for pruning delete files",
        "scope": "The data file's data sequence number is _strictly less than_",
        "global": _GLOBAL_EVIDENCE,
        "row_match": "A data row is deleted if its values are equal to all delete columns",
    },
    "constructed-file-sequence": {
        "counter": "It is used to prune equality delete files",
        "scope": "The data file's file sequence number is _strictly less than_",
        "global": _GLOBAL_EVIDENCE,
        "row_match": "A data row is deleted if its values are equal to all delete columns",
    },
}


def survey_user(source_text: str) -> str:
    """Put the source before the classification question to measure distance."""

    return source_text + "\n\n" + _SURVEY_QUERY


def decision_user(request_text: str, retained_rule: str) -> str:
    """Enumerate every possible retained label before any worker dispatch."""

    if retained_rule not in _RULES:
        raise ValueError("unregistered retained Iceberg rule label")
    return f"Retained source rule: {retained_rule}.\n\n" + request_text + "\n\n" + _DECISION_QUERY


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _messages(profile: APIProfile, user: str) -> list[dict[str, str]]:
    if not profile.system_prompt:
        raise ValueError("frozen Iceberg profile lacks system prompt")
    return [
        {"role": "system", "content": profile.system_prompt},
        {"role": "user", "content": user},
    ]


def _measure(
    tokenizer: ChatTokenizer,
    profile: APIProfile,
    user: str,
    *,
    evidence: str | None = None,
    query: str | None = None,
) -> dict[str, object]:
    messages = _messages(profile, user)
    geometry = measure_chat_geometry(
        tokenizer,
        messages,
        enable_thinking=profile.chat_template_enable_thinking,
        evidence=evidence,
        query=query,
    )
    count = geometry["rendered_input_tokens"]
    if not isinstance(count, int):
        raise TypeError("token count must be an integer")
    return {
        "messages_sha256": _sha(
            json.dumps(messages, sort_keys=True, separators=(",", ":")).encode()
        ),
        "input_tokens": count,
        "input_plus_requested_output": count + profile.max_output_tokens,
        "fits_32k": count + profile.max_output_tokens <= _BENCHMARK_WINDOW,
        "remaining_32k_after_requested_output": _BENCHMARK_WINDOW
        - count
        - profile.max_output_tokens,
        "fits_profile": count + profile.max_output_tokens <= profile.evaluation_max_model_len,
        "evidence_span_tokens": geometry["evidence_span_tokens"],
        "query_span_tokens": geometry["query_span_tokens"],
        "evidence_to_query_tokens": geometry["evidence_to_query_tokens"],
        "span_status": geometry["span_status"],
    }


def _source_git_identity(source_root: Path) -> dict[str, object]:
    # Fixed Git argv without a shell; the resolved executable must be absolute.
    git_bin = shutil.which("git")
    if git_bin is None or not Path(git_bin).is_absolute():
        raise RuntimeError("Git is required for Iceberg source attestation")

    def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # nosec B603
            [git_bin, "-C", str(source_root), *args],
            capture_output=True,
            text=True,
            check=check,
            timeout=10,
        )

    head = git("rev-parse", "HEAD").stdout.strip()
    if head != SOURCE_REVISION:
        raise ValueError("Iceberg checkout HEAD differs from pinned revision")
    branch = git("symbolic-ref", "--quiet", "HEAD", check=False)
    if branch.returncode != 1:
        raise ValueError("Iceberg checkout must be detached")
    if git("status", "--porcelain").stdout:
        raise ValueError("Iceberg checkout must be clean")
    origin = git("remote", "get-url", "origin").stdout.strip()
    if origin != "https://github.com/apache/iceberg.git":
        raise ValueError("Iceberg origin differs from registry URL")
    return {"head": head, "detached": True, "clean": True, "origin": origin}


def audit(source_root: Path, tokenizer_root: Path, profile_file: Path) -> dict[str, object]:
    """Measure all four S1 arms, all three allowed S2 asks, and full file."""

    source_git = _source_git_identity(source_root)
    source_ledger = iceberg_source_ledger(source_root)
    profile = load_api_profiles(profile_file).get(_PROFILE_ID)
    if profile.profile_hash != _PROFILE_SHA256:
        raise ValueError("frozen Iceberg reader profile hash changed")
    transformers = importlib.import_module("transformers")
    tokenizer = cast(
        ChatTokenizer,
        transformers.AutoTokenizer.from_pretrained(str(tokenizer_root), local_files_only=True),
    )
    importlib_metadata = importlib.import_module("importlib.metadata")
    runtime = {name: importlib_metadata.version(name) for name in _RUNTIME}
    if runtime != _RUNTIME:
        raise ValueError("frozen Iceberg tokenizer runtime changed")
    tokenizer_files = {
        name: _sha((tokenizer_root / name).read_bytes()) for name in _TOKENIZER_FILES
    }
    if tokenizer_files != _TOKENIZER_FILES:
        raise ValueError("frozen Iceberg tokenizer files changed")
    raw = (source_root / SOURCE_RELATIVE).read_bytes()
    if _sha(raw) != SOURCE_SHA256:
        raise ValueError("full Iceberg source changed before geometry")
    authentic_source = (
        build_iceberg_row_scan_sessions(source_root, case="authentic-pack")[0]
        .stages[0]
        .documents[0]
        .text
    )
    authentic_pack = raw[PACK_START:PACK_END].decode()
    if not authentic_source.endswith(authentic_pack):
        raise ValueError("authentic pack is not the exact pinned contiguous slice")
    source_wrapper = authentic_source[: -len(authentic_pack)]
    full_wrapper = source_wrapper.replace(
        "Selected reference body: contiguous source lines 90-1179.",
        "Selected reference body: complete source file.",
    )
    if full_wrapper == source_wrapper:
        raise ValueError("full-file geometry wrapper did not identify its material")
    full_user = survey_user(full_wrapper + raw.decode())
    full = _measure(tokenizer, profile, full_user, query=_SURVEY_QUERY)
    first: dict[str, object] = {}
    for case in CASES:
        sessions = build_iceberg_row_scan_sessions(source_root, case=case)
        source_text = sessions[0].stages[0].documents[0].text
        user = survey_user(source_text)
        row: dict[str, object] = _measure(tokenizer, profile, user, query=_SURVEY_QUERY)
        row["source_document_utf8_sha256"] = _sha(source_text.encode("utf-8"))
        row["source_document_utf8_bytes"] = len(source_text.encode("utf-8"))
        evidence = _EVIDENCE.get(case)
        row["evidence"] = (
            {
                label: _measure(tokenizer, profile, user, evidence=needle, query=_SURVEY_QUERY)
                for label, needle in evidence.items()
            }
            if evidence is not None
            else {}
        )
        first[case] = row
    request = build_iceberg_row_scan_sessions(source_root, case="authentic-pack")[1]
    request_text = request.stages[1].documents[0].text
    second = {
        rule: _measure(
            tokenizer,
            profile,
            decision_user(request_text, rule),
            evidence=f"Retained source rule: {rule}.",
            query=_DECISION_QUERY,
        )
        for rule in _RULES
    }
    return {
        "kind": "offline-local-template-geometry; no model/provider call",
        "source": source_ledger,
        "source_git": source_git,
        "profile_id": profile.id,
        "profile_sha256": profile.profile_hash,
        "tokenizer_root_resolved": str(tokenizer_root.resolve()),
        "tokenizer_files_sha256": tokenizer_files,
        "runtime_versions": runtime,
        "benchmark_window": _BENCHMARK_WINDOW,
        "requested_output_tokens_per_call": profile.max_output_tokens,
        "profile_max_model_len": profile.evaluation_max_model_len,
        "full_file_survey": full,
        "contiguous_pack_lines": [90, 1179],
        "contiguous_pack_byte_interval": [PACK_START, PACK_END],
        "session_1": first,
        "fixed_later_request_utf8_sha256": _sha(request_text.encode("utf-8")),
        "session_2_by_retained_rule": second,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=_SOURCE)
    parser.add_argument("--tokenizer-root", type=Path, default=_TOKENIZER)
    parser.add_argument("--profile-file", type=Path, default=_PROFILE)
    args = parser.parse_args()
    print(
        json.dumps(
            audit(args.source_root, args.tokenizer_root, args.profile_file),
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
