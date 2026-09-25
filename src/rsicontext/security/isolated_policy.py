"""Fail-closed entry gate for model-authored lifecycle policies.

The current ``PolicyHook`` executes Python in the evaluator process. Its
restricted builtins and static audit are useful hygiene checks, but neither
separates policy code from evaluator memory, credentials, or the filesystem.
Do not enable live candidate execution until a jailed worker and a typed,
metered turn/tool/model broker replace this gate.
"""

from __future__ import annotations


class PolicyIsolationUnavailable(RuntimeError):
    """A researcher-authored policy cannot run with the current executor."""


def require_isolated_policy_executor() -> None:
    """Refuse candidate execution before loading code or spending API tokens.

    A subprocess or network namespace alone is insufficient: the candidate
    must also be unable to read the evaluator's files and process state, and
    every visible turn, tool, and model operation must cross a checked broker.
    No executor in this repository currently satisfies that contract.
    """

    raise PolicyIsolationUnavailable(
        "live researcher policy execution requires a jailed candidate process "
        "and a metered turn/tool/model broker; neither is installed"
    )
