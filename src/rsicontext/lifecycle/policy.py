"""RSI core v1 — the open policy surface (spec Part 1.3).

The 4-knob strategy namespace (STRATEGY_RERVERIFY and friends) remains
the CALIBRATION profile. This module defines the v2 surface: the learned
artifact is an executable policy ``on_turn(Turn) -> TurnDecision`` over
observations (stage view + receipts) and the metered tool surface — the
decisions the old harness hard-coded (note retention, check derivation,
verification timing, citation, prompt construction) all move here.

Execution boundary (spec Part 1.4): policy code runs under a RESTRICTED
namespace — no imports beyond a stdlib whitelist, no open/__import__/os/
network. A capability scan runs at freeze time so a snapshot can never
carry code that escapes the boundary. Full OS-level sandboxing is
explicitly deferred; official runs additionally isolate whole
experiments.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from rsicontext.lifecycle.env import Action, Receipt
from rsicontext.lifecycle.runner import StageResponse, StageView
from rsicontext.lifecycle.tools import ToolSurface

#: Modules a policy may import (everything else is a freeze-time refusal).
ALLOWED_POLICY_MODULES: frozenset[str] = frozenset({"json", "re", "math", "statistics"})

_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bopen\s*\(", "open() call"),
    (r"\b__import__\s*\(", "__import__ call"),
    (r"\bexec\s*\(", "exec() call"),
    (r"\beval\s*\(", "eval() call"),
    (r"\bos\.", "os module access"),
    (r"\bsubprocess\b", "subprocess reference"),
    (r"\bsys\.", "sys module access"),
    (r"\bbuiltins\b", "builtins reference"),
    (r"\bglobals\s*\(", "globals() call"),
    (r"\bvars\s*\(", "vars() call"),
)


class PolicyBoundaryError(RuntimeError):
    """A policy text escapes the restricted execution boundary."""


def scan_policy_text(text: str) -> None:
    """Freeze-time capability scan: forbid escapes from the namespace.

    Pattern-level (defense in depth with the restricted namespace): the
    scan names what it found, so a researcher-authored strategy carrying
    e.g. an ``open(`` call is a NAMED snapshot refusal, not a silent
    acceptance.
    """

    for pattern, name in _FORBIDDEN_PATTERNS:
        if re.search(pattern, text):
            raise PolicyBoundaryError(f"policy text contains forbidden capability: {name}")


def _scan_imports(text: str) -> None:
    for match in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.MULTILINE):
        module = match.group(1)
        if module not in ALLOWED_POLICY_MODULES:
            raise PolicyBoundaryError(
                f"policy imports {module!r}; allowed modules are {sorted(ALLOWED_POLICY_MODULES)}"
            )


def scan_policy(text: str) -> None:
    """Full freeze-time scan (capabilities + import whitelist)."""

    scan_policy_text(text)
    _scan_imports(text)


def _restricted_builtins() -> dict[str, Any]:
    """The builtins a policy sees — everything but the escape hatches."""

    import builtins as _builtins

    safe = {
        name: getattr(_builtins, name)
        for name in (
            "abs",
            "all",
            "any",
            "bool",
            "dict",
            "divmod",
            "enumerate",
            "filter",
            "float",
            "frozenset",
            "int",
            "isinstance",
            "len",
            "list",
            "map",
            "max",
            "min",
            "range",
            "repr",
            "reversed",
            "round",
            "set",
            "sorted",
            "str",
            "sum",
            "tuple",
            "zip",
        )
    }
    return safe


@dataclass
class TurnActions:
    """The action factory handed to a policy (the only way to write).

    Policies cannot import the env module (restricted namespace), so
    ``turn.actions`` is their one construction channel — the surface the
    improvement loop actually shapes. New action kinds enter here, not
    through imports.
    """

    def create_record(self, record_id: str, fields: Mapping[str, Any]) -> Action:
        return Action(kind="create_record", record_id=record_id, fields=dict(fields))

    def update_record(self, record_id: str, fields: Mapping[str, Any]) -> Action:
        return Action(kind="update_record", record_id=record_id, fields=dict(fields))

    def request_verification(self, record_id: str, check: str, subject: str) -> Action:
        return Action(
            kind="request_verification",
            record_id=record_id,
            fields={"check": check, "subject": subject},
        )

    def finalize(
        self,
        record_id: str,
        fields: Mapping[str, Any],
        provenance: Sequence[str],
    ) -> Action:
        return Action(
            kind="finalize",
            record_id=record_id,
            fields=dict(fields),
            provenance=tuple(provenance),
        )


@dataclass
class Turn:
    """Everything a policy sees for one turn (observations + tools).

    ``view`` is the stage view INCLUDING this turn's pending receipts;
    ``tools`` is the metered tool surface; ``state`` is the participant's
    own memory dict (the policy decides how to shape it — retention is
    no longer a harness constant); ``actions`` is the write factory.
    """

    view: StageView
    receipts: tuple[Receipt, ...]
    tools: ToolSurface
    state: dict[str, Any]
    actions: TurnActions = field(default_factory=TurnActions)

    @property
    def stage_kind(self) -> str:
        return self.view.kind

    @property
    def documents_text(self) -> str:
        return "\n\n".join(f"[[doc:{d.doc_id}]] {d.title}\n{d.text}" for d in self.view.documents)


@dataclass
class TurnDecision:
    """The policy's full turn output."""

    pack_text: str
    actions: tuple[Action, ...] = ()
    memory_writes: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def load_policy(strategy_text: str) -> Callable[[Turn], TurnDecision]:
    """Compile a policy file under the restricted namespace.

    The file must define ``on_turn(turn: Turn) -> TurnDecision``. A
    policy that raises is the CALLER's named outcome (recorded, never
    silent) — matching the calibration profile's strategy_errors
    contract.
    """

    scan_policy(strategy_text)
    # Host-side import: the policy namespace's __import__ is a guarded
    # shim (whitelist only) so ``import re`` inside policy code works
    # while ``import os`` cannot — module VALUES are also pre-injected.
    import importlib

    def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in ALLOWED_POLICY_MODULES:
            raise PolicyBoundaryError(
                f"policy tried to import {name!r}; allowed modules are "
                f"{sorted(ALLOWED_POLICY_MODULES)}"
            )
        return importlib.import_module(name)

    builtins = _restricted_builtins()
    builtins["__import__"] = _safe_import
    namespace: dict[str, Any] = {"__builtins__": builtins}
    for module_name in sorted(ALLOWED_POLICY_MODULES):
        try:
            namespace[module_name] = importlib.import_module(module_name)
        except ImportError:  # pragma: no cover - stdlib always present
            continue
    exec(compile(strategy_text, "<policy>", "exec"), namespace)  # noqa: S307
    policy = namespace.get("on_turn")
    if not callable(policy):
        raise PolicyBoundaryError("policy must define on_turn(turn) -> TurnDecision")
    return policy


class PolicyHook:
    """A participant hook driven by an ``on_turn`` policy (RSI core v1).

    The wiring: each stage view becomes a ``Turn`` (view + receipts +
    metered tools + the participant's own state + the action factory);
    the policy's ``TurnDecision`` becomes the ``StageResponse`` and its
    memory writes merge into the state. A policy that raises or returns
    an invalid decision is a NAMED outcome (``policy_errors``), never a
    silent fallback — the calibration profile's contract, carried over.

    The reader/model channel is INJECTED (``responder``): the harness
    never calls a model directly; the host decides whether the policy
    gets a live reader, a deterministic fake, or none (the strong-fixed
    baseline is pure code — no model calls inside the policy itself).
    """

    def __init__(
        self,
        state: dict[str, Any],
        policy_text: str,
        *,
        tool_budget: ToolBudget,
        env: ProjectState | None = None,
        delegate_runner: Callable[[str, Sequence[str]], str] | None = None,
        responder: Callable[[str], str] | None = None,
    ) -> None:
        self.state = state
        self.policy_text = policy_text
        self.tool_budget = tool_budget
        self._env = env
        self._delegate_runner = delegate_runner
        self._responder = responder
        self.policy_errors: list[str] = []
        self._policy: Callable[[Turn], TurnDecision] | None = None
        try:
            self._policy = load_policy(policy_text)
        except Exception as exc:
            self.policy_errors.append(f"policy load failed: {type(exc).__name__}: {exc}")

    def bind_env(self, env: ProjectState) -> None:
        """Attach the live env (called by the host before the run starts)."""

        self._env = env

    def on_stage(self, stage: StageView) -> StageResponse:
        if self._policy is None:
            return StageResponse(pack_text="policy unavailable")
        tools = ToolSurface(
            documents=stage.documents,
            env=self._env if self._env is not None else ProjectState(),
            budget=self.tool_budget,
            delegate_runner=self._delegate_runner,
        )
        turn = Turn(
            view=stage,
            receipts=stage.receipts,
            tools=tools,
            state=self.state,
        )
        try:
            decision = self._policy(turn)
        except Exception as exc:
            self.policy_errors.append(f"on_turn raised {type(exc).__name__}: {exc}")
            return StageResponse(pack_text="policy turn error")
        if not isinstance(decision, TurnDecision):
            if isinstance(decision, dict):
                decision = TurnDecision(
                    pack_text=str(decision.get("pack_text", "")),
                    actions=tuple(decision.get("actions", ())),
                    memory_writes=dict(decision.get("memory_writes", {}) or {}),
                    errors=list(decision.get("errors", []) or []),
                )
            else:
                self.policy_errors.append(
                    f"on_turn returned {type(decision).__name__}; expected TurnDecision/dict"
                )
                return StageResponse(pack_text="policy decision error")
        for key, value in decision.memory_writes.items():
            self.state[key] = value
        self.policy_errors.extend(decision.errors)
        return StageResponse(pack_text=decision.pack_text, actions=decision.actions)
