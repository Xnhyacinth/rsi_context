"""Private one-shot worker for fresh-process context-policy execution."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from rsicontext.eval.fresh_policy import _decode_request, _encode_context
from rsicontext.policy import ContextPack


def _load_policy(policy_root: Path, entrypoint: str, policy_class: str) -> object:
    source_path = policy_root / entrypoint
    spec = importlib.util.spec_from_file_location("_rsicontext_candidate_policy", source_path)
    if spec is None or spec.loader is None:
        raise ImportError("candidate policy entrypoint has no Python loader")
    # Isolated interpreters omit cwd from sys.path. Append the audited tree so
    # sibling modules resolve without shadowing stdlib or rsicontext.
    root_str = str(policy_root)
    if root_str not in sys.path:
        sys.path.append(root_str)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    policy_type = getattr(module, policy_class)
    policy = policy_type()
    if not callable(getattr(policy, "assemble", None)):
        raise TypeError("candidate Policy must provide assemble")
    return policy


def main(arguments: list[str] | None = None) -> int:
    args = sys.argv[1:] if arguments is None else arguments
    if len(args) != 3:
        sys.stderr.write("policy worker requires root, entrypoint, and class\n")
        return 2
    try:
        policy_root = Path(args[0]).resolve(strict=True)
        artifact, query, budget = _decode_request(sys.stdin.buffer.read())
        policy = _load_policy(policy_root, args[1], args[2])
        context = policy.assemble(artifact, query, budget)  # type: ignore[attr-defined]
        if not isinstance(context, ContextPack):
            raise TypeError("candidate Policy.assemble must return ContextPack")
        sys.stdout.buffer.write(_encode_context(context))
    except BaseException as exc:  # Fail closed even for candidate-raised SystemExit.
        sys.stderr.write(f"policy worker failed: {type(exc).__name__}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
