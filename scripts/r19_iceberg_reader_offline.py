"""R19 Iceberg prospective reader: bounded offline synthetic chain only.

This runner never resolves credentials or uses a network transport. Its sealed
synthetic transport exercises the frozen Qwen request envelope, private fsynced
journal, two canaries and two-session reader loop.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import audit_r18_iceberg_geometry as r18_geometry  # noqa: E402
import r15_exact_profile_canary as canary  # noqa: E402
import r15_pep_paid_runner as journal_tools  # noqa: E402

from rsicontext.analysis.chat_geometry import ChatTokenizer, measure_chat_geometry  # noqa: E402
from rsicontext.analysis.iceberg_fixed_reader_r19 import (  # noqa: E402
    RULE_BUNDLES,
    IcebergFixedHook,
    parse_rule,
)
from rsicontext.analysis.otel_siflow_pilot import _Worker  # noqa: E402
from rsicontext.experiment.api import APIProfile, ResolvedAPIEndpoint  # noqa: E402
from rsicontext.lifecycle.env import ProjectState  # noqa: E402
from rsicontext.lifecycle.material_iceberg_row_scan import (  # noqa: E402
    Case,
    build_iceberg_row_scan_sessions,
)
from rsicontext.lifecycle.session_sequence import run_session_sequence  # noqa: E402
from rsicontext.lifecycle.spec import canonical_instance_json  # noqa: E402
from rsicontext.lifecycle.tools import DocumentRegistry  # noqa: E402

CASE_ORDER: tuple[Case, ...] = (
    "authentic-pack",
    "constructed-file-sequence",
    "source-free",
    "identity-only",
)
TASK_CALL_CAP = 8
CANARY_CALL_CAP = 2
GLOBAL_CALL_CAP = TASK_CALL_CAP + CANARY_CALL_CAP
R18_GEOMETRY_PATH = ROOT / "docs/reviews/r18-iceberg-geometry.json"
R18_GEOMETRY_SHA256 = "aec96c97e921163431f306728c5469ce8e9673186a73f19b0de46f90afa35448"
REGISTRY_SHA256 = "7ac3a92dcbf9128c2b39ef16978bb9d08854612a85126b98165f62ecd8a9c1a0"
_GEOMETRY_REL = "configs/r19_iceberg_reader_geometry_v1.json"
_LAUNCH_REL = "configs/r19_iceberg_reader_launch_v1.json"
_BOUND_FILES = (
    "scripts/r19_iceberg_reader_offline.py",
    "src/rsicontext/analysis/iceberg_fixed_reader_r19.py",
    "scripts/audit_r18_iceberg_geometry.py",
    "src/rsicontext/lifecycle/material_iceberg_row_scan.py",
    "src/rsicontext/lifecycle/session_sequence.py",
    "src/rsicontext/analysis/otel_siflow_pilot.py",
    "src/rsicontext/experiment/api.py",
    "scripts/r15_exact_profile_canary.py",
    "scripts/r15_pep_paid_runner.py",
    "configs/r15_siflow_fixed_reader_profile_v1.json",
    "configs/registry.json",
    "uv.lock",
)
_FAULTS = frozenset(
    ("mixed-first", "missing-usage-first", "wrong-model-first", "non-stop-first", "authentic-wrong")
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _committed_bytes(relative: str) -> bytes:
    return subprocess.run(  # nosec B603, B607
        ["git", "-C", str(ROOT), "show", f"HEAD:{relative}"],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout


def _read_frozen_registration() -> tuple[dict[str, object], dict[str, object]]:
    """Require clean committed producer, exact launch bytes and registered requests."""

    status = subprocess.run(  # nosec B603, B607
        ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
        check=True,
        capture_output=True,
        timeout=10,
    ).stdout
    if status:
        raise ValueError("R19 producer worktree is not clean")
    geometry_bytes = (ROOT / _GEOMETRY_REL).read_bytes()
    launch_bytes = (ROOT / _LAUNCH_REL).read_bytes()
    if geometry_bytes != _committed_bytes(_GEOMETRY_REL) or launch_bytes != _committed_bytes(
        _LAUNCH_REL
    ):
        raise ValueError("R19 geometry or launch differs from committed HEAD")
    launch = json.loads(launch_bytes)
    required = {
        "schema_version", "scope", "geometry_sha256", "registry_sha256",
        "profile_sha256", "endpoint_sha256", "canary_registration_sha256",
        "task_call_cap", "canary_call_cap", "global_call_cap", "auxiliary_call_cap",
        "task_local_plus_requested_ceiling", "global_local_plus_requested_ceiling",
        "bound_file_sha256", "live_enabled",
    }
    if not isinstance(launch, dict) or set(launch) != required or (
        launch["schema_version"] != 1
        or launch["scope"] != "r19-iceberg-prospective-fixed-reader-offline"
        or launch["live_enabled"] is not False
        or launch["geometry_sha256"] != _sha(geometry_bytes)
    ):
        raise ValueError("R19 frozen launch identity differs")
    bound = launch["bound_file_sha256"]
    if not isinstance(bound, dict) or set(bound) != set(_BOUND_FILES):
        raise ValueError("R19 bound producer set differs")
    for relative in _BOUND_FILES:
        raw = (ROOT / relative).read_bytes()
        if raw != _committed_bytes(relative) or bound[relative] != _sha(raw):
            raise ValueError(f"R19 producer differs from launch: {relative}")
    registration = json.loads(geometry_bytes)
    if not isinstance(registration, dict):
        raise ValueError("R19 geometry is not an object")
    fields = (
        "registry_sha256", "profile_sha256", "endpoint_sha256",
        "canary_registration_sha256", "task_call_cap", "canary_call_cap",
        "global_call_cap", "auxiliary_call_cap", "task_local_plus_requested_ceiling",
        "global_local_plus_requested_ceiling",
    )
    if any(launch[name] != registration.get(name) for name in fields):
        raise ValueError("R19 launch and geometry disagree")
    return registration, launch


def _request(profile: APIProfile, prompt: str) -> dict[str, object]:
    if not profile.system_prompt or profile.chat_template_enable_thinking is not False:
        raise ValueError("Iceberg reader requires the frozen non-thinking system profile")
    return {
        "max_tokens": profile.max_output_tokens,
        "messages": [
            {"role": "system", "content": profile.system_prompt},
            {"role": "user", "content": prompt},
        ],
        "model": profile.model,
        "seed": profile.seed,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }


@dataclass(slots=True)
class SyntheticTransport:
    """Local fixed SSE generator; no network transport is accepted by the runner."""

    profile: APIProfile
    tokenizer: ChatTokenizer
    fault: str | None = None
    calls: int = 0
    task_calls: int = 0

    def __post_init__(self) -> None:
        if self.fault is not None and self.fault not in _FAULTS:
            raise ValueError("unregistered R19 synthetic fault")

    def __call__(self, request: urllib.request.Request, timeout: float) -> bytes:
        del timeout
        if not isinstance(request.data, bytes):
            raise ValueError("synthetic R19 request has no body")
        body = json.loads(request.data)
        if not isinstance(body, dict) or body.get("model") != self.profile.model:
            raise ValueError("synthetic R19 request differs from profile")
        messages = body.get("messages")
        if (
            not isinstance(messages, list)
            or len(messages) != 2
            or messages[0] != {"role": "system", "content": self.profile.system_prompt}
            or not isinstance(messages[1], dict)
            or not isinstance(messages[1].get("content"), str)
        ):
            raise ValueError("synthetic R19 messages differ from profile")
        prompt = messages[1]["content"]
        self.calls += 1
        if prompt == canary.PROMPT:
            return canary._fake_transport(self.profile, self.tokenizer)(request, 0.0)
        self.task_calls += 1
        if "[[doc:reference-source]]" in prompt:
            if "[SOURCE WITHHELD]" in prompt:
                answer = RULE_BUNDLES[2]
            elif "file sequence number is _strictly less than_" in prompt:
                answer = RULE_BUNDLES[1]
            else:
                answer = RULE_BUNDLES[0]
            if self.fault == "mixed-first" and self.task_calls == 1:
                answer = (
                    "counter=data; bound=unknown; partition=same-or-global; row=all-equality-ids"
                )
            if self.fault == "authentic-wrong" and self.task_calls == 1:
                answer = RULE_BUNDLES[1]
        elif prompt.startswith("Retained source rule: "):
            answer = "plan=emit-row" if RULE_BUNDLES[1] in prompt else "plan=suppress-row"
        else:
            raise ValueError("synthetic R19 transport received unregistered prompt")
        geometry = measure_chat_geometry(self.tokenizer, messages, enable_thinking=False)
        input_tokens = geometry["rendered_input_tokens"]
        output_tokens = len(
            self.tokenizer(answer, add_special_tokens=False, return_offsets_mapping=True)[
                "input_ids"
            ]
        )
        if not isinstance(input_tokens, int) or output_tokens < 1:
            raise ValueError("synthetic R19 tokenization failed")
        identity = {
            "id": f"offline-r19-{self.calls}",
            "model": "Unregistered/Model"
            if self.fault == "wrong-model-first" and self.task_calls == 1
            else self.profile.model,
        }
        content = {
            **identity,
            "choices": [
                {
                    "delta": {"content": answer},
                    "finish_reason": "length"
                    if self.fault == "non-stop-first" and self.task_calls == 1
                    else "stop",
                }
            ],
        }
        usage = {
            **identity,
            "choices": [],
            "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
        }
        events = ["data: " + json.dumps(content)]
        if not (self.fault == "missing-usage-first" and self.task_calls == 1):
            events.append("data: " + json.dumps(usage))
        events.append("data: [DONE]")
        return ("\n\n".join(events) + "\n\n").encode()


def _entry(
    profile: APIProfile,
    *,
    stage: str,
    owner: str,
    prompt: str,
    r18_row: dict[str, object],
) -> dict[str, object]:
    messages = _request(profile, prompt)["messages"]
    count = _input_count(r18_row)
    if (
        _sha(_canonical(messages)) != r18_row.get("messages_sha256")
        or r18_row.get("fits_32k") is not True
    ):
        raise ValueError("R19 prompt differs from R18 final-chat geometry")
    return {
        "stage": stage,
        "owner": owner,
        "prompt_sha256": _sha(prompt.encode()),
        "request_sha256": _sha(_canonical(_request(profile, prompt))),
        "messages_sha256": r18_row["messages_sha256"],
        "local_template_geometry": {"rendered_input_tokens": count},
    }


def _input_count(row: dict[str, object]) -> int:
    count = row.get("input_tokens")
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        raise ValueError("R18 row lacks a positive input token count")
    return count


def build_registration(source_root: Path, tokenizer_root: Path) -> dict[str, object]:
    """Recompute source, profile, tokenizer and all seven exact API requests."""

    if _sha(R18_GEOMETRY_PATH.read_bytes()) != R18_GEOMETRY_SHA256:
        raise ValueError("R18 geometry artifact changed")
    if _sha((ROOT / "configs/registry.json").read_bytes()) != REGISTRY_SHA256:
        raise ValueError("R19 registry differs from pinned post-Gemma intake")
    actual = r18_geometry.audit(
        source_root, tokenizer_root, ROOT / "configs/r15_siflow_fixed_reader_profile_v1.json"
    )
    expected = json.loads(R18_GEOMETRY_PATH.read_text())
    if actual != expected:
        raise ValueError("R18 source, profile, tokenizer or prompt geometry changed")
    profile = canary._profile()
    first = cast(dict[str, dict[str, object]], actual["session_1"])
    second = cast(dict[str, dict[str, object]], actual["session_2_by_retained_rule"])
    if set(first) != set(CASE_ORDER) or set(second) != set(RULE_BUNDLES):
        raise ValueError("R18 geometry case or carry set changed")
    entries: list[dict[str, object]] = []
    worlds: dict[str, list[str]] = {}
    for case in CASE_ORDER:
        pair = build_iceberg_row_scan_sessions(source_root, case=case)
        worlds[case] = [_sha(canonical_instance_json(item).encode()) for item in pair]
        prompt = r18_geometry.survey_user(pair[0].stages[0].documents[0].text)
        entries.append(
            _entry(profile, stage="survey", owner=case, prompt=prompt, r18_row=first[case])
        )
    request = build_iceberg_row_scan_sessions(source_root, case="authentic-pack")[1]
    request_text = request.stages[1].documents[0].text
    for bundle in RULE_BUNDLES:
        prompt = r18_geometry.decision_user(request_text, bundle)
        entries.append(
            _entry(profile, stage="decision", owner=bundle, prompt=prompt, r18_row=second[bundle])
        )
    request_hashes = [entry["request_sha256"] for entry in entries]
    if len(entries) != 7 or len(set(request_hashes)) != 7:
        raise ValueError("Iceberg request registration is not seven unique payloads")
    survey_tokens = sum(_input_count(first[case]) for case in CASE_ORDER)
    later_max = max(_input_count(second[bundle]) for bundle in RULE_BUNDLES)
    task_input_cap = survey_tokens + len(CASE_ORDER) * later_max
    task_ceiling = task_input_cap + TASK_CALL_CAP * profile.max_output_tokens
    global_ceiling = task_ceiling + CANARY_CALL_CAP * (
        canary.EXPECTED_INPUT_TOKENS + profile.max_output_tokens
    )
    if (task_input_cap, task_ceiling, global_ceiling) != (51448, 67832, 72052):
        raise ValueError("R19 prospective call or token envelope changed")
    return {
        "schema_version": 1,
        "scope": "r19-iceberg-prospective-fixed-reader-offline",
        "qualified_parent": False,
        "r18_geometry_sha256": R18_GEOMETRY_SHA256,
        "registry_sha256": REGISTRY_SHA256,
        "source": actual["source"],
        "source_git": actual["source_git"],
        "world_sha256": worlds,
        "profile_sha256": profile.profile_hash,
        "tokenizer_files_sha256": actual["tokenizer_files_sha256"],
        "tokenizer_runtime": actual["runtime_versions"],
        "endpoint_sha256": _sha(canary.ENDPOINT.encode()),
        "canary_registration_sha256": canary.registration_sha256(),
        "case_order": list(CASE_ORDER),
        "registered_requests": entries,
        "task_call_cap": TASK_CALL_CAP,
        "task_local_worst_case_input_tokens": task_input_cap,
        "task_local_plus_requested_ceiling": task_ceiling,
        "canary_call_cap": CANARY_CALL_CAP,
        "global_call_cap": GLOBAL_CALL_CAP,
        "global_local_plus_requested_ceiling": global_ceiling,
        "auxiliary_call_cap": 0,
    }


class _NoRereadRegistry(DocumentRegistry):
    def get(self, doc_id: str) -> None:
        raise RuntimeError(f"R19 fixed reader must not reread documents: {doc_id}")


def _task_block(
    source_root: Path,
    *,
    profile: APIProfile,
    endpoint: ResolvedAPIEndpoint,
    registration: dict[str, object],
    journal: journal_tools._JournalTransport,
) -> dict[str, object]:
    requested = registration.get("registered_requests")
    if not isinstance(requested, list) or len(requested) != 7:
        raise ValueError("R19 registration lacks seven exact requests")
    indexed: dict[str, dict[str, object]] = {}
    for item in requested:
        if not isinstance(item, dict):
            raise ValueError("invalid R19 request registration")
        digest = item.get("prompt_sha256")
        if not isinstance(digest, str) or digest in indexed:
            raise ValueError("duplicate R19 prompt registration")
        indexed[digest] = item
    active_case = ""
    active_stage = ""
    active_bundle = ""

    def preflight(prompt: str) -> dict[str, object]:
        item = indexed.get(_sha(prompt.encode()))
        if item is None or item.get("stage") != active_stage:
            raise ValueError("R19 reader prompt is unregistered or out of stage order")
        if active_stage == "survey" and item.get("owner") != active_case:
            raise ValueError("R19 source prompt belongs to another arm")
        if active_stage == "decision" and item.get("owner") != active_bundle:
            raise ValueError("R19 decision prompt differs from actual S1 carry")
        return {
            "stage": active_stage,
            "prompt_sha256": item["prompt_sha256"],
            "request_sha256": item["request_sha256"],
            "local_template_geometry": item["local_template_geometry"],
        }

    worker = _Worker(profile, endpoint, preflight, journal)
    cases: list[dict[str, object]] = []
    terminal_failure: str | None = None
    for case in CASE_ORDER:
        active_case = case
        active_bundle = ""
        pair = build_iceberg_row_scan_sessions(source_root, case=case)
        env = ProjectState()
        session_count = 0
        start = len(worker.attempts)

        def factory(state: dict[str, object]) -> IcebergFixedHook:
            nonlocal session_count, active_stage, active_bundle
            active_stage = "survey" if session_count == 0 else "decision"
            if session_count == 1:
                carry = state.get("carry")
                if not isinstance(carry, dict) or set(carry) != {"rule"}:
                    raise ValueError("R19 S2 carry is absent or unbounded")
                active_bundle = parse_rule(carry["rule"])
            session_count += 1
            return IcebergFixedHook(
                state, worker, r18_geometry.survey_user, r18_geometry.decision_user
            )

        try:
            sequence = run_session_sequence(
                list(pair),
                factory,
                envs=[env, env],
                registry=_NoRereadRegistry(),
                max_turns_per_stage=2,
            )
            passed = [record.passed for record in sequence.sessions]
            calls = [record.model_calls for record in sequence.sessions]
            if calls != [1, 1] or len(worker.attempts) - start != 2:
                raise RuntimeError("R19 case did not use one target call per session")
            first_reply = worker.attempts[start].get("reply")
            if not isinstance(first_reply, str):
                raise RuntimeError("R19 S1 attempt lacks raw reader answer")
            expected_bundle = (
                RULE_BUNDLES[1] if case == "constructed-file-sequence" else RULE_BUNDLES[0]
            )
            expected_plan = "emit-row" if case == "constructed-file-sequence" else "suppress-row"
            final_plan = env.records.get("row_scan_decision", {}).get("plan")
            observed_rule = parse_rule(first_reply)
            source_bearing = case in CASE_ORDER[:2]
            cases.append(
                {
                    "case": case,
                    "session_passed": passed,
                    "session_failures": [record.failures for record in sequence.sessions],
                    "model_calls": calls,
                    "observed_s1_bundle": observed_rule,
                    "observed_s1_carry": sequence.sessions[0].final_carry,
                    "source_rule_extraction_matches_oracle": observed_rule == expected_bundle
                    if source_bearing
                    else None,
                    "control_prior_rule_match": observed_rule == RULE_BUNDLES[0]
                    if not source_bearing
                    else None,
                    "control_shortcut_completion": passed == [True, True]
                    if not source_bearing
                    else None,
                    "s2_plan_correct": final_plan == expected_plan,
                    "final_plan": final_plan,
                    "worker_attempt_indexes": list(range(start, len(worker.attempts))),
                }
            )
        except Exception as exc:
            observed_bundle: str | None = None
            if len(worker.attempts) > start:
                raw = worker.attempts[start].get("reply")
                if isinstance(raw, str) and raw.strip() in RULE_BUNDLES:
                    observed_bundle = raw.strip()
            expected_bundle = (
                RULE_BUNDLES[1] if case == "constructed-file-sequence" else RULE_BUNDLES[0]
            )
            source_bearing = case in CASE_ORDER[:2]
            cases.append(
                {
                    "case": case,
                    "session_passed": None,
                    "source_rule_extraction_matches_oracle": observed_bundle == expected_bundle
                    if source_bearing and observed_bundle is not None
                    else None,
                    "control_prior_rule_match": observed_bundle == RULE_BUNDLES[0]
                    if not source_bearing and observed_bundle is not None
                    else None,
                    "control_shortcut_completion": None,
                    "observed_s1_bundle": observed_bundle,
                    "observed_s1_carry": {"rule": observed_bundle}
                    if observed_bundle is not None
                    else None,
                    "s2_plan_correct": None,
                    "model_calls_observed": len(worker.attempts) - start,
                    "failure_type": type(exc).__name__,
                    "worker_attempt_indexes": list(range(start, len(worker.attempts))),
                }
            )
            terminal_failure = type(exc).__name__
            break
    return {
        "schema_version": 1,
        "scope": "r19-iceberg-prospective-fixed-reader-offline",
        "status": "completed-synthetic-screen"
        if terminal_failure is None and len(cases) == len(CASE_ORDER)
        else "stopped-on-task-failure",
        "cases": cases,
        "executed_arms": [item["case"] for item in cases],
        "failure_type": terminal_failure,
        "task_attempts": len(worker.attempts),
        "attempts": worker.attempts,
        "qualified_parent": False,
    }


def run_offline_screen(
    *,
    source_root: Path,
    tokenizer_root: Path,
    run_dir: Path,
    fault: str | None = None,
) -> dict[str, object]:
    """Reserve private evidence then run canary + bounded synthetic tasks."""

    journal_tools._private_dir(run_dir)
    journal_tools._write_json(
        run_dir / "reservation.json", {"schema_version": 1, "status": "reserved"}
    )
    journal_tools._reserve_journal(run_dir / "attempts.jsonl")
    result: dict[str, object] = {
        "schema_version": 1,
        "scope": "r19-iceberg-prospective-fixed-reader-offline",
        "status": "refused",
        "provider_usage_total": None,
        "qualified_parent": False,
        "live_ready": False,
        "auxiliary_calls": 0,
    }
    journal: journal_tools._JournalTransport | None = None
    try:
        frozen, launch = _read_frozen_registration()
        registration = build_registration(source_root, tokenizer_root)
        if registration != frozen:
            raise ValueError("R19 source, tokenizer or request geometry differs from frozen launch")
        profile = canary._profile()
        tokenizer = canary._tokenizer(tokenizer_root)
        transport = SyntheticTransport(profile, tokenizer, fault)
        manifest = {
            key: registration[key]
            for key in (
                "task_call_cap",
                "task_local_plus_requested_ceiling",
                "canary_call_cap",
                "global_call_cap",
                "global_local_plus_requested_ceiling",
            )
        }
        endpoint = ResolvedAPIEndpoint(endpoint=canary.ENDPOINT, api_key="synthetic-only-key")
        journal_tools._write_json(
            run_dir / "identity.json",
            {
                "registration_sha256": _sha(_canonical(registration)),
                "registry_sha256": registration["registry_sha256"],
                "source": registration["source"],
                "source_git": registration["source_git"],
                "world_sha256": registration["world_sha256"],
                "profile_sha256": registration["profile_sha256"],
                "tokenizer_files_sha256": registration["tokenizer_files_sha256"],
                "tokenizer_runtime": registration["tokenizer_runtime"],
                "task_call_cap": TASK_CALL_CAP,
                "global_call_cap": GLOBAL_CALL_CAP,
                "auxiliary_call_cap": 0,
                "producer_status": "clean-committed-and-launch-bound; synthetic-only",
                "launch_sha256": _sha((ROOT / _LAUNCH_REL).read_bytes()),
                "geometry_sha256": launch["geometry_sha256"],
            },
        )
        journal_tools._sync_directory(run_dir)
        registered = cast(list[dict[str, object]], registration["registered_requests"])
        journal = journal_tools._JournalTransport(
            base=transport,
            journal_path=run_dir / "attempts.jsonl",
            geometry={
                "registered_requests": {str(item["prompt_sha256"]): item for item in registered}
            },
            manifest=manifest,
        )
        pre = canary.run_canary(
            profile=profile,
            endpoint=endpoint,
            tokenizer=tokenizer,
            transport=journal,
            synthetic=True,
        )
        journal_tools._write_json(run_dir / "pre_canary.json", pre)
        journal_tools._sync_directory(run_dir)
        if pre["status"] != "passed":
            result["status"] = "pre-canary-failed"
        else:
            journal.phase = "task"
            before = journal.usage_summary()
            task = _task_block(
                source_root,
                profile=profile,
                endpoint=endpoint,
                registration=registration,
                journal=journal,
            )
            journal_tools._write_json(run_dir / "task.json", task)
            journal_tools._sync_directory(run_dir)
            result["synthetic_task_usage"] = {
                key: journal.usage_summary()[key] - before[key]
                for key in ("input_tokens", "output_tokens", "unknown_usage_attempts")
            }
            if journal.usage_summary()["unknown_usage_attempts"]:
                result["status"] = "usage-unverified"
            elif task["status"] != "completed-synthetic-screen":
                result["status"] = "task-failed"
            else:
                journal.phase = "post-canary"
                post = canary.run_canary(
                    profile=profile,
                    endpoint=endpoint,
                    tokenizer=tokenizer,
                    transport=journal,
                    synthetic=True,
                )
                journal_tools._write_json(run_dir / "post_canary.json", post)
                journal_tools._sync_directory(run_dir)
                result["status"] = (
                    "completed-synthetic-screen"
                    if post["status"] == "passed"
                    else "post-canary-failed"
                )
                global_cap = registration["global_local_plus_requested_ceiling"]
                if not isinstance(global_cap, int):
                    raise ValueError("R19 global planning cap is invalid")
                if result["status"] == "completed-synthetic-screen" and (
                    journal.task_attempts != TASK_CALL_CAP
                    or journal.canary_attempts != CANARY_CALL_CAP
                    or journal.attempts != GLOBAL_CALL_CAP
                    or journal.planned_tokens > global_cap
                ):
                    raise RuntimeError("completed R19 chain lacks registered calls or token cap")
    except Exception as exc:
        result["status"] = "refused-or-interrupted"
        result["failure_type"] = type(exc).__name__
    finally:
        if journal is not None:
            result["attempted_http_calls"] = journal.attempts
            result["task_http_calls"] = journal.task_attempts
            result["canary_http_calls"] = journal.canary_attempts
            result["local_plus_requested_tokens"] = journal.planned_tokens
            result["synthetic_usage"] = journal.usage_summary()
            result["synthetic_transport_calls"] = transport.calls
        journal_tools._write_json(run_dir / "final.json", result)
        journal_tools._sync_directory(run_dir)
    return result


__all__ = ["CASE_ORDER", "TASK_CALL_CAP", "build_registration", "run_offline_screen"]
