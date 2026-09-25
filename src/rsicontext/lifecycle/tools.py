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

from collections.abc import Callable, Sequence
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
    """The arm's tool metering state — and its ENFORCEMENT (v1.1).

    Review §3.5: a counter without a cap is not a budget. ``max_calls``
    and ``max_tokens`` are cumulative caps; once exceeded, every further
    tool call refuses BEFORE executing (a named refusal receipt, never a
    silent pass, never a crash). ``calls`` counts every attempted request,
    including refusals, while ``PolicyHook.model_calls`` counts only model
    dispatches. Failed attempts cannot probe for free. Known input estimates
    are checked before external dispatch; output is charged afterward and
    cannot be hard-capped here without a bounded provider response.
    """

    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    max_calls: int | None = None
    max_tokens: int | None = None
    receipts: list[ToolReceipt] = field(default_factory=list)
    #: R1.1: the verification-request sequence lives on the BUDGET so
    #: ids stay unique across stage turns (surfaces are rebuilt per
    #: turn; a per-surface counter collided when actions and tools
    #: mixed). Every env verification — tool-path OR action-path —
    #: draws its id from here and is charged through here.
    verification_seq: int = 0

    def next_verification_id(self) -> str:
        self.verification_seq += 1
        return f"verif-{self.verification_seq}"

    def charge_verification(self) -> None:
        """Count one admitted verification request, regardless of env verdict."""

        self.calls += 1

    def enforce(self, name: str) -> str | None:
        """Refusal cause if the next call would exceed a cap, else None.

        R1.1: the TOKEN cap is checked against the cumulative total
        actually consumed (the old ``max_tokens <= 0`` check never fired
        for positive caps). Verified once + charged once: the same
        accounting entry gates both the tool path and the
        Action-submitted path.
        """

        if self.max_calls is not None and self.calls >= self.max_calls:
            return f"tool budget exhausted: call cap {self.max_calls} reached ({name})"
        if self.max_tokens is not None and (self.tokens_in + self.tokens_out) >= self.max_tokens:
            return f"tool budget exhausted: token cap {self.max_tokens} reached ({name})"
        return None

    def enforce_input(self, name: str, tokens_in: int) -> str | None:
        """Refuse known input cost before dispatch; output is not yet known."""

        if self.max_tokens is not None and (
            self.tokens_in + self.tokens_out + tokens_in > self.max_tokens
        ):
            return f"tool budget exhausted: token cap {self.max_tokens} exceeded by input ({name})"
        return None

    def charge(self, tokens_in: int, tokens_out: int) -> None:
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.calls += 1

    def charge_input(self, tokens_in: int) -> None:
        """Add input from an already charged call without counting it twice."""

        self.tokens_in += tokens_in

    def charge_output(self, tokens_out: int) -> None:
        """Add output from an already charged call without counting it twice."""

        self.tokens_out += tokens_out

    def ledger(self) -> dict[str, int | None]:
        return {
            "tool_calls": self.calls,
            "tool_tokens_in": self.tokens_in,
            "tool_tokens_out": self.tokens_out,
            "max_calls": self.max_calls,
            "max_tokens": self.max_tokens,
        }


class DocumentRegistry:
    """Every document the world has LEGALLY revealed, in order (v1.1).

    Review §3.4: reread used to index only the CURRENT stage's
    attachments, so previously-seen survey material read back as
    "unknown doc id". The registry accumulates what was revealed as
    stages run — reread reads from it, so any document the participant
    legitimately saw stays readable, and future material is unreachable
    by construction (it has not been revealed yet).
    """

    def __init__(self) -> None:
        self._documents: dict[str, DocumentRef] = {}

    def reveal(self, documents: Sequence[DocumentRef]) -> None:
        """Accumulate revealed documents — REPLACE on content change.

        B-group correctness (design review, 2026-09-23): a NEW project
        may legitimately re-reveal the same doc id with DIFFERENT text
        (the mirror corpus patches card-01/03/11). The old ``setdefault``
        served the STALE card text in session 3 — a correctness bug for
        cross-session reuse; the registry must resolve to the CURRENT
        world's text. Replacement is safe for the in-session case
        (re-revealing identical content is a no-op).
        """

        for doc in documents:
            existing = self._documents.get(doc.doc_id)
            if existing is None or existing.text != doc.text:
                self._documents[doc.doc_id] = doc

    def get(self, doc_id: str) -> DocumentRef | None:
        return self._documents.get(doc_id)

    def knows(self, doc_id: str) -> bool:
        return doc_id in self._documents


class ToolSurface:
    """The stage-scoped tools handed to a participant policy each turn.

    One instance per stage view; built by the trajectory entry (or any
    host) from the world's documents and the live ``ProjectState``. The
    env-verification channel stays Action-shaped (request_verification);
    here it gains a direct callable form whose receipt carries the same
    verdict fields.

    v1.1: reread resolves through the ``registry`` (everything legally
    revealed so far), and every tool enforces the budget BEFORE
    executing.
    """

    def __init__(
        self,
        *,
        documents: Sequence[DocumentRef],
        env: ProjectState,
        budget: ToolBudget,
        registry: DocumentRegistry | None = None,
        max_output_tokens: int = 2048,
        delegate_runner: Callable[[str, Sequence[str]], str] | None = None,
    ) -> None:
        self._documents = {doc.doc_id: doc for doc in documents}
        self._registry = registry
        if registry is not None:
            registry.reveal(documents)
        self._env = env
        self._budget = budget
        self._max_output_tokens = max_output_tokens
        self._delegate_runner = delegate_runner

    def reread(self, doc_id: str, span: tuple[int, int] | None = None) -> ToolReceipt:
        """Re-read any document the world has LEGALLY revealed (v1.1).

        Resolution order: the document registry (everything revealed in
        earlier stages) first, then the current stage's attachments.
        Future material is unreachable by construction — it has not been
        revealed. ``span`` (start, length) in lines bounds the cost for
        policies that learned to read slices. Unknown ids refuse with a
        cause. Budget is enforced BEFORE the read; the refusal still
        meters (a call is a call).
        """

        refusal = self._budget.enforce("reread")
        if refusal is not None:
            self._budget.charge(0, 0)
            receipt = ToolReceipt(tool="reread", ok=False, cause=refusal)
            self._budget.receipts.append(receipt)
            return receipt
        doc = self._documents.get(doc_id)
        if doc is None and self._registry is not None:
            doc = self._registry.get(doc_id)
        if doc is None:
            self._budget.charge(0, 0)
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

        refusal = self._budget.enforce("query_sandbox")
        if refusal is not None:
            self._budget.charge(0, 0)
            receipt = ToolReceipt(tool="query_sandbox", ok=False, cause=refusal)
            self._budget.receipts.append(receipt)
            return receipt
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
        """The env verification service in callable form (same oracle).

        v1.1: the call is METERED (charge + unique sequential record id —
        the old id derived from ``budget.calls`` collided with
        reread/query usage) and budget-gated before the env executes.
        """

        refusal = self._budget.enforce("request_verification")
        if refusal is not None:
            self._budget.charge(0, 0)
            receipt = ToolReceipt(tool="request_verification", ok=False, cause=refusal)
            self._budget.receipts.append(receipt)
            return receipt
        record_id = self._budget.next_verification_id()
        action = Action(
            kind="request_verification",
            record_id=record_id,
            fields={"check": check, "subject": subject},
        )
        env_receipt = self._env.submit(action)
        self._budget.charge_verification()
        tool_receipt = ToolReceipt(
            tool="request_verification",
            ok=env_receipt.applied and env_receipt.verdict == "pass",
            answer=env_receipt.verdict,
            cause=env_receipt.cause,
        )
        self._budget.receipts.append(tool_receipt)
        return tool_receipt

    def delegate(self, query: str, doc_ids: Sequence[str]) -> ToolReceipt:
        """A bounded sub-agent over named documents; returns its finding.

        The host injects ``delegate_runner`` (the model channel). A
        return without finding/source/applicability is recorded as
        unusable — exactly the delegation stage's documented contract.
        Without a runner installed, the tool refuses with a cause (the
        calibration profile runs delegation-free). v1.1: budget-gated
        before the sub-agent runs; documents resolve through the
        registry so delegation may cite previously-revealed material.
        """

        refusal = self._budget.enforce("delegate")
        if refusal is not None:
            self._budget.charge(0, 0)
            receipt = ToolReceipt(tool="delegate", ok=False, cause=refusal)
            self._budget.receipts.append(receipt)
            return receipt
        self._budget.charge(0, 0)
        if self._delegate_runner is None:
            receipt = ToolReceipt(tool="delegate", ok=False, cause="no delegate runner installed")
            self._budget.receipts.append(receipt)
            return receipt
        if (
            isinstance(doc_ids, str)
            or not isinstance(doc_ids, Sequence)
            or any(not isinstance(doc_id, str) for doc_id in doc_ids)
        ):
            receipt = ToolReceipt(
                tool="delegate",
                ok=False,
                cause=(
                    "invalid delegate documents: TypeError: doc_ids must be a sequence of strings"
                ),
            )
            self._budget.receipts.append(receipt)
            return receipt
        docs = []
        for doc_id in doc_ids:
            doc = self._documents.get(doc_id)
            if doc is None and self._registry is not None:
                doc = self._registry.get(doc_id)
            if doc is not None:
                docs.append(doc.text)
        if not docs:
            receipt = ToolReceipt(tool="delegate", ok=False, cause="no known documents named")
            self._budget.receipts.append(receipt)
            return receipt
        tokens_in = DELEGATE_OVERHEAD_TOKENS + sum(max(1, len(doc.split())) for doc in docs)
        refusal = self._budget.enforce_input("delegate", tokens_in)
        if refusal is not None:
            receipt = ToolReceipt(tool="delegate", ok=False, cause=refusal)
            self._budget.receipts.append(receipt)
            return receipt
        self._budget.charge_input(tokens_in)
        try:
            answer = self._delegate_runner(query, docs)
            if not isinstance(answer, str):
                raise TypeError("delegate runner must return a string")
            tokens_out = DELEGATE_OVERHEAD_TOKENS + max(1, len(answer.split()))
        except Exception as exc:
            receipt = ToolReceipt(
                tool="delegate",
                ok=False,
                cause=f"delegate call failed: {type(exc).__name__}: {exc}",
                tokens_in=tokens_in,
            )
            self._budget.receipts.append(receipt)
            return receipt
        self._budget.charge_output(tokens_out)
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
    registry: DocumentRegistry | None = None,
    delegate_runner: Callable[[str, Sequence[str]], str] | None = None,
) -> ToolSurface:
    """Build the stage-scoped tool surface from a view and live env."""

    return ToolSurface(
        documents=view.documents,
        env=env,
        budget=budget,
        registry=registry,
        delegate_runner=delegate_runner,
    )
