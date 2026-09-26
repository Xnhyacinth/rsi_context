#!/usr/bin/env python3
"""Guarded, small Siflow PEP development screen with private evidence files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess  # nosec B404
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import r15_exact_profile_canary as canary  # noqa: E402

from rsicontext.analysis.otel_siflow_pilot import _validated_usage  # noqa: E402
from rsicontext.analysis.pep_fixed_reader_r15 import (  # noqa: E402
    MAX_WORKER_ATTEMPTS,
    _validate_registration,
    build_pep_cases,
    run_pep_screen,
)
from rsicontext.eval.openai_compatible import Transport, _urlopen_transport  # noqa: E402
from rsicontext.experiment.api import ResolvedAPIEndpoint, resolve_api_endpoint  # noqa: E402

_LAUNCH_PATH = ROOT / "configs/r15_pep_paid_launch_v1.json"
_GEOMETRY_PATH = ROOT / "configs/r15_pep_fixed_reader_geometry_v1.json"
_RUNNER_RELATIVE = "scripts/r15_pep_paid_runner.py"
_CANARY_RELATIVE = "scripts/r15_exact_profile_canary.py"
_GEOMETRY_RELATIVE = "configs/r15_pep_fixed_reader_geometry_v1.json"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _committed_bytes(relative: str) -> bytes:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(ROOT), "show", f"HEAD:{relative}"],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout


def _read_launch_manifest() -> tuple[dict[str, object], str]:
    raw = _LAUNCH_PATH.read_bytes()
    if raw != _committed_bytes("configs/r15_pep_paid_launch_v1.json"):
        raise ValueError("launch manifest differs from committed HEAD")
    value = json.loads(raw)
    required = {
        "schema_version",
        "scope",
        "geometry_sha256",
        "canary_registration_sha256",
        "canary_script_sha256",
        "runner_script_sha256",
        "endpoint_sha256",
        "profile_sha256",
        "task_call_cap",
        "task_local_plus_requested_ceiling",
        "canary_call_cap",
        "canary_local_input_tokens",
        "canary_requested_output_tokens",
        "global_call_cap",
        "global_local_plus_requested_ceiling",
        "auxiliary_call_cap",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("launch manifest schema differs from frozen contract")
    if value["schema_version"] != 1 or value["scope"] != "r15-pep-paid-development":
        raise ValueError("launch manifest version or scope differs")
    if value["geometry_sha256"] != _sha(_GEOMETRY_PATH.read_bytes()) or (
        _GEOMETRY_PATH.read_bytes() != _committed_bytes(_GEOMETRY_RELATIVE)
    ):
        raise ValueError("launch geometry differs from committed registration")
    if value["canary_registration_sha256"] != canary.registration_sha256():
        raise ValueError("launch canary request differs from frozen registration")
    for relative, field in (
        (_RUNNER_RELATIVE, "runner_script_sha256"),
        (_CANARY_RELATIVE, "canary_script_sha256"),
    ):
        current = (ROOT / relative).read_bytes()
        if current != _committed_bytes(relative) or value[field] != _sha(current):
            raise ValueError(f"launch producer differs from committed bytes: {relative}")
    if (
        value["endpoint_sha256"] != _sha(canary.ENDPOINT.encode())
        or value["profile_sha256"] != canary.PROFILE_SHA256
        or value["task_call_cap"] != MAX_WORKER_ATTEMPTS
        or value["canary_call_cap"] != 2
        or value["canary_local_input_tokens"] != canary.EXPECTED_INPUT_TOKENS
        or value["canary_requested_output_tokens"] != 2048
        or value["global_call_cap"] != MAX_WORKER_ATTEMPTS + 2
        or value["auxiliary_call_cap"] != 0
    ):
        raise ValueError("launch identity or call caps differ from frozen inputs")
    task_cap = value["task_local_plus_requested_ceiling"]
    global_cap = value["global_local_plus_requested_ceiling"]
    if (
        type(task_cap) is not int
        or type(global_cap) is not int
        or task_cap <= 0
        or global_cap != task_cap + 2 * (canary.EXPECTED_INPUT_TOKENS + 2048)
    ):
        raise ValueError("launch requested-token envelope differs")
    return value, _sha(raw)


def _private_dir(path: Path) -> None:
    if path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("run directory must be outside the repository")
    parent = path.parent.resolve()
    repository = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if repository.returncode == 0:
        raise ValueError("run directory must be outside a Git repository")
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite run directory: {path}")
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    if path.stat().st_mode & 0o077:
        raise PermissionError("run directory must be private")


def _write_json(path: Path, value: object) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _append_event(path: Path, event: dict[str, object]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":"), sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _reserve_journal(path: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        os.fsync(stream.fileno())


class _JournalTransport:
    """Persist every dispatch and response without headers, bodies, or errors."""

    def __init__(
        self,
        *,
        base: Transport,
        journal_path: Path,
        geometry: dict[str, object],
        manifest: dict[str, object],
    ) -> None:
        self.base = base
        self.journal_path = journal_path
        self.manifest = manifest
        self.phase = "pre-canary"
        self.attempts = 0
        self.task_attempts = 0
        self.canary_attempts = 0
        self.planned_tokens = 0
        self.task_planned_tokens = 0
        self.provider_input_tokens = 0
        self.provider_output_tokens = 0
        self.unknown_usage_attempts = 0
        registered = geometry.get("registered_requests")
        if not isinstance(registered, dict):
            raise ValueError("geometry lacks registered requests")
        self.registered = registered

    def _cap(self, name: str) -> int:
        value = self.manifest.get(name)
        if type(value) is not int or value <= 0:
            raise ValueError(f"launch manifest has invalid cap: {name}")
        return value

    def __call__(self, request: urllib.request.Request, timeout: float) -> bytes:
        if self.phase not in {"pre-canary", "task", "post-canary"}:
            raise RuntimeError("unknown provider phase")
        if request.full_url != canary.ENDPOINT:
            raise RuntimeError("provider request endpoint differs from frozen URL")
        if not isinstance(request.data, bytes):
            raise RuntimeError("provider request lacks body")
        request_hash = _sha(request.data)
        if self.phase == "task":
            matches = [
                entry
                for entry in self.registered.values()
                if isinstance(entry, dict) and entry.get("request_sha256") == request_hash
            ]
            if len(matches) != 1:
                raise RuntimeError("provider task request is not registered")
            local = matches[0].get("local_template_geometry")
            tokens = local.get("rendered_input_tokens") if isinstance(local, dict) else None
            if self.task_attempts >= self._cap("task_call_cap"):
                raise RuntimeError("task provider attempt cap reached")
        else:
            if request_hash != canary.REQUEST_SHA256:
                raise RuntimeError("provider canary request is not registered")
            tokens = canary.EXPECTED_INPUT_TOKENS
            if self.canary_attempts >= self._cap("canary_call_cap"):
                raise RuntimeError("canary provider attempt cap reached")
        if not isinstance(tokens, int) or tokens <= 0:
            raise RuntimeError("provider request lacks local token geometry")
        projected = self.planned_tokens + tokens + 2048
        if self.phase == "task" and self.task_planned_tokens + tokens + 2048 > self._cap(
            "task_local_plus_requested_ceiling"
        ):
            raise RuntimeError("task requested-token ceiling reached")
        if self.attempts >= self._cap("global_call_cap") or projected > self._cap(
            "global_local_plus_requested_ceiling"
        ):
            raise RuntimeError("global requested-token or call cap reached")
        self.planned_tokens = projected
        if self.phase == "task":
            self.task_planned_tokens += tokens + 2048
        self.attempts += 1
        if self.phase == "task":
            self.task_attempts += 1
        else:
            self.canary_attempts += 1
        sequence = self.attempts
        _append_event(
            self.journal_path,
            {
                "sequence": sequence,
                "phase": self.phase,
                "event": "dispatched",
                "request_sha256": request_hash,
                "local_input_tokens": tokens,
                "requested_output_cap": 2048,
            },
        )
        try:
            raw = self.base(request, timeout)
        except Exception as exc:
            self.unknown_usage_attempts += 1
            _append_event(
                self.journal_path,
                {
                    "sequence": sequence,
                    "event": "transport-failed",
                    "error_type": type(exc).__name__,
                },
            )
            raise RuntimeError("provider transport failed") from None
        if not isinstance(raw, bytes):
            self.unknown_usage_attempts += 1
            _append_event(self.journal_path, {"sequence": sequence, "event": "response-invalid"})
            raise RuntimeError("provider response is not bytes")
        response_sha = _sha(raw)
        try:
            usage = _validated_usage(raw)
        except Exception as exc:
            self.unknown_usage_attempts += 1
            _append_event(
                self.journal_path,
                {
                    "sequence": sequence,
                    "event": "usage-parse-failed",
                    "response_sha256": response_sha,
                    "error_type": type(exc).__name__,
                },
            )
            raise RuntimeError("provider usage parsing failed") from None
        if usage is None:
            self.unknown_usage_attempts += 1
        else:
            self.provider_input_tokens += usage["input_tokens"]
            self.provider_output_tokens += usage["output_tokens"]
        _append_event(
            self.journal_path,
            {
                "sequence": sequence,
                "event": "response-received",
                "response_sha256": response_sha,
                "provider_usage": usage,
            },
        )
        if usage is None:
            raise RuntimeError("provider usage is missing or malformed")
        if usage["input_tokens"] != tokens or usage["output_tokens"] > 2048:
            _append_event(
                self.journal_path,
                {
                    "sequence": sequence,
                    "event": "usage-out-of-contract",
                    "input_matches_local": usage["input_tokens"] == tokens,
                    "output_within_requested_cap": usage["output_tokens"] <= 2048,
                },
            )
            raise RuntimeError("provider usage exceeds or differs from registered geometry")
        return raw

    def usage_summary(self) -> dict[str, int]:
        return {
            "input_tokens": self.provider_input_tokens,
            "output_tokens": self.provider_output_tokens,
            "unknown_usage_attempts": self.unknown_usage_attempts,
        }


def run_guarded(
    *,
    source_root: Path,
    tokenizer_path: Path,
    run_dir: Path,
    transport_override: Transport | None = None,
) -> dict[str, object]:
    """Run a bounded development block; injected transport remains synthetic."""

    _private_dir(run_dir)
    _write_json(run_dir / "reservation.json", {"schema_version": 1, "status": "reserved"})
    _reserve_journal(run_dir / "attempts.jsonl")
    result: dict[str, object] = {
        "schema_version": 1,
        "scope": "r15-pep-paid-development",
        "status": "refused",
        "mode": "injected-test" if transport_override is not None else "live-siflow",
        "live_ready": False,
        "provider_block_valid": False,
        "qualified_parent": False,
        "task_provider_usage_total": None,
        "pre_canary_provider_usage": None,
        "post_canary_provider_usage": None,
    }
    journal: _JournalTransport | None = None
    try:
        launch, launch_sha = _read_launch_manifest()
        geometry = json.loads(_GEOMETRY_PATH.read_text())
        if not isinstance(geometry, dict):
            raise ValueError("PEP geometry is not an object")
        task_plan = geometry.get("local_worst_case_total_input_tokens")
        output_plan = geometry.get("profile_max_total_output_tokens")
        if (
            not isinstance(task_plan, int)
            or not isinstance(output_plan, int)
            or task_plan + output_plan != launch["task_local_plus_requested_ceiling"]
        ):
            raise ValueError("task requested-token ceiling differs from geometry")
        cases = build_pep_cases(source_root)
        profile = canary._profile()
        tokenizer = canary._tokenizer(tokenizer_path)
        # Authenticate committed geometry, source, tokenizer, profile and clean
        # producer before the credential is read or either canary is dispatched.
        _validate_registration(
            cases,
            profile,
            geometry,
            geometry_path=_GEOMETRY_PATH,
            source_root=source_root,
            tokenizer_path=tokenizer_path,
        )
        configured_endpoint = os.environ.get(profile.endpoint_env)
        if configured_endpoint is not None and configured_endpoint != canary.ENDPOINT:
            raise ValueError("configured endpoint differs from frozen URL")
        endpoint = (
            ResolvedAPIEndpoint(endpoint=canary.ENDPOINT, api_key="synthetic-test-key")
            if transport_override is not None
            else resolve_api_endpoint(profile, endpoint=canary.ENDPOINT)
        )
        if (
            endpoint.endpoint != canary.ENDPOINT
            or _sha(endpoint.endpoint.encode()) != launch["endpoint_sha256"]
        ):
            raise ValueError("resolved endpoint differs from launch registration")
        _write_json(
            run_dir / "identity.json",
            {
                "launch_manifest_sha256": launch_sha,
                "geometry_sha256": _sha(_GEOMETRY_PATH.read_bytes()),
                "canary_registration_sha256": canary.registration_sha256(),
                "endpoint_sha256": launch["endpoint_sha256"],
                "profile_sha256": profile.profile_hash,
                "source_revision": geometry["source_identity"]["revision"],
                "tokenizer_manifest_sha256": geometry["tokenizer"]["manifest_sha256"],
                "runner_sha256": launch["runner_script_sha256"],
                "canary_script_sha256": launch["canary_script_sha256"],
                "max_task_calls": launch["task_call_cap"],
                "max_global_calls": launch["global_call_cap"],
                "local_plus_requested_token_ceiling": launch["global_local_plus_requested_ceiling"],
                "auxiliary_call_cap": 0,
            },
        )
        base = transport_override if transport_override is not None else _urlopen_transport
        journal = _JournalTransport(
            base=base,
            journal_path=run_dir / "attempts.jsonl",
            geometry=geometry,
            manifest=launch,
        )
        pre = canary.run_canary(
            profile=profile,
            endpoint=endpoint,
            tokenizer=tokenizer,
            transport=journal,
            synthetic=transport_override is not None,
        )
        _write_json(run_dir / "pre_canary.json", pre)
        result["pre_canary_provider_usage"] = (
            None if transport_override is not None else pre.get("provider_usage_total")
        )
        if pre.get("status") != "passed":
            result["status"] = "pre-canary-failed"
        else:
            journal.phase = "task"
            task_input_before = journal.provider_input_tokens
            task_output_before = journal.provider_output_tokens
            task_unknown_before = journal.unknown_usage_attempts
            task = run_pep_screen(
                cases,
                profile=profile,
                endpoint=endpoint,
                geometry_report=geometry,
                geometry_path=_GEOMETRY_PATH,
                source_root=source_root,
                tokenizer_path=tokenizer_path,
                transport=journal,
            )
            _write_json(run_dir / "task.json", task)
            result["task_status"] = task.get("status")
            result["task_provider_usage_total"] = (
                None if transport_override is not None else task.get("provider_usage_total")
            )
            observed_task_usage = {
                "input_tokens": journal.provider_input_tokens - task_input_before,
                "output_tokens": journal.provider_output_tokens - task_output_before,
                "unknown_usage_attempts": journal.unknown_usage_attempts - task_unknown_before,
            }
            if (
                task.get("worker_attempt_count") != journal.task_attempts
                or task.get("provider_usage_total") != observed_task_usage
            ):
                raise RuntimeError("task worker attempts or usage differ from transport journal")
            if task.get("status") == "stopped-on-worker-failure":
                result["status"] = "task-worker-failed"
            elif journal.unknown_usage_attempts:
                result["status"] = "usage-unverified"
            else:
                journal.phase = "post-canary"
                post = canary.run_canary(
                    profile=profile,
                    endpoint=endpoint,
                    tokenizer=tokenizer,
                    transport=journal,
                    synthetic=transport_override is not None,
                )
                _write_json(run_dir / "post_canary.json", post)
                result["post_canary_provider_usage"] = (
                    None if transport_override is not None else post.get("provider_usage_total")
                )
                result["status"] = (
                    "completed-development-screen"
                    if post.get("status") == "passed"
                    and task.get("status") == "completed-development-screen"
                    else "stopped-on-full-task-failure"
                    if post.get("status") == "passed"
                    else "post-canary-failed"
                )
                if result["status"] == "completed-development-screen":
                    if (
                        journal.task_attempts != MAX_WORKER_ATTEMPTS
                        or journal.canary_attempts != 2
                        or journal.attempts != launch["global_call_cap"]
                    ):
                        raise RuntimeError("completed block lacks all registered provider calls")
                    _read_launch_manifest()
                    _validate_registration(
                        cases,
                        profile,
                        geometry,
                        geometry_path=_GEOMETRY_PATH,
                        source_root=source_root,
                        tokenizer_path=tokenizer_path,
                    )
        result["provider_block_valid"] = (
            result["status"] == "completed-development-screen" and transport_override is None
        )
        if transport_override is not None and result["status"] == "completed-development-screen":
            result["status"] = "completed-synthetic-screen"
    except Exception as exc:
        result["status"] = "refused-or-interrupted"
        result["failure_type"] = type(exc).__name__
    finally:
        if journal is not None:
            result["attempted_http_calls"] = journal.attempts
            result["task_http_calls"] = journal.task_attempts
            result["canary_http_calls"] = journal.canary_attempts
            result["local_plus_requested_tokens"] = journal.planned_tokens
            result["all_provider_usage"] = (
                None if transport_override is not None else journal.usage_summary()
            )
            result["synthetic_usage"] = (
                journal.usage_summary() if transport_override is not None else None
            )
        _write_json(run_dir / "final.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tokenizer-path", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_guarded(
        source_root=args.source_root,
        tokenizer_path=args.tokenizer_path,
        run_dir=args.run_dir,
    )
    print(json.dumps({"status": result["status"], "run_dir": str(args.run_dir)}, sort_keys=True))
    return 0 if result["status"] == "completed-development-screen" else 2


if __name__ == "__main__":
    raise SystemExit(main())
