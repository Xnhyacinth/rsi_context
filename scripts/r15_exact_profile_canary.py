#!/usr/bin/env python3
"""Exact R15 Qwen profile canary with a source-free prompt and safe evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
import tempfile
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rsicontext.analysis.chat_geometry import (  # noqa: E402
    ChatTokenizer,
    measure_chat_geometry,
)
from rsicontext.analysis.otel_siflow_pilot import _validated_usage, _Worker  # noqa: E402
from rsicontext.eval.openai_compatible import Transport, _urlopen_transport  # noqa: E402
from rsicontext.experiment.api import (  # noqa: E402
    APIProfile,
    ResolvedAPIEndpoint,
    load_api_profiles,
    resolve_api_endpoint,
)
from rsicontext.experiment.offline_provenance import (  # noqa: E402
    producer_attestation,
    require_clean_producer,
    require_stable_attestation,
)
from rsicontext.registry.tokenizer import verify_tokenizer_snapshot  # noqa: E402

PROFILE_PATH = ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json"
PROFILE_ID = "siflow-qwen3.6-27b-r15-bc-dev-2048"
PROFILE_SHA256 = "b9e0df1d39f4c74b684661a7b7e4a714f33a7b0fd8741c3e183d1203ca21ce69"
PROFILE_FILE_SHA256 = "c3bb91d662d588e0a0a69101fb8fd851a1c910ded66e4387d4afccc9c9002ff6"
ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
TOKENIZER_FILES = (
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    ("tokenizer_config.json", "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02"),
)
TOKENIZER_MANIFEST_SHA256 = "8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290"
PROMPT = "The canary code is amber.\nQuestion: What is the canary code?\nReturn only the code."
PROMPT_SHA256 = "82db1be2cb4e36e5b467da2878aa5fe12472b368c183dad5fe96832fd898d29e"
REQUEST_SHA256 = "ae27605ddced560f68df36a2dca547813ae58104be3bf164b7ab54ae8bff7314"
EXPECTED_INPUT_TOKENS = 62
EXPECTED_ANSWER = "amber"
MAX_CALLS = 1
_PRODUCER_FILES = tuple(
    Path(name)
    for name in (
        "configs/r15_siflow_fixed_reader_profile_v1.json",
        "scripts/r15_exact_profile_canary.py",
        "src/rsicontext/analysis/chat_geometry.py",
        "src/rsicontext/analysis/otel_siflow_pilot.py",
        "src/rsicontext/eval/openai_compatible.py",
        "src/rsicontext/experiment/api.py",
        "src/rsicontext/experiment/offline_provenance.py",
        "src/rsicontext/registry/tokenizer.py",
        "uv.lock",
    )
)


class CanaryRefusal(RuntimeError):
    """Named pre-dispatch refusal; its message never enters output."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _artifact_bytes(result: Mapping[str, object]) -> bytes:
    return (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reserve_artifact(path: Path, result: Mapping[str, object]) -> None:
    """Reserve a private evidence file before a credential or request is used."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(_artifact_bytes(result))
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _update_artifact(path: Path, result: Mapping[str, object]) -> None:
    """Keep the previous valid ledger if a later write cannot complete."""

    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(_artifact_bytes(result))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def registration() -> dict[str, object]:
    """Code-owned source-free canary identity for explicit execute opt-in."""

    return {
        "schema_version": 1,
        "kind": "r15-exact-qwen-profile-source-free-canary",
        "profile_id": PROFILE_ID,
        "profile_sha256": PROFILE_SHA256,
        "profile_file_sha256": PROFILE_FILE_SHA256,
        "tokenizer_manifest_sha256": TOKENIZER_MANIFEST_SHA256,
        "prompt_sha256": PROMPT_SHA256,
        "request_sha256": REQUEST_SHA256,
        "expected_input_tokens": EXPECTED_INPUT_TOKENS,
        "expected_answer_sha256": _sha(EXPECTED_ANSWER.encode()),
        "endpoint_sha256": _sha(ENDPOINT.encode()),
        "max_output_tokens": 2048,
        "max_calls": MAX_CALLS,
    }


def registration_sha256() -> str:
    return _sha(_canonical(registration()))


def _profile() -> APIProfile:
    if _sha(PROFILE_PATH.read_bytes()) != PROFILE_FILE_SHA256:
        raise CanaryRefusal("profile-file-drift")
    profile = load_api_profiles(PROFILE_PATH).get(PROFILE_ID)
    if (
        profile.profile_hash != PROFILE_SHA256
        or profile.model != "Qwen/Qwen3.6-27B"
        or profile.max_output_tokens != 2048
        or profile.chat_template_enable_thinking is not False
        or not profile.system_prompt
    ):
        raise CanaryRefusal("profile-fields-drift")
    return profile


def _tokenizer(root: Path) -> ChatTokenizer:
    if verify_tokenizer_snapshot(root, TOKENIZER_FILES) != TOKENIZER_MANIFEST_SHA256:
        raise CanaryRefusal("tokenizer-manifest-drift")
    versions = {
        package: importlib.metadata.version(package)
        for package in ("transformers", "tokenizers", "jinja2")
    }
    if versions != {"transformers": "5.15.0", "tokenizers": "0.22.2", "jinja2": "3.1.6"}:
        raise CanaryRefusal("tokenizer-runtime-drift")
    transformers = importlib.import_module("transformers")
    return cast(
        ChatTokenizer,
        transformers.AutoTokenizer.from_pretrained(str(root), local_files_only=True),  # nosec B615
    )


def _geometry(tokenizer: ChatTokenizer, profile: APIProfile) -> dict[str, object]:
    if not isinstance(profile.system_prompt, str):
        raise CanaryRefusal("profile-system-prompt-missing")
    messages: list[dict[str, str]] = [
        {"role": "system", "content": profile.system_prompt},
        {"role": "user", "content": PROMPT},
    ]
    measured = measure_chat_geometry(
        tokenizer,
        messages,
        enable_thinking=False,
        evidence="The canary code is amber.",
        query="What is the canary code?",
    )
    payload = {
        "max_tokens": profile.max_output_tokens,
        "messages": messages,
        "model": profile.model,
        "seed": profile.seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if (
        _sha(PROMPT.encode()) != PROMPT_SHA256
        or _sha(_canonical(payload)) != REQUEST_SHA256
        or measured["rendered_input_tokens"] != EXPECTED_INPUT_TOKENS
        or measured["span_status"] != "unique_later_query"
        or EXPECTED_INPUT_TOKENS + profile.max_output_tokens > profile.evaluation_max_model_len
    ):
        raise CanaryRefusal("exact-chat-geometry-drift")
    return {
        "stage": "source-free-profile-canary",
        "prompt_sha256": PROMPT_SHA256,
        "request_sha256": REQUEST_SHA256,
        "local_template_geometry": measured,
        "profile_sha256": PROFILE_SHA256,
    }


def _fake_transport(profile: APIProfile, tokenizer: ChatTokenizer) -> Transport:
    def fake(request: urllib.request.Request, _timeout: float) -> bytes:
        if not isinstance(request.data, bytes):
            raise CanaryRefusal("fake-request-missing-body")
        body = json.loads(request.data)
        if not isinstance(body, dict) or _sha(_canonical(body)) != REQUEST_SHA256:
            raise CanaryRefusal("fake-request-drift")
        output_tokens = len(
            tokenizer(EXPECTED_ANSWER, add_special_tokens=False, return_offsets_mapping=True)[
                "input_ids"
            ]
        )
        identity = {"id": "offline-r15-profile-canary", "model": profile.model}
        content = {
            **identity,
            "choices": [{"delta": {"content": EXPECTED_ANSWER}, "finish_reason": "stop"}],
        }
        usage = {
            **identity,
            "choices": [],
            "usage": {
                "prompt_tokens": EXPECTED_INPUT_TOKENS,
                "completion_tokens": output_tokens,
            },
        }
        return (
            "data: "
            + json.dumps(content)
            + "\n\n"
            + "data: "
            + json.dumps(usage)
            + "\n\n"
            + "data: [DONE]\n\n"
        ).encode()

    return fake


def _safe_attempt(attempt: Mapping[str, object] | None, *, synthetic: bool) -> dict[str, object]:
    if attempt is None:
        return {"attempted": False, "usage": None}
    usage = attempt.get("provider_usage")
    safe_usage: dict[str, int] | None = None
    if (
        isinstance(usage, dict)
        and type(usage.get("input_tokens")) is int
        and type(usage.get("output_tokens")) is int
        and usage["input_tokens"] >= 0
        and usage["output_tokens"] >= 0
    ):
        safe_usage = {
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        }
    response_id = attempt.get("response_id")
    response_sha = attempt.get("response_sha256")
    response_id_valid = False
    response_id_sha256: str | None = None
    if isinstance(response_id, str):
        try:
            response_id.encode("utf-8")
            response_id_valid = True
        except UnicodeEncodeError:
            pass
        response_id_sha256 = _sha(response_id.encode("utf-8", errors="surrogatepass"))
    result: dict[str, object] = {
        "attempted": True,
        "status": "ok" if attempt.get("status") == "ok" else "failed",
        "request_sha256": attempt.get("request_sha256")
        if attempt.get("request_sha256") == REQUEST_SHA256
        else None,
        "prompt_sha256": attempt.get("prompt_sha256")
        if attempt.get("prompt_sha256") == PROMPT_SHA256
        else None,
        "response_sha256": response_sha
        if isinstance(response_sha, str) and len(response_sha) == 64
        else None,
        "response_id_sha256": response_id_sha256,
        "response_id_valid": response_id_valid,
        "model_echo_exact": attempt.get("response_model") == "Qwen/Qwen3.6-27B",
        "finish_stop": attempt.get("finish_reason") == "stop",
        "usage": safe_usage,
        "usage_provenance": "synthetic" if synthetic else "provider-reported",
    }
    return result


def run_canary(
    *,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    tokenizer: ChatTokenizer,
    transport: Transport,
    synthetic: bool,
) -> dict[str, object]:
    """Run one strict reader request; retain only allowlisted evidence fields."""

    geometry = _geometry(tokenizer, profile)

    def preflight(prompt: str) -> dict[str, object]:
        if prompt != PROMPT:
            raise CanaryRefusal("canary-prompt-drift")
        return geometry

    worker = _Worker(profile, endpoint, preflight, transport)
    failure_type: str | None = None
    answer = ""
    try:
        answer = worker(PROMPT)
    except Exception as exc:
        failure_type = type(exc).__name__
    attempt = _safe_attempt(worker.attempts[0] if worker.attempts else None, synthetic=synthetic)
    answer_observed = failure_type is None
    try:
        local_output_tokens = len(
            tokenizer(answer, add_special_tokens=False, return_offsets_mapping=True)["input_ids"]
        )
    except Exception as exc:
        failure_type = type(exc).__name__
        local_output_tokens = -1
    usage = attempt.get("usage")
    passed = (
        failure_type is None
        and answer == EXPECTED_ANSWER
        and len(worker.attempts) == MAX_CALLS
        and attempt.get("status") == "ok"
        and attempt.get("response_id_valid") is True
        and attempt.get("model_echo_exact") is True
        and attempt.get("finish_stop") is True
        and isinstance(usage, dict)
        and usage.get("input_tokens") == EXPECTED_INPUT_TOKENS
        and usage.get("output_tokens") == local_output_tokens
    )
    if failure_type is None and not passed:
        if answer != EXPECTED_ANSWER:
            failure_type = "AnswerMismatch"
        elif attempt.get("response_id_valid") is not True:
            failure_type = "ResponseIdentityInvalid"
        elif isinstance(usage, dict) and usage.get("output_tokens") != local_output_tokens:
            failure_type = "OutputUsageMismatch"
        elif isinstance(usage, dict) and usage.get("input_tokens") != EXPECTED_INPUT_TOKENS:
            failure_type = "InputUsageMismatch"
        else:
            failure_type = "CanaryInvariantMismatch"
    return {
        "status": "passed" if passed else "failed",
        "failure_type": failure_type,
        "answer_exact": answer == EXPECTED_ANSWER if answer_observed else False,
        "answer_sha256": _sha(answer.encode()) if answer_observed else None,
        "call_count": len(worker.attempts),
        "attempt": attempt,
        "provider_usage_total": None if synthetic else attempt.get("usage"),
        "synthetic_usage_total": attempt.get("usage") if synthetic else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registration-sha256")
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():
        parser.error(f"output already exists: {args.output}")
    if args.execute and args.output.resolve().is_relative_to(ROOT.resolve()):
        parser.error("execute output must be outside the producer worktree")
    synthetic = bool(args.dry_run)
    result: dict[str, object] = {
        "schema_version": 1,
        "kind": "r15-exact-profile-source-free-canary",
        "mode": "dry-run" if args.dry_run else "execute",
        "transport_kind": "offline-fake" if args.dry_run else "live-siflow",
        "status": "preflight",
        "registration": registration(),
        "registration_sha256": registration_sha256(),
        "live_model_called": False,
        "call_count": 0,
        "attempt": {"attempted": False, "usage": None},
        "provider_usage_total": None,
        "synthetic_usage_total": None,
    }
    try:
        _reserve_artifact(args.output, result)
    except OSError as exc:
        parser.error(f"cannot reserve output artifact: {type(exc).__name__}")
    try:
        if args.execute and args.registration_sha256 != registration_sha256():
            raise CanaryRefusal("registration-mismatch")
        if args.dry_run and args.registration_sha256 is not None:
            raise CanaryRefusal("dry-run-does-not-take-registration")
        before = producer_attestation(
            ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
        )
        result["code_identity"] = {"producer_attestation": before}
        if args.execute:
            require_clean_producer(before)
        profile = _profile()
        if args.execute:
            endpoint = resolve_api_endpoint(profile, endpoint=ENDPOINT)
            if endpoint.endpoint != ENDPOINT or endpoint.api_key is None:
                raise CanaryRefusal("endpoint-or-key-missing")
        else:
            endpoint = ResolvedAPIEndpoint(ENDPOINT, "offline-synthetic-key")
        tokenizer = _tokenizer(args.tokenizer_path)
        geometry = _geometry(tokenizer, profile)
        result["local_geometry"] = geometry["local_template_geometry"]
        result["status"] = "preflight-passed"
        _update_artifact(args.output, result)

        def live_transport(request: urllib.request.Request, timeout: float) -> bytes:
            if result["call_count"] != 0:
                raise CanaryRefusal("canary-call-cap-reached")
            if request.full_url != ENDPOINT or not isinstance(request.data, bytes):
                raise CanaryRefusal("canary-request-route-drift")
            result.update(
                status="dispatch-started",
                live_model_called=True,
                call_count=1,
                attempt={
                    "attempted": True,
                    "status": "dispatch-started",
                    "request_sha256": _sha(request.data),
                    "usage": None,
                },
            )
            try:
                _update_artifact(args.output, result)
            except OSError:
                result["live_model_called"] = False
                result["status"] = "dispatch-blocked-on-artifact-write"
                raise
            raw = _urlopen_transport(request, timeout)
            usage = _validated_usage(raw)
            result["provider_usage_total"] = usage
            result["attempt"] = {
                "attempted": True,
                "status": "response-received",
                "request_sha256": _sha(request.data),
                "response_sha256": _sha(raw),
                "usage": usage,
                "usage_provenance": "provider-reported",
            }
            _update_artifact(args.output, result)
            return raw

        transport = _fake_transport(profile, tokenizer) if synthetic else live_transport
        try:
            result.update(
                run_canary(
                    profile=profile,
                    endpoint=endpoint,
                    tokenizer=tokenizer,
                    transport=transport,
                    synthetic=synthetic,
                )
            )
        finally:
            after = producer_attestation(
                ROOT, _PRODUCER_FILES, package_names=("transformers", "tokenizers", "jinja2")
            )
            require_stable_attestation(before, after)
    except Exception as exc:
        result["status"] = "refused"
        result["failure_type"] = type(exc).__name__
        result["failure_code"] = str(exc) if isinstance(exc, CanaryRefusal) else "preflight-error"
    try:
        _update_artifact(args.output, result)
    except OSError:
        print("canary artifact update failed; prior ledger retained", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(args.output),
                "artifact_sha256": _sha(args.output.read_bytes()),
                "registration_sha256": registration_sha256(),
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
