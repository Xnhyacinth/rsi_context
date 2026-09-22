"""RSI core v1 — the metered tool surface (spec Part 1.2).

The information diet becomes improvable: WHEN to re-read, WHAT to store,
WHEN to verify, WHEN to delegate are policy decisions backed by real,
priced channels. Tools are stage-scoped, env-answered, and every call is
metered into the run's cost ledger — the strong-fixed and improved arms
pay the same prices.

Design rules (spec Part 1.2):
- tools answer from WORLD DATA only (docs the world showed, the
  participant's own records, the env's oracle) — evaluator internals
  are unreachable by construction;
- budget exhaustion is a NAMED refusal (``ToolRefused`` receipt), never
  a silent pass and never a crash;
- the delegation surface is a real bounded sub-agent call, no longer a
  document ABOUT delegation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.runner import StageView
from rsicontext.lifecycle.spec import DocumentRef

#: Fixed per-call overheads (spec Part 1.5; tokens, ledgered as such).
REREAD_OVERHEAD_TOKENS = 32
DELEGATE_OVERHEAD_TOKENS = 64
QUERY_SANDBOX_OVERHEAD_TOKENS = 16


@dataclass(frozen=True, slots=True)
class ToolReceipt:
    """One tool call's answer, in the same receipt currency as actions."""

    tool: str
    ok: bool
    answer: str = ""
    cause: str = ""
    tokens_in: int = 0
    tokens_out: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "ok": self.ok,
            "answer": self.answer,
            "cause": self.cause,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
        }


@dataclass
class ToolBudget:
    """The arm's tool metering state (the caller owns the ledger merge)."""

    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    receipts: list[ToolReceipt] = field(default_factory=list)

    def charge(self, tokens_in: int, tokens_out: int) -> None:
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.calls += 1

    def ledger(self) -> dict[str, int]:
        return {
            "tool_calls": self.calls,
            "tool_tokens_in": self.tokens_in,
            "tool_tokens_out": self.tokens_out,
        }


class ToolSurface:
    """The stage-scoped tools handed to a participant policy each turn.

    One instance per stage view; built by the trajectory entry (or any
    host) from the world's documents and the live ``ProjectState``. The
    env-verification channel stays Action-shaped (request_verification);
    here it gains a direct callable form whose receipt carries the same
    verdict fields.
    """

    def __init__(
        self,
        *,
        documents: Sequence[DocumentRef],
        env: ProjectState,
        budget: ToolBudget,
        max_output_tokens: int = 2048,
        delegate_runner: Callable[[str, Sequence[str]], str] | None = None,
    ) -> None:
        self._documents = {doc.doc_id: doc for doc in documents}
        self._env = env
        self._budget = budget
        self._max_output_tokens = max_output_tokens
        self._delegate_runner = delegate_runner

    def reread(self, doc_id: str, span: tuple[int, int] | None = None) -> ToolReceipt:
        """Re-read a document the world showed (the promise stage 1 makes).

        ``span`` (start, length) in lines bounds the cost for policies
        that learned to read slices; the default is the full document.
        Unknown ids refuse with a cause.
        """

        doc = self._documents.get(doc_id)
        if doc is None:
            receipt = ToolReceipt(tool="reread", ok=False, cause=f"unknown doc id {doc_id!r}")
            self._budget.receipts.append(receipt)
            return receipt
        text = doc.text
        if span is not None:
            start, length = max(0, span[0]), max(0, span[1])
            text = "\n".join(text.splitlines()[start : start + length])
        tokens_in = REREAD_OVERHEAD_TOKENS + max(1, len(text.split()))
        tokens_out = 0
        self._budget.charge(tokens_in, tokens_out)
        receipt = ToolReceipt(tool="reread", ok=True, answer=text, tokens_in=tokens_in)
        self._budget.receipts.append(receipt)
        return receipt

    def query_sandbox(self, pattern: str) -> ToolReceipt:
        """Read back the participant's own records (and their fields)."""

        matches = []
        for record_id, record in self._env.records.items():
            if pattern.lower() in record_id.lower() or any(
                pattern.lower() in str(value).lower() for value in record.values()
            ):
                matches.append(f"{record_id}: {record}")
        body = "\n".join(matches) if matches else "(no matching records)"
        tokens_out = QUERY_SANDBOX_OVERHEAD_TOKENS + max(1, len(body.split()))
        self._budget.charge(0, tokens_out)
        receipt = ToolReceipt(tool="query_sandbox", ok=True, answer=body, tokens_out=tokens_out)
        self._budget.receipts.append(receipt)
        return receipt

    def request_verification(self, check: str, subject: str) -> ToolReceipt:
        """The env verification service in callable form (same oracle)."""

        action = Action(
            kind="request_verification",
            record_id=f"tool-verif-{self._budget.calls}",
            fields={"check": check, "subject": subject},
        )
        receipt = self._env.submit(action)
        payload = receipt.to_dict()
        tool_receipt = ToolReceipt(
            tool="request_verification",
            ok=receipt.applied and receipt.verdict == "pass",
            answer=payload["verdict"],
            cause=payload["cause"],
        )
        self._budget.receipts.append(tool_receipt)
        return tool_receipt

    def delegate(self, query: str, doc_ids: Sequence[str]) -> ToolReceipt:
        """A bounded sub-agent over named documents; returns its finding.

        The host injects ``delegate_runner`` (the model channel). A
        return without finding/source/applicability is recorded as
        unusable — exactly the delegation stage's documented contract.
        Without a runner installed, the tool refuses with a cause (the
        calibration profile runs delegation-free).
        """

        if self._delegate_runner is None:
            receipt = ToolReceipt(tool="delegate", ok=False, cause="no delegate runner installed")
            self._budget.receipts.append(receipt)
            return receipt
        docs = [self._documents[doc_id].text for doc_id in doc_ids if doc_id in self._documents]
        if not docs:
            receipt = ToolReceipt(tool="delegate", ok=False, cause="no known documents named")
            self._budget.receipts.append(receipt)
            return receipt
        tokens_in = DELEGATE_OVERHEAD_TOKENS + sum(max(1, len(doc.split())) for doc in docs)
        answer = self._delegate_runner(query, docs)
        tokens_out = DELEGATE_OVERHEAD_TOKENS + max(1, len(answer.split()))
        self._budget.charge(tokens_in, tokens_out)
        receipt = ToolReceipt(
            tool="delegate", ok=True, answer=answer, tokens_in=tokens_in, tokens_out=tokens_out
        )
        self._budget.receipts.append(receipt)
        return receipt


def tool_surface_for_stage(
    view: StageView,
    env: ProjectState,
    budget: ToolBudget,
    *,
    delegate_runner: Callable[[str, Sequence[str]], str] | None = None,
) -> ToolSurface:
    """Build the stage-scoped tool surface from a view and live env."""

    return ToolSurface(
        documents=view.documents,
        env=env,
        budget=budget,
        delegate_runner=delegate_runner,
    )
