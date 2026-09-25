"""Participant-agnostic stage runner for research-v1 lifecycles.

Spec: ``docs/task-family-research-v1.md`` §Task structure and
``docs/benchmark-contract-v2.md`` §Protocol semantics. The runner executes
the five stages in order against an injected ``ParticipantHook`` — it never
calls a reader itself, so participants (fixed / experience-only / open-S
arms; adapters land in other workstreams) drive behavior through the hook.

Evaluator-only fields (including ``gold_evidence_ids``,
``expected_state_delta``, ``commit_precondition``, and
``verification_oracle``) are never surfaced to the hook: the runner builds
``StageView`` from explicitly selected participant fields. The two-column
cost split is honored in miniature: token counts are
placeholders the hook caller fills (reader accounting lands with the cost
ledger workstream), wall seconds are measured here.
"""

from __future__ import annotations

import copy
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from rsicontext.lifecycle.env import (
    Action,
    CheckResult,
    ObjectiveChecker,
    ProjectState,
    Receipt,
)
from rsicontext.lifecycle.spec import (
    DescriptionAxes,
    DocumentRef,
    LifecycleInstance,
    StageSpec,
)

_DOC_MARKER = re.compile(r"\[\[doc:([^]]+)\]\]")


@dataclass(frozen=True, slots=True)
class StageView:
    """What a participant sees for one stage — evaluator-only fields excluded.

    Constructed from participant-visible ``StageSpec`` fields; evaluator
    fields such as commit preconditions and verification oracles are not
    copied. ``remaining_budget`` counts stages left including this one.
    """

    stage_id: str
    kind: str
    prompt_text: str
    documents: tuple[DocumentRef, ...]
    axes: DescriptionAxes
    remaining_budget: int
    #: RSI core v1 — the act->observe channel: everything the environment
    #: said since the participant's last turn (action receipts: verdicts,
    #: refusals with named causes). Evaluator-only fields stay excluded;
    #: receipts carry env ANSWERS, never oracle internals.
    receipts: tuple[Receipt, ...] = ()

    def cited_doc_ids(self, pack_text: str) -> tuple[str, ...]:
        """Doc ids referenced by ``[[doc:ID]]`` markers in ``pack_text``."""

        return tuple(_DOC_MARKER.findall(pack_text))


@dataclass(frozen=True, slots=True)
class StageResponse:
    """One participant turn: the pack it would act on plus its writes."""

    pack_text: str
    actions: tuple[Action, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.pack_text, str):
            raise TypeError("pack_text must be a string")
        object.__setattr__(self, "actions", tuple(self.actions))
        if any(not isinstance(action, Action) for action in self.actions):
            raise TypeError("stage actions must be Action values")


class ParticipantHook(Protocol):
    """The participant-facing surface of one lifecycle run.

    ``on_stage`` receives only ``StageView`` data (see its docstring) and
    returns the pack text plus any sandbox writes. Implementations hold the
    participant's retainable state Σ; the runner holds none.
    """

    def on_stage(self, stage: StageView) -> StageResponse: ...


@runtime_checkable
class RevealSink(Protocol):
    """Where revealed documents accumulate (tools.DocumentRegistry's shape).

    Structural (not the concrete class) because tools.py imports this
    module for ``StageView`` — a concrete import here would be circular.
    """

    def reveal(self, documents: Sequence[DocumentRef]) -> None: ...


@dataclass(frozen=True, slots=True)
class StageRecord:
    """Evaluator-side record of one executed stage.

    ``stale_fact_rate`` and ``delegation_completeness`` are placeholder
    record fields — family-qualification deliverables computed by the
    qualification battery (contract-tests §5), not by this runtime.
    """

    stage_id: str
    kind: str
    cited_doc_ids: tuple[str, ...]
    available_doc_ids: tuple[str, ...]
    provenance_retention: float
    actions_applied: int
    stale_fact_rate: float
    delegation_completeness: float
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "kind": self.kind,
            "cited_doc_ids": list(self.cited_doc_ids),
            "available_doc_ids": list(self.available_doc_ids),
            "provenance_retention": self.provenance_retention,
            "actions_applied": self.actions_applied,
            "stale_fact_rate": self.stale_fact_rate,
            "delegation_completeness": self.delegation_completeness,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class LifecycleRunRecord:
    """The auditable outcome of one lifecycle run.

    ``cost`` carries the two-column split in miniature: ``tokens_in`` /
    ``tokens_out`` are placeholders the hook caller fills; ``wall_seconds``
    is measured. ``sandbox_final_state`` is the deep-copied end state the
    final check was computed against.

    ``stale_references`` (reviewer 6.2, task-card §Scoring
    "finalized-then-invalidated conclusions still referenced"): the
    sandbox record ids a FINALIZED commit record references that a
    LATER record supersedes. Supersession is recorded by the
    participant itself through the ``supersedes`` field — the runner
    only reports it; a record never superseded, or a superseding
    record created but the commit re-pointed away, both report clean.
    """

    instance_id: str
    family: str
    final_check: CheckResult
    stage_records: tuple[StageRecord, ...]
    cost: Mapping[str, float]
    axes: DescriptionAxes
    sandbox_final_state: Mapping[str, dict[str, Any]] = field(default_factory=dict)
    stale_references: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "family": self.family,
            "final_check": self.final_check.to_dict(),
            "stage_records": [record.to_dict() for record in self.stage_records],
            "cost": dict(self.cost),
            "axes": self.axes.to_dict(),
            "sandbox_final_state": {
                record_id: dict(record) for record_id, record in self.sandbox_final_state.items()
            },
            "stale_references": list(self.stale_references),
        }


def _provenance_retention(
    stage: StageSpec, cited: tuple[str, ...], available: tuple[str, ...]
) -> float:
    """Share of gold evidence the acting context cited, over available docs.

    Per task-family spec §Metrics: "did the acting context cite evidence that
    exists in the gold-support set". Cites of doc ids not in the stage's
    documents do not count (they are recorded in the stage record's notes).
    """

    gold = frozenset(stage.gold_evidence_ids)
    if not gold:
        return 1.0
    available_set = frozenset(available)
    valid_cites = frozenset(cited) & available_set
    return len(gold & valid_cites) / len(gold)


def _stage_notes(stage: StageSpec, cited: tuple[str, ...]) -> tuple[str, ...]:
    available = frozenset(document.doc_id for document in stage.documents)
    unknown = sorted(frozenset(cited) - available)
    return (f"cited unknown doc ids: {unknown}",) if unknown else ()


def _build_stage_view(
    stage: StageSpec,
    axes: DescriptionAxes,
    *,
    remaining: int,
    receipts: tuple[Receipt, ...] = (),
) -> StageView:
    """Build the participant view of one stage — evaluator fields excluded.

    ``StageView`` is constructed from ``stage``'s participant-visible fields
    plus the env's pending receipts; ``gold_evidence_ids`` and
    ``expected_state_delta`` are never read here, so no view (or
    serialization of one) can leak them.
    """

    return StageView(
        stage_id=stage.stage_id,
        kind=stage.kind,
        prompt_text=stage.prompt_text,
        documents=stage.documents,
        axes=axes,
        remaining_budget=remaining,
        receipts=receipts,
    )


def run_lifecycle(
    inst: LifecycleInstance,
    hook: ParticipantHook,
    env: ProjectState,
    *,
    max_turns_per_stage: int = 1,
    registry: RevealSink | None = None,
) -> LifecycleRunRecord:
    """Execute ``inst``'s stages in order against ``hook``, writing into ``env``.

    Applies each stage's actions to ``env`` as they arrive (act_verify
    included), then checks the final sandbox state against the act_verify
    stage's ``expected_state_delta`` via ``ObjectiveChecker``.

    ``registry`` (review 892f1d0 M1, reveal-on-presentation): when
    supplied, each stage's documents are revealed to it right BEFORE the
    stage's first view is built — future material is structurally
    unreachable (a later stage's docs are not in the registry until that
    stage runs, so reread of them refuses; earlier stages' docs stay
    rereadable). ``None`` (the default, single-lifecycle arms) keeps the
    legacy behavior: the docs live in the stage views themselves and the
    registry is the caller's own concern.

    Multi-turn recovery (RSI core v1.1, review §3.2): a stage may run up
    to ``max_turns_per_stage`` participant turns. After each turn the
    actions' receipts queue, and the next turn's view carries them — a
    refused action can be read, corrected, and re-submitted WITHIN the
    same stage. The stage advances when the hook returns a response
    without actions (its way of saying "done here") or when the turn
    budget is exhausted. ``max_turns_per_stage=1`` (the default) is the
    legacy single-turn behavior.

    Event ordering (review §3.3): the stage's ENVIRONMENT events (the
    rule-change protocol-clock advance) apply BEFORE the first view is
    built — a verification requested through the synchronous tool and
    one submitted as an action at the same logical moment are stamped
    with the SAME protocol revision.
    """

    if not isinstance(inst, LifecycleInstance):
        raise TypeError("run_lifecycle requires a LifecycleInstance")
    if not isinstance(env, ProjectState):
        raise TypeError("run_lifecycle requires a ProjectState")
    if not isinstance(max_turns_per_stage, int) or isinstance(max_turns_per_stage, bool):
        raise TypeError("max_turns_per_stage must be an int")
    if max_turns_per_stage < 1:
        raise ValueError("max_turns_per_stage must be at least 1")
    started = time.monotonic()
    # A later session may renew only a contract that was already finalized
    # before this lifecycle began. Capture the environment's own finalization
    # ledger now; a participant cannot create the missing prior award during
    # the renewal stage and have it count retroactively.
    prior_finalized_record_ids = env.finalized_record_ids
    # Preserve the pre-session record and environment-issued evidence state
    # only when a world opts into the stronger gate. This prevents a later
    # verification from filling a dangling reference in a prior award.
    prior_verification_stages = tuple(
        stage
        for stage in inst.stages
        if stage.commit_precondition is not None
        and "prior_verification" in stage.commit_precondition
    )
    if any(stage.kind != "act_verify" for stage in prior_verification_stages):
        raise ValueError("prior_verification applies to act_verify stages only")
    prior_verification_required = bool(prior_verification_stages)
    prior_records = copy.deepcopy(env.snapshot()) if prior_verification_required else None
    prior_verification_record_ids = (
        env.verification_record_ids if prior_verification_required else frozenset()
    )
    stage_records: list[StageRecord] = []
    commit_gate_failures_at_time: list[str] = []
    total_stages = len(inst.stages)
    # The commit stage is the LAST act_verify (longitudinal v4 instances
    # carry follow_up stages after it); the oracle comes from it.
    act_verify = next(
        (stage for stage in reversed(inst.stages) if stage.kind == "act_verify"),
        inst.stages[-1],
    )
    # The evaluator-owned verification service: the act_verify stage's
    # oracle is installed BEFORE the first stage runs, so
    # request_verification actions are live from stage 1 (a fixed-arm
    # hook may pre-request verifications; a strategy that re-requests
    # after the rule change gets current-revision evidence). The oracle
    # is evaluator-only — never surfaced through StageView.
    # B-group threading: a session whose LAST act_verify carries no
    # oracle of its own must not WIPE the env's installed one (session
    # 2's re-award reuses the project's oracle installed at session 1).
    # begin_instance with None clears deliberately ONLY for fresh envs.
    if act_verify.verification_oracle is not None:
        env.begin_instance(act_verify.verification_oracle)
    elif env._verification_oracle is None:
        env.begin_instance(None)
    for index, stage in enumerate(inst.stages):
        # Reveal-on-presentation (review 892f1d0 M1): the stage's
        # documents enter the registry only NOW — the participant's
        # reread surface can reach previously-presented material but
        # never a later stage's.
        if registry is not None and stage.documents:
            registry.reveal(stage.documents)
        if stage.kind == "rule_change" and stage.rule_change_effect is not None:
            # The rule change is an ENVIRONMENT event: the protocol clock
            # advances BEFORE this stage's observations are built, so
            # synchronous tool calls and submitted actions at the same
            # logical moment see the SAME revision.
            env.apply_protocol_revision(stage.rule_change_effect, tuple(stage.rule_change_scope))
        cited: tuple[str, ...] = ()
        actions_applied = 0
        available = tuple(document.doc_id for document in stage.documents)
        for _turn_number in range(max_turns_per_stage):
            # RSI core v1 — the act->observe channel: this view carries
            # the receipts of everything the env said since the
            # participant's last turn (across stages AND within one
            # stage when recovery turns are enabled).
            view = _build_stage_view(
                stage,
                inst.axes,
                remaining=total_stages - index,
                receipts=env.drain_receipts(),
            )
            response = hook.on_stage(view)
            if not isinstance(response, StageResponse):
                raise TypeError(
                    f"hook returned {type(response).__name__} for stage "
                    f"{stage.stage_id!r}; expected StageResponse"
                )
            cited = view.cited_doc_ids(response.pack_text)
            for action in response.actions:
                env.submit(action)
            actions_applied += len(response.actions)
            if not response.actions:
                break  # the participant closed the stage voluntarily
        stage_records.append(
            StageRecord(
                stage_id=stage.stage_id,
                kind=stage.kind,
                cited_doc_ids=cited,
                available_doc_ids=available,
                provenance_retention=_provenance_retention(stage, cited, available),
                actions_applied=actions_applied,
                stale_fact_rate=0.0,
                delegation_completeness=0.0,
                notes=_stage_notes(stage, cited),
            )
        )
        if stage.kind == "act_verify" and stage.commit_precondition is not None:
            # R1.1 TIME-POINT grading (review §2.2): the award gate is
            # judged AT THE STAGE where the award happened — evidence
            # valid then is not retroactively staled by LATER rule
            # changes (the end-state check would see revision 3 and
            # fail a legitimate s5 commit). Longitudinal follow-ups are
            # graded at the END (their own contract); the commit gate is
            # not one of them.
            stage_gate_failures = _commit_gate_failures(
                stage.commit_precondition,
                env.snapshot(),
                env,
                prior_finalized_record_ids=prior_finalized_record_ids,
                prior_records=prior_records,
                prior_verification_record_ids=prior_verification_record_ids,
            )
            if stage_gate_failures:
                commit_gate_failures_at_time.extend(
                    f"commit gate[{stage.stage_id}]: {failure}" for failure in stage_gate_failures
                )
    expected = act_verify.expected_state_delta
    if expected is None:  # guarded by StageSpec.__post_init__; kept for mypy
        raise ValueError("act_verify stage lacks expected_state_delta")
    final_check = ObjectiveChecker().check(
        env, expected, aliases=act_verify.expected_aliases or None
    )
    if commit_gate_failures_at_time:
        final_check = CheckResult(
            passed=False,
            failures=(*final_check.failures, *commit_gate_failures_at_time),
        )
    # Longitudinal grading (research-v4): every follow_up stage's
    # expected_state_delta is checked over the SAME sandbox at the end —
    # a conclusion record that should have been created/refreshed from
    # retained or re-read evidence. Follow-up failures are named with the
    # stage id so the record says WHICH horizon link broke.
    # R1.1 (review §2.2, Option A): a follow_up may declare an
    # ``evidence_currency`` grading — the participant's diagnosis is
    # scored against the value DERIVED from the sandbox (the commit's
    # referenced in-scope evidence vs the env's per-check revisions), so
    # different legal histories legitimately yield different correct
    # answers; the stage grades a DIAGNOSIS, not a memorized string.
    for follow in inst.stages:
        if follow.kind != "follow_up" or follow.expected_state_delta is None:
            continue
        expected_follow = follow.expected_state_delta
        precondition = follow.commit_precondition or {}
        currency = precondition.get("evidence_currency")
        if isinstance(currency, Mapping):
            derived = _derive_evidence_currency(env, currency)
            record_key = str(currency.get("record_id", ""))
            field_name = str(currency.get("field", "status"))
            expected_follow = dict(expected_follow)
            raw_record_spec = expected_follow.get(record_key, {})
            if not isinstance(raw_record_spec, Mapping):
                raise TypeError(f"expected follow-up record {record_key!r} must be a mapping")
            record_spec = dict(raw_record_spec)
            record_spec[field_name] = derived
            expected_follow[record_key] = record_spec
        follow_check = ObjectiveChecker().check(
            env, expected_follow, aliases=follow.expected_aliases or None
        )
        if not follow_check.passed:
            final_check = CheckResult(
                passed=False,
                failures=(
                    *final_check.failures,
                    *(
                        f"follow_up[{follow.stage_id}]: {failure}"
                        for failure in follow_check.failures
                    ),
                ),
            )
    wall_seconds = time.monotonic() - started
    snapshot = env.snapshot()
    return LifecycleRunRecord(
        instance_id=inst.instance_id,
        family=inst.family,
        final_check=final_check,
        stage_records=tuple(stage_records),
        cost={"tokens_in": 0.0, "tokens_out": 0.0, "wall_seconds": wall_seconds},
        axes=inst.axes,
        sandbox_final_state=snapshot,
        stale_references=_stale_references(snapshot),
    )


def _derive_evidence_currency(env: ProjectState, spec: Mapping[str, object]) -> str:
    """Derive the correct evidence-currency diagnosis from the sandbox.

    R1.1 Option A: the follow-up grades a DIAGNOSIS. The expected value
    is computed from what actually happened — ALL of it, ORDER-FREE
    (review 892f1d0 M1): every referenced record carrying the named
    ``check`` is compared against the env's CURRENT revision for that
    check, mirroring ``_commit_gate_failures``' scoped-currency rule.

    - ANY referenced in-scope evidence older than the current revision
      -> ``stale_value`` (e.g. "reverify") — a stale citation fails the
      diagnosis exactly as it fails the scoped commit gate, regardless
      of provenance order.
    - otherwise (at least one current, none stale) -> ``current_value``
      (e.g. "current"). A participant whose evidence was acquired AFTER
      the supersession legitimately answers "current" — different legal
      histories, different correct answers.
    - NO referenced record carries the named check -> the explicit
      ``missing_value`` (default "no-evidence"): "current" would be the
      optimistic guess, the opposite of a diagnosis with nothing to
      diagnose; the ObjectiveChecker then grades the participant's
      answer as a mismatch.

    A malformed spec or a missing commit record is evidence FOR the
    stale verdict, never neutral.
    """

    commit_id = spec.get("commit_record")
    check = spec.get("check")
    stale_value = str(spec.get("stale_value", "reverify"))
    current_value = str(spec.get("current_value", "current"))
    missing_value = str(spec.get("missing_value", "no-evidence"))
    if not isinstance(commit_id, str) or not isinstance(check, str):
        return stale_value
    commit = env.records.get(commit_id)
    if not isinstance(commit, dict):
        return stale_value
    refs = commit.get("provenance")
    if not isinstance(refs, list):
        return stale_value
    matched = [
        record
        for ref in refs
        if isinstance(ref, str)
        and isinstance((record := env.records.get(ref)), dict)
        and record.get("check") == check
    ]
    if not matched:
        return missing_value
    current = env.check_revisions.get(check, 1)
    if any(
        isinstance(revision := record.get("protocol_revision"), int) and revision < current
        for record in matched
    ):
        return stale_value
    return current_value


def _stale_references(records: Mapping[str, dict[str, Any]]) -> tuple[str, ...]:
    """Record ids that a FINALIZED record still references while a later
    record supersedes them (reviewer 6.2 — the metric definition).

    Supersession is the participant's own ``supersedes`` field (the
    finalize-lock's sanctioned recovery path: create a NEW record that
    supersedes the stale one). The metric fires exactly when a
    finalized commit still points at the superseded record — the
    "finalized-then-invalidated conclusions still referenced" state the
    task card's scoring section names.
    """

    superseded: set[str] = set()
    for record in records.values():
        target = record.get("supersedes")
        if isinstance(target, str) and target in records:
            superseded.add(target)
    if not superseded:
        return ()
    stale: list[str] = []
    for record in records.values():
        if record.get("finalized") is not True:
            continue
        refs = record.get("provenance")
        if isinstance(refs, list):
            stale.extend(ref for ref in refs if isinstance(ref, str) and ref in superseded)
    return tuple(stale)


def _commit_gate_failures(
    precondition: Mapping[str, object],
    records: Mapping[str, dict[str, Any]],
    env: ProjectState,
    *,
    prior_finalized_record_ids: frozenset[str] = frozenset(),
    prior_records: Mapping[str, Mapping[str, Any]] | None = None,
    prior_verification_record_ids: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    """Evaluator-side commit legality over the sandbox's ACTUAL records.

    The participant's finalize ``Action`` preconditions are opt-in and
    participant-emitted; this gate is the evaluator's own copy, checked
    after the stages run, so a plain finalize of an illegal plan cannot
    pass the final check. Recognized keys (all optional):

    - ``record_id`` (str): the commit record whose legality is checked.
    - ``plan_field`` (str): the field on that record naming the plan.
    - ``legal_plans`` (list[str]): the derived legal plan set.
    - ``plan_requirements`` (mapping plan -> {domain, requires_check}):
      the committed plan's required verification, keyed by the sandbox
      records the commit references (its ``provenance`` list).
      ``requires_check`` may be ONE check name (str) or SEVERAL (list
      of str — the M2 "vector" decision type: the commit must cite a
      passing env-issued verification for EVERY named check; a plan
      passing only one of them fails).
    - ``current_revision`` (int) + ``revision_scope`` (list[str]):
      referenced records carrying a ``check`` in the scope must carry
      ``protocol_revision == current_revision``.
    - ``prior_finalized_record`` (str): a named award that the environment
      had finalized before this lifecycle began (a cross-session renewal
      cannot create its own prerequisite in the current session).
    - ``prior_verification`` (mapping): opt-in proof that the prior award
      cited an environment-issued PASS verification before this session.
      ``check`` names the verification, ``plan_field`` the prior record's
      plan field, and optional ``allowed_later_plans`` maps each prior
      plan value to its legal later plan values.

    Evidence truthfulness (external review 2026-09-22, deliverable A):
    a required verification counts ONLY when the ENVIRONMENT issued it
    (``env.verification_record_ids``), its ``subject`` names the
    committed plan, and its ``verdict`` is "pass". A participant-written
    record that merely carries ``check``/``protocol_revision`` is data,
    not evidence. Likewise the commit record must have been genuinely
    finalized through the env (``env.finalized_record_ids``) — a bare
    ``create_record`` with ``status="final"`` is a claim, not a state.
    """

    failures: list[str] = []
    if "prior_finalized_record" in precondition:
        prior_record = precondition["prior_finalized_record"]
        if not isinstance(prior_record, str) or not prior_record:
            raise ValueError("prior_finalized_record must name a non-empty record id")
        if prior_record not in prior_finalized_record_ids:
            failures.append(
                f"commit gate: prior finalized record {prior_record!r} was absent at session start"
            )
    record_id = precondition.get("record_id")
    if not isinstance(record_id, str):
        return tuple(failures)
    commit = records.get(record_id)
    if not isinstance(commit, dict):
        return (*failures, f"commit gate: record {record_id!r} is missing")
    plan_field = precondition.get("plan_field")
    if not isinstance(plan_field, str):
        return tuple(failures)
    plan = commit.get(plan_field)
    if not isinstance(plan, str):
        return (*failures, f"commit gate: record {record_id!r} lacks a {plan_field!r} value")
    if record_id not in env.finalized_record_ids:
        failures.append(
            f"commit gate: record {record_id!r} was never finalized through the "
            "environment (a self-declared status is not a finalized state)"
        )
    if "prior_verification" in precondition:
        prior_id = precondition.get("prior_finalized_record")
        if not isinstance(prior_id, str) or not prior_id:
            raise ValueError("prior_verification requires prior_finalized_record")
        if prior_records is None:
            raise ValueError("prior_verification requires a session-entry snapshot")
        if prior_id in prior_finalized_record_ids:
            failures.extend(
                _prior_verification_failures(
                    precondition["prior_verification"],
                    prior_id=prior_id,
                    later_plan=plan,
                    prior_records=prior_records,
                    prior_verification_record_ids=prior_verification_record_ids,
                )
            )
    legal = precondition.get("legal_plans")
    if isinstance(legal, list) and plan not in legal:
        failures.append(f"commit gate: plan {plan!r} is not in the legal set")
    refs = commit.get("provenance")
    referenced: list[dict[str, Any]] = []
    referenced_ids: list[str] = []
    if isinstance(refs, list):
        for ref in refs:
            record = records.get(ref) if isinstance(ref, str) else None
            if isinstance(record, dict):
                referenced.append(record)
                referenced_ids.append(ref)
            elif isinstance(ref, str):
                # A named reference that does not exist: evidence FOR
                # failure, never neutral (a garbage ref must not pass).
                failures.append(
                    f"commit gate: plan {plan!r} cites record {ref!r} which does "
                    "not exist in the sandbox"
                )
    requirements = precondition.get("plan_requirements")
    requirement = requirements.get(plan) if isinstance(requirements, Mapping) else None
    if isinstance(requirement, Mapping):
        # A plan named in plan_requirements must cite a NON-EMPTY set of
        # sandbox records: absence of references is evidence FOR the
        # failure, never neutral (reviewer 2.1R — a bare create_record
        # or a provenance-free finalize must not pass by citing
        # nothing).
        if not referenced:
            failures.append(
                f"commit gate: plan {plan!r} is committed without any referenced "
                "records; the required verifications are missing"
            )
        required_check = requirement.get("requires_check")
        # M2 "vector": ONE check (str) or SEVERAL (list/tuple). The gate
        # demands a passing env-issued verification for the committed
        # subject on EVERY named check — a plan passing only one of a
        # two-check requirement fails, with the MISSING check named.
        if isinstance(required_check, (str, list, tuple)):
            if isinstance(required_check, str):
                required_checks: tuple[str, ...] = (required_check,)
            else:
                required_checks = tuple(str(entry) for entry in required_check)
            environment_evidence = [
                (ref, record)
                for ref, record in zip(referenced_ids, referenced, strict=True)
                if ref in env.verification_record_ids
            ]
            for check_name in required_checks:
                qualifying = [
                    record
                    for _ref, record in environment_evidence
                    if record.get("check") == check_name
                    and record.get("subject") == plan
                    and record.get("verdict") == "pass"
                ]
                if not qualifying:
                    if environment_evidence:
                        failures.append(
                            f"commit gate: plan {plan!r} lacks an environment-issued "
                            f"{check_name!r} verification for subject {plan!r} "
                            "with a passing verdict among its referenced records"
                        )
                    else:
                        # Keyed by the COMMITTED PLAN, never by a
                        # participant-supplied domain field: the
                        # requirement applies because the world's
                        # precondition names this plan, not because the
                        # participant labeled it.
                        failures.append(
                            f"commit gate: plan {plan!r} lacks a "
                            f"{check_name!r} verification among its referenced records"
                        )
    current_revision = precondition.get("current_revision")
    scope = precondition.get("revision_scope")
    if (
        isinstance(current_revision, int)
        and not isinstance(current_revision, bool)
        and isinstance(scope, list)
    ):
        scope_set = {entry for entry in scope if isinstance(entry, str)}
        # PARTIAL supersession: the revision-currency rule applies to
        # in-scope checks ONLY for plans named in plan_requirements (the
        # rule change's scope); referenced in-scope checks of OTHER plans
        # are not invalidated (zephyr: rev-1 genre evidence is fine for
        # non-film candidates).
        # R1.1 SCOPED currency: the CURRENT revision for each check is
        # the env's per-check revision (an out-of-scope documentation
        # update never makes unrelated evidence stale); the precondition
        # value serves as the floor only when the env has no entry.
        scoped_plan = isinstance(requirement, Mapping)
        for record in referenced:
            check = record.get("check")
            if not (scoped_plan and isinstance(check, str) and check in scope_set):
                continue
            required_now = env.check_revisions.get(check, current_revision)
            if record.get("protocol_revision") != required_now:
                failures.append(
                    f"commit gate: plan {plan!r} relies on a stale "
                    f"{check!r} verification (revision "
                    f"{record.get('protocol_revision')!r}, current "
                    f"{required_now})"
                )
    return tuple(failures)


def _prior_verification_failures(
    raw_rule: object,
    *,
    prior_id: str,
    later_plan: str,
    prior_records: Mapping[str, Mapping[str, Any]],
    prior_verification_record_ids: frozenset[str],
) -> tuple[str, ...]:
    """Check a prior finalized award using only session-entry evidence."""

    if not isinstance(raw_rule, Mapping):
        raise ValueError("prior_verification must be a mapping")
    if set(raw_rule) - {"check", "plan_field", "allowed_later_plans"}:
        raise ValueError("prior_verification has unknown fields")
    check = raw_rule.get("check")
    plan_field = raw_rule.get("plan_field")
    if not isinstance(check, str) or not check:
        raise ValueError("prior_verification.check must be a non-empty string")
    if not isinstance(plan_field, str) or not plan_field:
        raise ValueError("prior_verification.plan_field must be a non-empty string")
    allowed_later_plans = raw_rule.get("allowed_later_plans")
    if allowed_later_plans is not None:
        if not isinstance(allowed_later_plans, Mapping) or not allowed_later_plans:
            raise ValueError("prior_verification.allowed_later_plans must be a non-empty mapping")
        for prior_plan, later_plans in allowed_later_plans.items():
            if (
                not isinstance(prior_plan, str)
                or not prior_plan
                or not isinstance(later_plans, list)
                or not later_plans
                or any(not isinstance(value, str) or not value for value in later_plans)
            ):
                raise ValueError("prior_verification.allowed_later_plans has invalid entries")

    prior = prior_records.get(prior_id)
    if not isinstance(prior, Mapping) or prior.get("finalized") is not True:
        return (
            f"commit gate: prior record {prior_id!r} is absent from the session-start snapshot",
        )
    prior_plan = prior.get(plan_field)
    if not isinstance(prior_plan, str) or not prior_plan:
        return (f"commit gate: prior record {prior_id!r} lacks a {plan_field!r} plan",)
    refs = prior.get("provenance")
    evidence_ids = refs if isinstance(refs, list) else []
    qualifying = any(
        isinstance(ref, str)
        and ref in prior_verification_record_ids
        and isinstance(evidence := prior_records.get(ref), Mapping)
        and evidence.get("performed_by") == "environment"
        and evidence.get("check") == check
        and evidence.get("subject") == prior_plan
        and evidence.get("verdict") == "pass"
        for ref in evidence_ids
    )
    failures: list[str] = []
    if not qualifying:
        failures.append(
            f"commit gate: prior record {prior_id!r} lacks a provenance-linked "
            f"environment-issued PASS {check!r} verification from session start "
            f"for subject {prior_plan!r}"
        )
    if allowed_later_plans is not None:
        allowed = allowed_later_plans.get(prior_plan)
        if not isinstance(allowed, list) or later_plan not in allowed:
            failures.append(
                f"commit gate: prior plan {prior_plan!r} does not allow later plan {later_plan!r}"
            )
    return tuple(failures)
