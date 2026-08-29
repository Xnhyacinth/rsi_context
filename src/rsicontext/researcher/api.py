"""Stateless OpenAI-compatible researcher that emits audited policy artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, cast

from rsicontext.artifacts import Manifest, ManifestError
from rsicontext.eval.openai_compatible import OpenAICompatibleReader, Transport
from rsicontext.experiment.api import APIProfile, load_api_profiles, resolve_api_endpoint
from rsicontext.researcher.commands import CommandSpec, ResearcherRequest
from rsicontext.security import PolicyAuditor, PolicySecurityError

API_RESEARCHER_SYSTEM_PROMPT: Final = (
    "You are the context-policy researcher, not the question-answering reader. "
    "Return exactly one JSON object with schema_version=1, policy_source containing the full "
    "Python source for policy/policy.py, and manifest containing the complete researcher "
    "manifest. Do not use Markdown fences, commentary, tool calls, or additional fields. "
    "Do not answer any benchmark question. Generalize only from the visible research feedback."
)
_RESPONSE_FIELDS: Final = {"manifest", "policy_source", "schema_version"}
_MAX_POLICY_SOURCE_BYTES: Final = 256 * 1024


class APIResearcherError(RuntimeError):
    """Raised when an API researcher violates its frozen artifact protocol."""


@dataclass(frozen=True, slots=True)
class APIResearcherArtifact:
    """One fully parsed policy and researcher manifest returned by the API."""

    policy_source: str
    manifest: Manifest

    @classmethod
    def from_response(cls, response: str) -> APIResearcherArtifact:
        """Parse one strict JSON response without accepting Markdown or coercions."""
        try:
            raw: object = json.loads(
                response,
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except (json.JSONDecodeError, UnicodeError, ValueError) as error:
            raise APIResearcherError("API researcher response is not valid JSON") from error
        if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
            raise APIResearcherError("API researcher response root must be an object")
        if set(raw) != _RESPONSE_FIELDS:
            raise APIResearcherError("API researcher response fields do not match the protocol")
        if raw.get("schema_version") != 1:
            raise APIResearcherError("API researcher schema_version must be 1")
        source = raw.get("policy_source")
        if not isinstance(source, str) or not source.strip() or "\x00" in source:
            raise APIResearcherError("policy_source must be non-empty UTF-8 text")
        if len(source.encode()) > _MAX_POLICY_SOURCE_BYTES:
            raise APIResearcherError("policy_source exceeds the byte limit")
        manifest_raw = raw.get("manifest")
        if not isinstance(manifest_raw, dict):
            raise APIResearcherError("manifest must be an object")
        try:
            manifest = Manifest.from_dict(cast(dict[str, object], manifest_raw))
        except ManifestError as error:
            raise APIResearcherError("API researcher manifest is invalid") from error
        return cls(policy_source=source, manifest=manifest)

    def write_workspace(self, workspace: Path) -> None:
        """Validate completely, then replace only policy and manifest submission paths."""
        if workspace.is_symlink() or not workspace.is_dir():
            raise APIResearcherError("researcher workspace must be a regular directory")
        policy_directory = workspace / "policy"
        manifest_path = workspace / "manifest.json"
        if policy_directory.is_symlink() or not policy_directory.is_dir():
            raise APIResearcherError("researcher policy directory must be a regular directory")
        if manifest_path.exists() or manifest_path.is_symlink():
            raise APIResearcherError("researcher manifest path must not already exist")
        for entry in policy_directory.rglob("*"):
            if entry.is_symlink() or (entry.is_file() and entry.suffix != ".py"):
                raise APIResearcherError("existing policy tree contains an unsafe entry")
        try:
            PolicyAuditor().enforce_source(
                self.policy_source,
                filename=str(policy_directory.resolve() / "policy.py"),
            )
        except PolicySecurityError as error:
            raise APIResearcherError("policy audit rejected the API researcher artifact") from error

        manifest_payload = (
            json.dumps(
                self.manifest.to_dict(),
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        shutil.rmtree(policy_directory)
        policy_directory.mkdir()
        (policy_directory / "policy.py").write_text(self.policy_source, encoding="utf-8")
        with manifest_path.open("x", encoding="utf-8") as handle:
            handle.write(manifest_payload)


@dataclass(frozen=True, slots=True)
class APIResearcherTurnResult:
    """Credential-free identity, usage, and latency for one researcher call."""

    profile_id: str
    profile_hash: str
    requested_model: str
    response_model: str
    response_id: str
    system_prompt_sha256: str
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def api_researcher_system_prompt_hash() -> str:
    """Return the role prompt identity included in every researcher run."""
    return hashlib.sha256(API_RESEARCHER_SYSTEM_PROMPT.encode()).hexdigest()


def run_api_researcher_turn(
    *,
    profile: APIProfile,
    endpoint: str,
    api_key: str,
    prompt: str,
    workspace: Path,
    timeout_seconds: float = 300.0,
    transport: Transport | None = None,
    timer: Callable[[], float] = time.perf_counter,
) -> APIResearcherTurnResult:
    """Request, validate, and materialize exactly one stateless researcher artifact."""
    kwargs: dict[str, Any] = {}
    if transport is not None:
        kwargs["transport"] = transport
    client = OpenAICompatibleReader(
        endpoint=endpoint,
        model=profile.model,
        max_tokens=profile.max_output_tokens,
        max_model_len=profile.evaluation_max_model_len,
        seed=profile.seed,
        stream=True,
        chat_template_enable_thinking=profile.chat_template_enable_thinking,
        require_response_model=True,
        timeout_seconds=timeout_seconds,
        allowed_hosts=(profile.allowed_host,),
        system_prompt=API_RESEARCHER_SYSTEM_PROMPT,
        api_key=api_key,
        **kwargs,
    )
    before = timer()
    output = client.complete(prompt)
    elapsed = timer() - before
    if not math.isfinite(elapsed) or elapsed < 0:
        raise APIResearcherError("API researcher timer returned an invalid duration")
    if output.response_model is None or output.response_id is None:
        raise APIResearcherError("API researcher response identity is missing")
    APIResearcherArtifact.from_response(output.answer).write_workspace(workspace)
    return APIResearcherTurnResult(
        profile_id=profile.id,
        profile_hash=profile.profile_hash,
        requested_model=profile.model,
        response_model=output.response_model,
        response_id=output.response_id,
        system_prompt_sha256=api_researcher_system_prompt_hash(),
        input_tokens=output.input_tokens,
        output_tokens=output.output_tokens,
        elapsed_seconds=elapsed,
    )


@dataclass(frozen=True, slots=True)
class APIResearcherCommandBuilder:
    """Build the bounded local worker used to make one API researcher call."""

    python_executable: Path
    profiles_path: Path
    profile_id: str

    def __post_init__(self) -> None:
        python = self.python_executable.absolute()
        profiles = self.profiles_path.resolve(strict=True)
        if not python.is_file() or (python.is_symlink() and not python.resolve().is_file()):
            raise APIResearcherError("researcher Python executable must resolve to a file")
        if not profiles.is_file():
            raise APIResearcherError("researcher executable and profiles must be regular files")
        load_api_profiles(profiles).get(self.profile_id)
        object.__setattr__(self, "python_executable", python)
        object.__setattr__(self, "profiles_path", profiles)

    def build(self, request: ResearcherRequest) -> CommandSpec:
        """Return an inert worker command; the visible prompt remains on stdin."""
        profile = load_api_profiles(self.profiles_path).get(self.profile_id)
        if request.max_budget_usd is not None:
            raise APIResearcherError("API researcher does not accept a CLI dollar budget")
        if request.model is not None and request.model != profile.model:
            raise APIResearcherError("researcher request model does not match its API profile")
        return CommandSpec(
            argv=(
                str(self.python_executable),
                "-m",
                "rsicontext.researcher.api",
                "--profiles",
                str(self.profiles_path),
                "--profile-id",
                self.profile_id,
                "--workspace",
                str(request.workspace),
            ),
            cwd=request.workspace,
            output_format="jsonl",
            stdin=request.prompt,
        )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant: {value}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--profile-id", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    return parser


def main() -> int:
    """Run one worker turn and emit the existing Codex-compatible JSONL envelope."""
    args = _parser().parse_args()
    profile = load_api_profiles(args.profiles).get(args.profile_id)
    endpoint = resolve_api_endpoint(profile)
    if endpoint.api_key is None:
        raise APIResearcherError("API researcher profile requires a credential")
    prompt = sys.stdin.read()
    result = run_api_researcher_turn(
        profile=profile,
        endpoint=endpoint.endpoint,
        api_key=endpoint.api_key,
        prompt=prompt,
        workspace=args.workspace,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({"type": "thread.started", "thread_id": result.response_id}))
    print(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": json.dumps(
                        {
                            "profile_hash": result.profile_hash,
                            "response_model": result.response_model,
                            "system_prompt_sha256": result.system_prompt_sha256,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                },
            }
        )
    )
    print(
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
