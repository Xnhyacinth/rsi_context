#!/usr/bin/env python3
"""S0->S1 improvement trajectory on the research-v3 world pool — replication-matrix capable.

Contract: review round 4 deliverable 5, now multi-round (round 5). Three
participants of DIFFERENT kinds (not a method competition):

  reference   scripted executor of a legal path (task solvability; not a
              capability result)
  fixed       memory-operational fixed agent (real reader; notes work,
              strategy never updates) — the "experience alone" control:
              the SAME dev stream, snapshot F0 frozen from it
  ds          the improvement arm: N rounds (S0 -> S1 -> ... -> SN).
              Default: a harness-scripted strategy. With --researcher:
              the DS model authors every round over feedback
              REGENERATED from the CURRENT snapshot's probe (round N
              sees round N-1's residual failures, not the initial
              ones); the strategy file is cumulative.

Every snapshot enters the SAME three evaluation branches
(continuation / new-world over the VARIANT worlds / regression) through
the frozen-snapshot carry — legitimate carry, no cross-branch writes.

--seed labels the run's provenance: branch session ids and instance
ids only. WORLD MATERIAL, branch surface order, and variant order are
seed-FREE (a scripted-arm trajectory is seed-independent offline; the
researcher arm varies across seeds only because the model re-authors
the strategy per run — the seed axis labels that variance, it does not
cause it).

Offline mode (--offline) verifies the WIRING with a deterministic fake
reader at zero API cost. --researcher is live-only. The improvement's
VALUE is not judged here: the deliverable is the closed, explainable,
now repeatable loop. S1 > S0 is neither required nor expected; the
record reports whatever happened.

Run from the repo root (SIFLOW_API_KEY exported for live mode).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from rsicontext.lifecycle.env import Action, ProjectState
from rsicontext.lifecycle.material_v3 import build_research_v3_instance
from rsicontext.lifecycle.runner import StageResponse, StageView, run_lifecycle
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.participant.snapshot import (
    BranchKind,
    FrozenSnapshot,
    LearningCarry,
    freeze_session,
    run_evaluation_branch,
)
from rsicontext.reader_tiers import MIN_VARIANCE_REPEATS as _MIN_VARIANCE_REPEATS
from rsicontext.security.isolated_policy import (
    PolicyIsolationUnavailable,
    require_isolated_policy_executor,
)
from rsicontext.session import SessionKind, SessionStateStore

READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
READER_SYSTEM = (
    "You are the migration project agent. Read the stage prompt and the "
    "documents. Answer concisely. When asked to commit, you will be given "
    "the action protocol. Output ONLY the requested content."
)
_CAP = 65536
_SCHEMA: dict[str, object] = {"type": "object", "properties": {"notes": {"type": "array"}}}
_COMMIT = "migration_commit"
_STATUS = "candidate_status"
_VARIANT_IDS = ("orinoco", "parana")
_OPTION2_IDS = ("zephyr", "quill", "atlas", "lumen", "swift", "mirror")
#: The DEV new-instance pool (external review 2.3/4.3: development feedback
#: must not flow through the evaluation pool's worlds — the probe that
#: regenerates the researcher's feedback runs DEV-DISTRIBUTION new instances,
#: disjoint from the held-out evaluation set). The authored variants serve
#: as the dev surface: transfer probes in the loop, never final-evaluation
#: worlds.
_DEV_UNSEEN_POOL: tuple[str, ...] = ()


class _RoundPayload(TypedDict):
    round: int
    snapshot_id: str
    authored_by: str
    researcher_record: dict[str, object] | None
    strategy_text: str
    state_update: dict[str, object]
    memory_notes: list[object]


#: T2 variance-floor ceiling (design-t2floor): the minimal reportable
#: contrast is 0.20 (hy3 precedent); the rejection ceiling sits at a
#: quarter of it. A floor SD above this rejects the reader for the block.
_VARIANCE_CEILING = 0.05

_KNOWN_CHECKS = (
    "replica-lag",
    "online-cutover",
    "disk-encryption",
    "soak-window",
    "retention",
    "checksum-drift",
    "acl-audit",
)


def _first_plan_name(survey_text: str) -> str:
    """The first candidate plan's name from the survey's doc markers.

    Every v3 world's candidate documents share the ``doc-cand-<key>``
    doc-id convention (authored worlds AND Option-2 real-document
    worlds), so the FIRST ``[[doc:doc-cand-<key>]]`` marker yields the
    plan key directly — no reliance on title text, which real KILT
    titles ('Play the Game (song)') do not follow. Falls back to the
    legacy title heuristic, then 'aurora'.
    """

    import re

    marker = re.search(r"\[\[doc:doc-cand-([a-z0-9_-]+)\]\]", survey_text)
    if marker and len(marker.group(1)) > 2:
        # Option-2 worlds key their candidate docs by the plan name
        # ('doc-cand-play-the-game'). Single-letter keys are the authored
        # worlds' doc order (doc-cand-a), not plan names — fall through
        # to the title heuristic there.
        return marker.group(1)
    # Legacy heuristic for material without the doc-cand convention.
    for line in survey_text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.endswith("plan") and " " in stripped:
            words = stripped.split()
            rest = words[1:] if words and words[0].startswith("[[doc:") else words
            if rest:
                return rest[0].lower()
    return "aurora"


def _rebind_instance_id(inst: LifecycleInstance, instance_id: str) -> LifecycleInstance:
    """A copy of the instance with a fresh instance id (branch-distinct)."""

    from dataclasses import replace

    return replace(inst, instance_id=instance_id)


def _survey_checks(survey_text: str) -> list[str]:
    """The check names the survey's protocol document mentioned, in order.

    World-generic: the authored worlds name their checks from
    ``_KNOWN_CHECKS``; the Option-2 real-document worlds name their check
    in their own protocol doc as "the <name> check" (genre, occupation,
    site, …), so the fallback derives the vocabulary from the material
    itself rather than a fixed list.
    """

    lowered = survey_text.lower()
    known = [check for check in _KNOWN_CHECKS if check in lowered]
    if known:
        return known
    import re

    names: list[str] = []
    for match in re.finditer(r"the ([a-z][a-z0-9\- ]{1,30}?) check\b", lowered):
        name = match.group(1).strip()
        if name and name not in names:
            names.append(name)
    return names


def _pass_fraction(branch_results: Mapping[str, object]) -> float:
    """The pass fraction over ALL branch cells — crashed cells count as 0.

    Rethinking-the-harness-evolution rule (spec Part 2.2):
    infrastructure failures are SCORED ZERO, never silently dropped from
    the denominator — a crashed cell used to leave the fraction's
    denominator, inflating the score (1 crash + 1 pass = 1.0). Now every
    cell that intended to run counts: ran=False cells contribute 0/1.
    """

    total = 0
    passed = 0
    for variants in branch_results.values():
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            if variant.get("ran") is False:
                total += 1
                continue
            for entry in variant.get("final_checks", []):
                if isinstance(entry, dict):
                    total += 1
                    passed += 1 if entry.get("passed") else 0
    return passed / total if total else 0.0


def _sample_sd(values: list[float]) -> float:
    """Sample standard deviation (ddof=1); 0.0 for fewer than 2 values."""

    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return float((sum((value - mean) ** 2 for value in values) / (len(values) - 1)) ** 0.5)


def _modal_share(values: list[float]) -> float:
    """The share of the most frequent value (the honesty statistic at
    small n with discrete scores: flip_rate = 1 - modal_share)."""

    if not values:
        return 0.0
    counts: dict[float, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.values()) / len(values)


def _reply_plan_name(reply: str, survey_text: str) -> str | None:
    """A candidate plan name the reader's reply states, validated against
    the CURRENT world's survey (a reply naming another world's plan —
    hallucinated or carried — does not pass the containment check)."""

    if not reply:
        return None
    # Candidate-name tokens: first words of the survey's title lines
    # (the v3 material convention — 'Aurora migration plan' etc.).
    tokens = _reply_plan_tokens(survey_text)
    for word in reply.replace(",", " ").replace(".", " ").split():
        cleaned = word.strip().strip("'\"").lower()
        if cleaned and cleaned in tokens:
            return cleaned
    return None


def _reply_plan_tokens(survey_text: str) -> set[str]:
    """The candidate-name token pool: the doc-cand keys (every v3 world
    shares the ``doc-cand-<key>`` doc-id convention), plus the legacy
    title-first-word heuristic for material without it."""

    import re

    tokens = {
        marker.group(1)
        for marker in re.finditer(r"\[\[doc:doc-cand-([a-z0-9_-]+)\]\]", survey_text)
        if len(marker.group(1)) > 2
    }
    for line in survey_text.splitlines():
        stripped = line.strip()
        if stripped.lower().endswith("plan"):
            words = stripped.split()
            rest = words[1:] if words and words[0].startswith("[[doc:") else words
            if rest:
                tokens.add(rest[0].lower())
    return tokens


def _reply_check_names(reply: str) -> list[str]:
    """The known check names present in the reader's reply, in order."""

    if not reply:
        return []
    lowered = reply.lower()
    return [check for check in _KNOWN_CHECKS if check in lowered]


def reader_call(
    prompt: str, *, offline: bool, offline_answers: dict[str, str] | None = None
) -> tuple[str, int, int]:
    if offline:
        assert offline_answers is not None
        for needle, answer in offline_answers.items():
            if needle in prompt:
                return answer, max(1, len(prompt) // 100), 32
        return "working notes", max(1, len(prompt) // 100), 8
    body = {
        "model": READER_MODEL,
        "messages": [
            {"role": "system", "content": READER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
        "temperature": 0.0,
        "seed": 42,
        "stream": False,
    }
    request = urllib.request.Request(
        READER_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['SIFLOW_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # READER_ENDPOINT is the fixed HTTPS Siflow chat-completions URL.
    with urllib.request.urlopen(request, timeout=300) as response:  # nosec B310
        raw = json.loads(response.read())
    message = raw["choices"][0]["message"]
    content = (message.get("content") or "").strip()
    usage = raw["usage"]
    return content, int(usage["prompt_tokens"]), int(usage["completion_tokens"])


class TrajectoryHook:
    """A reader-driven participant with working memory and a strategy file.

    The strategy file (code channel) is OPTIONAL: the DS arm's edited
    strategy replaces the built-in plan-choice heuristic; without it the
    hook is the fixed arm. This is the single seam where a code edit can
    change behavior — observable, accounted, and carried by snapshot.

    World-generic by construction: the hook's commit records are built
    from the world's OWN material (the survey prompt's candidate names
    and check names, which the participant legitimately read at stage 1)
    plus the strategy's declared profile when one exists. A strategy
    that hardcodes one world's plan names fails on other worlds — the
    transfer test the variant branches exist to run.
    """

    def __init__(
        self,
        state: dict[str, object],
        carry: LearningCarry | None = None,
        *,
        offline: bool = False,
        offline_answers: dict[str, str] | None = None,
        strategy_text: str | None = None,
    ) -> None:
        self.state = state
        self.carry = carry
        self.offline = offline
        self.offline_answers = offline_answers
        self.strategy_text = strategy_text
        self.tokens_in = 0
        self.tokens_out = 0
        self.calls = 0
        self.rereads: list[str] = []
        self.strategy_errors: list[str] = []
        self._survey_text = ""
        # Reader-derived decision inputs (the score-graded prerequisite:
        # the READER's replies feed plan/check decisions, not only notes).
        self._reader_survey_reply = ""
        self._reader_protocol_reply = ""
        # The verification-request channel (env-owned evidence): every
        # request this hook emits, by record id -> (check, subject). The
        # commit cites these — a record the env did not issue does not
        # exist as evidence.
        self._verification_requests: dict[str, tuple[str, str]] = {}
        # The subject plan fixed at the constraint stage (early/reread
        # requests share it so evidence stays subject-bound).
        self._request_subject: str | None = None

    def _strategy_namespace(self) -> dict[str, object]:
        if self.strategy_text is None:
            return {}
        if not self.offline:
            require_isolated_policy_executor()
        namespace: dict[str, object] = {}
        try:
            exec(self.strategy_text, namespace)
        except Exception as exc:
            # A crashing strategy is a NAMED outcome, never a silent
            # fallback: a broken researcher edit must be distinguishable
            # from "the improvement did not transfer" (reviewer 2.2).
            self.strategy_errors.append(f"strategy exec raised {type(exc).__name__}: {exc}")
            return {}
        return namespace

    def choose_plan(self) -> str:
        """Plan choice — the seam a strategy edit may improve.

        Fixed heuristic (no strategy): commit the FIRST candidate the
        survey presented (order-dependent, no constraint tracking — the
        fixed arm's characteristic weakness). A strategy file may
        provide ``choose_plan(survey_text)`` or a ``PLAN_PREFERENCE``
        list consulted against the survey's candidate names. A chooser
        that raises is recorded, not swallowed.
        """

        namespace = self._strategy_namespace()
        chooser = namespace.get("choose_plan")
        if callable(chooser):
            try:
                result = chooser(self._survey_text)
                if isinstance(result, str):
                    return result
            except Exception as exc:
                self.strategy_errors.append(f"choose_plan raised {type(exc).__name__}: {exc}")
        preference = namespace.get("PLAN_PREFERENCE")
        if isinstance(preference, list):
            for name in preference:
                if isinstance(name, str) and name in self._survey_text:
                    return name
        # Reader channel: a plan named in the reader's own survey reply
        # (the extraction surface) takes precedence over the doc-order
        # fallback — the reply is what the participant actually read out.
        reader_plan = _reply_plan_name(self._reader_survey_reply, self._survey_text)
        if reader_plan:
            return reader_plan
        # Fixed fallback: first candidate name mentioned in the survey.
        return _first_plan_name(self._survey_text)

    def _derived_checks(self) -> list[str]:
        """The check names for the commit: reader reply first, then survey.

        The reader's rule-change reply is the re-read surface (the
        check names it surfaced) — but a reply naming checks the
        CURRENT world's survey never contained (hallucinated or carried
        from another world) must not survive: reply checks are
        validated against the survey's own check vocabulary.
        """

        survey_checks = _survey_checks(self._survey_text)
        from_replies = _reply_check_names(self._reader_protocol_reply)
        validated = [check for check in from_replies if check in survey_checks]
        if validated:
            return validated
        return survey_checks

    def _request_checks(self) -> list[str]:
        """The checks to request from the environment's verification service.

        The strategy's WORLD_PROFILES (when one exists) names the checks
        per world; otherwise the check vocabulary is the world's own
        survey material. Requests are validated by the environment
        against its oracle — an uncovered (check, subject) pair is a
        NAMED refusal, never a fabricated pass.
        """

        namespace = self._strategy_namespace()
        profile = namespace.get("WORLD_PROFILES")
        checks: list[str] = []
        if isinstance(profile, dict):
            for entry in profile.values():
                if isinstance(entry, dict):
                    world_checks = entry.get("checks")
                    if isinstance(world_checks, list):
                        checks.extend(check for check in world_checks if isinstance(check, str))
        if not checks:
            checks = self._derived_checks()
        return checks

    def on_stage(self, stage: StageView) -> StageResponse:
        docs = "\n\n".join(f"[[doc:{d.doc_id}]] {d.title}\n{d.text}" for d in stage.documents)
        raw_notes = self.state.get("notes", [])
        notes = "\n".join(str(n) for n in raw_notes) if isinstance(raw_notes, list) else ""
        prompt = (
            f"Working notes so far:\n{notes or '(none)'}\n\n{stage.prompt_text}\n\n"
            f"Documents:\n{docs or '(none attached)'}"
        )
        reply, tokens_in, tokens_out = reader_call(
            prompt, offline=self.offline, offline_answers=self.offline_answers
        )
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out
        self.calls += 1
        if stage.kind == "survey":
            # Only the DOCUMENT BODY (never the working-notes prefix):
            # carried notes from other worlds mention their own plans,
            # and PLAN_PREFERENCE/survey derivation must see the CURRENT
            # world's material only.
            self._survey_text = docs
            # The reader's survey REPLY is a decision input: the fixed
            # fallback's plan derivation consults it (the reader is the
            # extraction channel; the strategy is the policy).
            self._reader_survey_reply = reply
        if stage.kind == "rule_change":
            # The reader's rule-change reply carries the check names the
            # re-read surfaced — the checks input for the commit.
            self._reader_protocol_reply = reply
        notes_list = list(raw_notes) if isinstance(raw_notes, list) else []
        notes_list.append({"stage": stage.stage_id, "summary": reply[:160]})
        self.state["notes"] = notes_list[-24:]

        # The verification service: verifications are REQUESTED from the
        # environment (env-issued, subject-bound, revision-timed); the
        # participant can no longer write an evidence record itself. The
        # fixed arm requests once, EARLY (constraint stage — evidence ages
        # with the protocol clock); the strategy decides whether to
        # RE-REQUEST after the rule change (STRATEGY_RERVERIFY: the env
        # re-executes at the current revision — a real re-verification,
        # not a rewritten label).
        stage_actions: tuple[Action, ...] = ()
        if stage.kind == "constraint_injection":
            checks = self._request_checks()
            subject = self.choose_plan()
            self._request_subject = subject
            for index, check in enumerate(checks):
                self._verification_requests[f"verif-early-{index}"] = (check, subject)
            stage_actions = tuple(
                Action(
                    kind="request_verification",
                    record_id=f"verif-early-{index}",
                    fields={"check": check, "subject": subject},
                )
                for index, check in enumerate(checks)
            )
        if stage.kind == "rule_change":
            namespace = self._strategy_namespace()
            if bool(namespace.get("STRATEGY_RERVERIFY", False)):
                # A REAL re-verification: the environment re-executes the
                # checks under the current revision. The reread
                # bookkeeping now records what was actually re-requested.
                checks = self._request_checks()
                subject = self._request_subject or self.choose_plan()
                for index, check in enumerate(checks):
                    self._verification_requests[f"verif-reread-{index}"] = (check, subject)
                rerequests = tuple(
                    Action(
                        kind="request_verification",
                        record_id=f"verif-reread-{index}",
                        fields={"check": check, "subject": subject},
                    )
                    for index, check in enumerate(checks)
                )
                stage_actions = rerequests
                self.rereads.append(f"reverify:{len(rerequests)}")
            else:
                # The reread path: re-consult the protocol document.
                self.rereads.append("doc-verif-db")

        if stage_actions:
            return StageResponse(
                pack_text=f"{stage.stage_id} [[doc:anchor]]", actions=stage_actions
            )
        if stage.kind != "act_verify":
            return StageResponse(pack_text=f"{stage.stage_id} [[doc:anchor]]")

        plan = self.choose_plan()
        actions = self._commit_actions(plan)
        return StageResponse(pack_text=f"commit {plan}", actions=tuple(actions))

    def _commit_actions(self, plan: str) -> list[Action]:
        """World-generic commit over ENVIRONMENT-ISSUED evidence.

        Verification records exist only through ``request_verification``
        (issued by the environment, subject-bound, revision-timed — the
        fixed arm's early requests and the strategy's post-rule-change
        re-requests land in the sandbox before this stage runs). The
        commit cites those records; it never writes an evidence record.
        The strategy decides ONE thing: whether to re-request after the
        rule change (STRATEGY_RERVERIFY — a real re-verification, not a
        rewritten revision label).
        """

        namespace = self._strategy_namespace()
        profile = namespace.get("WORLD_PROFILES")
        domain_by_plan: dict[str, str] = {}
        if isinstance(profile, dict):
            for entry in profile.values():
                if isinstance(entry, dict):
                    domains = entry.get("domains")
                    if isinstance(domains, dict):
                        domain_by_plan.update(
                            {
                                plan_name: domain
                                for plan_name, domain in domains.items()
                                if isinstance(plan_name, str) and isinstance(domain, str)
                            }
                        )
        domain = domain_by_plan.get(plan, "other")
        actions: list[Action] = []
        # Commit-time requests are the DEFERRED-VERIFICATION baseline: a
        # participant may verify everything at the end (the env stamps the
        # current revision; a fail verdict fails). But a pair already
        # requested earlier is NOT re-requested here — re-requesting is
        # exactly the STRATEGY's move (STRATEGY_RERVERIFY); the fixed arm
        # cites its early, aged evidence by design.
        requested_pairs = set(self._verification_requests.values())
        new_index = 0
        for check in self._request_checks():
            if (check, plan) in requested_pairs:
                continue
            record_id = f"verif-commit-{new_index}"
            new_index += 1
            self._verification_requests[record_id] = (check, plan)
            actions.append(
                Action(
                    kind="request_verification",
                    record_id=record_id,
                    fields={"check": check, "subject": plan},
                )
            )
        # Cite the plan's own evidence: every request whose subject IS the
        # committed plan (early requests may have used the stage-2 plan
        # choice; subject binding is what the evaluator's gate checks).
        # Per check, the FRESHEST record wins: a post-rule-change
        # re-request supersedes the early one for citation purposes
        # (the early record still exists — supersession is cite-side,
        # the env's revision clock is truth-side).
        by_check_early: dict[str, str] = {}
        by_check_fresh: dict[str, str] = {}
        for record_id, (check, subject) in self._verification_requests.items():
            if subject != plan:
                continue
            if record_id.startswith("verif-early-"):
                by_check_early.setdefault(check, record_id)
            else:
                by_check_fresh[check] = record_id
        refs: list[str] = [
            by_check_fresh.get(check, by_check_early.get(check, ""))
            for check in dict.fromkeys(check for check, _ in self._verification_requests.values())
        ]
        refs = [ref for ref in refs if ref]
        actions.append(
            Action(
                kind="create_record",
                record_id=f"{_STATUS}-{plan}",
                fields={"plan": plan, "domain": domain},
            )
        )
        refs.append(f"{_STATUS}-{plan}")
        actions.append(Action(kind="create_record", record_id=_COMMIT, fields={"plan": plan}))
        actions.append(
            Action(
                kind="finalize",
                record_id=_COMMIT,
                fields={"plan": plan, "status": "final"},
                provenance=tuple(refs),
            )
        )
        return actions


class ReferenceHook:
    """Scripted executor of the full-notes legal path (solvability, not capability).

    World-generic: the plan and checks come from the instance's own
    survey material via the module helpers, so the reference path runs
    on any v3 world (main or variant). Verifications are REQUESTED from
    the environment after the rule change (current-revision evidence);
    the commit cites the env-issued records.
    """

    def __init__(self) -> None:
        self.calls = 0
        self._survey_text = ""

    def on_stage(self, stage: StageView) -> StageResponse:
        self.calls += 1
        docs = "\n".join(f"[[doc:{d.doc_id}]] {d.title}\n{d.text}" for d in stage.documents)
        if stage.kind == "survey":
            self._survey_text = docs
            return StageResponse(pack_text="reference working notes")
        if stage.kind == "rule_change":
            # The reference path re-verifies after the rule change: env-issued,
            # subject-bound, current-revision evidence.
            checks = _survey_checks(self._survey_text)
            plan = _reference_plan(self._survey_text)
            return StageResponse(
                pack_text="reference re-verification",
                actions=tuple(
                    Action(
                        kind="request_verification",
                        record_id=f"verif-ref-{index}",
                        fields={"check": check, "subject": plan},
                    )
                    for index, check in enumerate(checks)
                ),
            )
        if stage.kind != "act_verify":
            return StageResponse(pack_text="reference working notes")
        checks = _survey_checks(self._survey_text)
        plan = _reference_plan(self._survey_text)
        actions: list[Action] = []
        refs: list[str] = [f"verif-ref-{index}" for index in range(len(checks))]
        actions.append(
            Action(
                kind="create_record",
                record_id=f"{_STATUS}-{plan}",
                fields={"plan": plan, "domain": "domain"},
            )
        )
        refs.append(f"{_STATUS}-{plan}")
        actions.append(Action(kind="create_record", record_id=_COMMIT, fields={"plan": plan}))
        actions.append(
            Action(
                kind="finalize",
                record_id=_COMMIT,
                fields={"plan": plan, "status": "final"},
                provenance=tuple(refs),
            )
        )
        return StageResponse(pack_text="reference commit", actions=tuple(actions))


def _reference_plan(survey_text: str) -> str:
    """The reference executor's plan: the FIRST plan-title candidate.

    On the main world this is 'aurora' (legal); on variant worlds the
    first candidate is likewise the legal-with-verification plan by
    construction (each variant's first candidate is its legal plan).
    """

    return _first_plan_name(survey_text)


def run_dev_session(
    hook_factory: Callable[[dict[str, object]], TrajectoryHook],
    *,
    session_id: str,
    online: bool = True,
) -> tuple[SessionStateStore, dict[str, int]]:
    """One dev session on the v3 world; the participant state persists in-store."""

    store = SessionStateStore(schema=_SCHEMA)
    store.begin_session(SessionKind.VISIBLE, session_id, _CAP)
    inst = build_research_v3_instance()

    state: dict[str, object] = {}
    hook = hook_factory(state)

    def run() -> None:
        # Refusals are recorded outcomes; the dev session continues.
        with contextlib.suppress(Exception):
            run_lifecycle(inst, hook, ProjectState())

    run()
    store.write(session_id, {"notes": state.get("notes", [])})
    totals = {
        "reader_calls": hook.calls,
        "tokens_in": hook.tokens_in,
        "tokens_out": hook.tokens_out,
    }
    return store, totals


def _world_identity(inst: LifecycleInstance) -> dict[str, str]:
    """The reproducibility record for one world instance (external review
    4.1: the artifact must state WHICH world ran, not just a seed).

    The instance id and a sha256 over the canonical to_dict of the
    instance's stages — the material hash. Two runs with the same world
    identity ran the same material; the seed axis alone proves nothing.
    """

    import hashlib

    payload = [stage.to_dict() for stage in inst.stages]
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return {
        "instance_id": inst.instance_id,
        "family": inst.family,
        "material_sha256": hashlib.sha256(blob).hexdigest()[:16],
    }


def evaluate_branches(
    snapshot: FrozenSnapshot,
    *,
    strategy_text: str | None,
    offline: bool,
    offline_answers: dict[str, str] | None,
    seed_suffix: str = "",
    unseen_rotation: int = 0,
    unseen_pool: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Run continuation / new-world / regression branches from one snapshot.

    The new-world branch runs over the UNSEEN-WORLD pool — the two
    authored variant worlds (orinoco/parana) PLUS the Option-2
    real-document worlds, round-robin over the two variant slots so
    every run exercises two different unseen worlds. A strategy whose
    improvement is structural (scope-aware invalidation) rather than
    topic-specific is thereby exercised on authored AND real material it
    never saw.
    ``seed_suffix`` makes branch session ids seed-distinct; the WORLD
    MATERIAL is never seed-dependent, and each branch record states the
    world identity + material hash it actually ran (reproducibility).
    ``unseen_pool`` selects between the DEV distribution (feedback
    probes — dev-distribution new instances, disjoint from the held-out
    set) and the EVALUATION distribution (the default: the held-out
    unseen pool).
    """

    results: dict[str, object] = {}
    branch_specs = (
        (BranchKind.CONTINUATION, "branch-cont", "main"),
        (BranchKind.NEW_WORLD, "branch-new", "unseen"),
        (BranchKind.REGRESSION, "branch-reg", "main"),
    )
    from rsicontext.lifecycle.material_v3_segment import build_option2_world
    from rsicontext.lifecycle.material_v3_variant import build_research_v3_variant

    variant_ids = _VARIANT_IDS
    option2_ids = _OPTION2_IDS if unseen_pool is None else unseen_pool

    def _unseen_world(slot: int) -> LifecycleInstance:
        # Slot 0 runs one AUTHORED variant world; slot 1 runs one
        # OPTION-2 real-document world — both indexed by the rotation
        # counter (derived from the run's seed, deterministic within a
        # run, distinct across seeds). Every run exercises unseen
        # material from both pools.
        if slot == 0:
            return build_research_v3_variant(variant_ids[unseen_rotation % len(variant_ids)])
        if option2_ids:
            return build_option2_world(option2_ids[unseen_rotation % len(option2_ids)])
        return build_research_v3_instance()

    for kind, session_id, surface in branch_specs:
        records: list[dict[str, object]] = []
        for variant in range(2):
            if surface == "unseen":
                inst = _rebind_instance_id(
                    _unseen_world(variant),
                    f"research-v3-{session_id}{seed_suffix}-{variant}",
                )
            else:
                inst = build_research_v3_instance(
                    instance_id=f"research-v3-{session_id}{seed_suffix}-{variant}"
                )
            world_identity = _world_identity(inst)
            try:
                captured: dict[str, list[TrajectoryHook]] = {"hooks": []}

                def make_hook_factory(
                    captured_box: dict[str, list[TrajectoryHook]],
                ) -> Callable[[dict[str, object], LearningCarry], TrajectoryHook]:
                    def hook_factory(
                        state: dict[str, object], carry: LearningCarry
                    ) -> TrajectoryHook:
                        hook = TrajectoryHook(
                            state,
                            carry,
                            offline=offline,
                            offline_answers=offline_answers,
                            strategy_text=strategy_text,
                        )
                        captured_box["hooks"].append(hook)
                        return hook

                    return hook_factory

                capturing_hook_factory = make_hook_factory(captured)

                branch_record = run_evaluation_branch(
                    snapshot,
                    kind,
                    f"{session_id}{seed_suffix}-{variant}",
                    instances=[inst],
                    hook_factory=capturing_hook_factory,
                    byte_cap=_CAP,
                )
                run_records = branch_record.run_records
                final_checks = [
                    {
                        "passed": record.final_check.passed,
                        "failures": list(record.final_check.failures),
                    }
                    for record in run_records
                ]
                # The one honest graded signal at matrix size (per
                # docs/research/analyze-grading-20260921.md): the count
                # of distinct commit-gate failures. 0 = pass; the
                # refused-cell case records None (never averaged over).
                gate_failure_counts = [
                    sum(
                        1
                        for failure in record.final_check.failures
                        if failure.startswith("commit gate:")
                    )
                    for record in run_records
                ]
                strategy_errors = [
                    error for hook in captured["hooks"] for error in hook.strategy_errors
                ]
                hook_totals = {
                    "reader_calls": sum(hook.calls for hook in captured["hooks"]),
                    "tokens_in": sum(hook.tokens_in for hook in captured["hooks"]),
                    "tokens_out": sum(hook.tokens_out for hook in captured["hooks"]),
                }
                records.append(
                    {
                        "variant": variant,
                        "ran": True,
                        "surface": surface,
                        "world": world_identity,
                        "final_checks": final_checks,
                        "gate_failure_counts": gate_failure_counts,
                        "strategy_errors": strategy_errors,
                        "hook_totals": hook_totals,
                    }
                )
            except Exception as exc:
                records.append(
                    {
                        "variant": variant,
                        "ran": False,
                        "surface": surface,
                        "world": world_identity,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        results[kind.value] = records
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="fake reader, zero API cost")
    parser.add_argument(
        "--researcher",
        action="store_true",
        help="the DS researcher model authors the S1 strategy (live; needs SIFLOW_API_KEY)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="improvement rounds: S0->S1->...->SN (feedback regenerated per round)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="provenance seed: branch/instance ids only; material and surfaces are seed-free",
    )
    parser.add_argument(
        "--variance-repeats",
        type=int,
        default=0,
        help="T2 variance floor: N fresh repeats of --variance-cell (0=off; >=5 required)",
    )
    parser.add_argument(
        "--variance-cell",
        type=str,
        default="S1",
        help="the snapshot whose branch cells the variance floor measures",
    )
    parser.add_argument(
        "--author-repeats",
        type=int,
        default=0,
        help=(
            "researcher-in-the-loop variance floor: N independent authoring "
            "rounds from the same S0 (0=off; >=2 required; live researcher "
            "mode measures real re-authoring, offline is the deterministic "
            "sd-0 shape)"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/trajectory-v3/trajectory-20260921.json"),
    )
    args = parser.parse_args()
    if args.rounds < 1:
        print("--rounds must be at least 1", file=sys.stderr)
        return 2
    if args.variance_repeats and args.variance_repeats < _MIN_VARIANCE_REPEATS:
        print(
            f"--variance-repeats must be at least {_MIN_VARIANCE_REPEATS} (T2 gate)",
            file=sys.stderr,
        )
        return 2
    if args.author_repeats and args.author_repeats < 2:
        print("--author-repeats must be at least 2", file=sys.stderr)
        return 2
    if args.author_repeats and args.rounds != 1:
        print("--author-repeats runs alongside --rounds 1 only", file=sys.stderr)
        return 2
    if args.researcher and args.offline:
        print("--researcher is live-only (the researcher is a real model)", file=sys.stderr)
        return 2
    if not args.offline:
        # Both the scripted and researcher-authored S1 strategies reach
        # TrajectoryHook's host-process exec. No fixed-only CLI mode exists.
        try:
            require_isolated_policy_executor()
        except PolicyIsolationUnavailable as exc:
            print(str(exc), file=sys.stderr)
            return 2

    started = time.monotonic()
    offline_answers = {
        "Constraint": (
            "The constraint applies to finance-domain plans: they must support online cutover."
        ),
        "Rule change": (
            "The revision supersedes the replica-lag check only; revision 2 tightens the threshold."
        ),
        "Survey": (
            "Five candidate plans: aurora (finance, online cutover), "
            "borealis (finance, hard freeze), cumulus (reporting), "
            "draco (analytics, thin replica-lag margin), ember (operations)."
        ),
    }

    # 1. Reference executor: task solvability (not a capability result).
    ref_record = run_lifecycle(build_research_v3_instance(), ReferenceHook(), ProjectState())
    reference = {
        "final_check_passed": ref_record.final_check.passed,
        "failures": list(ref_record.final_check.failures),
        "committed_plan": ref_record.sandbox_final_state.get(_COMMIT, {}).get("plan"),
    }

    # 2. Fixed arm: dev session, then F0 frozen (the experience control).
    fixed_store, fixed_totals = run_dev_session(
        lambda state: TrajectoryHook(state, offline=args.offline, offline_answers=offline_answers),
        session_id="dev-fixed",
    )
    f0 = freeze_session(
        fixed_store,
        "dev-fixed",
        agent_files_root=None,
        participant_id="fixed",
        snapshot_id="F0",
        byte_cap=_CAP,
    )

    # 3. DS arm: dev session -> S0; one improvement round -> S1.
    ds_store, ds_dev_totals = run_dev_session(
        lambda state: TrajectoryHook(state, offline=args.offline, offline_answers=offline_answers),
        session_id="dev-ds",
    )
    s0 = freeze_session(
        ds_store,
        "dev-ds",
        agent_files_root=None,
        participant_id="ds",
        snapshot_id="S0",
        byte_cap=_CAP,
    )

    # The dev-world probe: run the CURRENT snapshot over the three branch
    # kinds (dev surfaces only) to COLLECT the failure feedback for the
    # round — regenerated per round so round N sees round N-1's residual
    # failures, never the initial ones. FEEDBACK ISOLATION (external review
    # 2.3): the probe's new-world branch runs the DEV unseen pool (the
    # authored variants — transfer probes inside the loop), NEVER the
    # held-out Option-2 evaluation worlds, so evaluation-pool failures
    # cannot enter the improver's input.
    def probe(snapshot: FrozenSnapshot, strategy_text: str | None) -> dict[str, object]:
        return evaluate_branches(
            snapshot,
            strategy_text=strategy_text,
            offline=args.offline,
            offline_answers=offline_answers,
            seed_suffix=f"-s{args.seed}",
            unseen_rotation=args.seed,
            unseen_pool=_DEV_UNSEEN_POOL,
        )

    # Improvement rounds: S0 -> S1 -> ... -> SN. Each round's feedback
    # comes from the CURRENT snapshot's probe; the strategy file is
    # CUMULATIVE (round N's author sees round N-1's file in the stub
    # workspace); a failed or empty round keeps the previous strategy
    # (recorded, never silent).
    rounds_payload: list[_RoundPayload] = []
    strategy_text: str = _STRATEGY_STUB if args.researcher else _SCRIPTED_STRATEGY
    current = s0
    current_strategy: str | None = None  # S0 runs WITHOUT a strategy
    snapshots: dict[str, FrozenSnapshot] = {"S0": s0}
    branch_results: dict[str, dict[str, object]] = {}

    for round_index in range(args.rounds):
        researcher_record: dict[str, object] | None = None
        ds_state_update: dict[str, object] = {}
        if args.researcher:
            if args.offline:
                print("--researcher is live-only (the researcher is a real model)", file=sys.stderr)
                return 2
            if not os.environ.get("SIFLOW_API_KEY"):
                print("missing SIFLOW_API_KEY", file=sys.stderr)
                return 2
            import tempfile

            workspace = Path(tempfile.mkdtemp(prefix=f"ds-agent-r{round_index}-"))
            agent_dir = workspace / "agent"
            agent_dir.mkdir(parents=True, exist_ok=True)
            stub = agent_dir / "strategy.py"
            # Round N's author sees round N-1's strategy (cumulative).
            stub.write_text(strategy_text, encoding="utf-8")
            feedback = _dev_feedback_bytes(probe(current, current_strategy))
            try:
                changes, usage, round_attempts = _researcher_round(
                    stub, feedback, round_index=round_index
                )
                usage = dict(usage, attempts=round_attempts)
                proposed = changes.get("strategy.py")
                if proposed is None or not proposed.strip():
                    researcher_record = {
                        "round_outcome": "no-strategy-file",
                        "changes": sorted(changes),
                        "usage": usage,
                    }
                    # Keep the previous strategy.
                else:
                    researcher_record = {
                        "round_outcome": "ok",
                        "changes": sorted(changes),
                        "usage": usage,
                    }
                    strategy_text = proposed
            except Exception as exc:
                # The attempt log rides on the exception when the round
                # failed inside the improver (endpoint reliability
                # evidence for the failure record).
                failure_attempts = getattr(exc, "attempts", None)
                usage_payload: dict[str, object] = {}
                if isinstance(failure_attempts, list):
                    usage_payload = {"attempts": [dict(e) for e in failure_attempts]}
                researcher_record = {
                    "round_outcome": f"failed: {type(exc).__name__}: {exc}",
                    "changes": [],
                    "usage": usage_payload,
                }
            ds_state_update = {
                "notes": [
                    f"round {round_index} ran; see rounds[{round_index}] for its outcome",
                ]
            }
        else:
            # Scripted mode: the world-generic fix applies in round 0;
            # later rounds keep it (the script has no further edits).
            if round_index == 0:
                strategy_text = _SCRIPTED_STRATEGY
                ds_state_update = {
                    "notes": [
                        "rule changes invalidate only in-scope verifications",
                        "re-verify in-scope checks under the current revision before commit",
                    ]
                }
            else:
                ds_state_update = {
                    "notes": [f"round {round_index}: strategy unchanged (scripted arm)"],
                }
        snapshot_id = f"S{round_index + 1}"
        current_strategy = strategy_text
        current = _freeze_from_parts(current, snapshot_id, strategy_text, ds_state_update)
        snapshots[snapshot_id] = current
        current_notes = current.memory.get("notes", [])
        rounds_payload.append(
            {
                "round": round_index,
                "snapshot_id": snapshot_id,
                "authored_by": "researcher" if args.researcher else "harness-script",
                "researcher_record": researcher_record,
                "strategy_text": strategy_text,
                "state_update": ds_state_update,
                # The frozen snapshot's ACCUMULATED memory (audit view of
                # the carry contract: earlier rounds' notes survive).
                "memory_notes": list(current_notes) if isinstance(current_notes, list) else [],
            }
        )

    # 4. The three branches per snapshot: S0 (no strategy), every S_n,
    # and the fixed F0 control.
    fixed_branches = evaluate_branches(
        f0,
        strategy_text=None,
        offline=args.offline,
        offline_answers=offline_answers,
        seed_suffix=f"-s{args.seed}",
        unseen_rotation=args.seed,
    )
    branch_results["S0"] = evaluate_branches(
        s0,
        strategy_text=None,
        offline=args.offline,
        offline_answers=offline_answers,
        seed_suffix=f"-s{args.seed}",
        unseen_rotation=args.seed,
    )
    for round_index in range(1, args.rounds + 1):
        snapshot_id = f"S{round_index}"
        branch_results[snapshot_id] = evaluate_branches(
            snapshots[snapshot_id],
            strategy_text=rounds_payload[round_index - 1]["strategy_text"],
            offline=args.offline,
            offline_answers=offline_answers,
            seed_suffix=f"-s{args.seed}",
            unseen_rotation=args.seed,
        )

    # 5. T2 variance floor (optional, per docs/research/design-t2floor-20260921.md):
    # N FRESH repeats of the chosen snapshot's branch cells — fresh-request
    # replay variance only (policy identical: same strategy, temp 0, seed 42),
    # session ids distinct per repeat. The floor bounds what a reported
    # score delta must exceed; it does NOT cover researcher re-authoring,
    # dev-session drift, or cross-run endpoint drift.
    variance_floor: dict[str, object] | None = None
    if args.variance_repeats:
        if args.variance_cell == "F0":
            floor_snapshot, floor_strategy = f0, None
        elif args.variance_cell == "S0":
            floor_snapshot, floor_strategy = s0, None
        elif args.variance_cell in snapshots:
            floor_snapshot = snapshots[args.variance_cell]
            floor_strategy = rounds_payload[int(args.variance_cell[1:]) - 1]["strategy_text"]
        else:
            print(f"unknown --variance-cell: {args.variance_cell}", file=sys.stderr)
            return 2
        scores: list[float] = []
        for repeat in range(args.variance_repeats):
            repeat_results = evaluate_branches(
                floor_snapshot,
                strategy_text=floor_strategy,
                offline=args.offline,
                offline_answers=offline_answers,
                seed_suffix=f"-s{args.seed}-vr{repeat}",
                unseen_rotation=args.seed,
            )
            scores.append(_pass_fraction(repeat_results))
        sd = _sample_sd(scores)
        flip_rate = 1.0 - (_modal_share(scores) if scores else 0.0)
        variance_floor = {
            "cell": args.variance_cell,
            "repeats": args.variance_repeats,
            "scores": scores,
            "sd": sd,
            "flip_rate": flip_rate,
            "ceiling": _VARIANCE_CEILING,
            "within_ceiling": sd <= _VARIANCE_CEILING,
        }

    # 6. Researcher-in-the-loop variance floor (optional): N INDEPENDENT
    # authoring rounds from the SAME S0 with the SAME feedback (round 0's
    # probe) — each variant S1_k is a fresh authoring draw, evaluated on
    # the branch cells. In researcher mode this measures the model's
    # re-authoring variance (the source the T2 floor cannot cover); in
    # scripted mode it is the deterministic sd-0 shape. The comparison
    # S1 vs S0 must exceed max(2*sd_author, floor) to be an authoring
    # effect rather than a re-draw.
    author_variance: dict[str, object] | None = None
    if args.author_repeats:
        # DEV pool again (feedback isolation: the author-draw feedback is
        # regenerated from dev-distribution surfaces, never the eval pool).
        author_feedback = _dev_feedback_bytes(
            evaluate_branches(
                s0,
                strategy_text=None,
                offline=args.offline,
                offline_answers=offline_answers,
                seed_suffix=f"-s{args.seed}-probe",
                unseen_rotation=args.seed,
                unseen_pool=_DEV_UNSEEN_POOL,
            )
        )
        variant_scores: list[float] = []
        variant_records: list[dict[str, object]] = []
        for repeat in range(args.author_repeats):
            # Independent authoring draw from the SAME S0 + feedback.
            repeat_strategy: str
            if args.researcher:
                import tempfile

                workspace = Path(tempfile.mkdtemp(prefix=f"ds-author-r{repeat}-"))
                agent_dir = workspace / "agent"
                agent_dir.mkdir(parents=True, exist_ok=True)
                stub = agent_dir / "strategy.py"
                stub.write_text(_STRATEGY_STUB, encoding="utf-8")
                draw_usage: dict[str, object] = {}
                draw_attempts: list[dict[str, object]] = []
                try:
                    changes, usage, draw_attempt_log = _researcher_round(
                        stub, author_feedback, round_index=repeat
                    )
                    draw_usage = usage
                    draw_attempts = draw_attempt_log
                    proposed = changes.get("strategy.py")
                    if proposed is None or not proposed.strip():
                        repeat_strategy = _STRATEGY_STUB
                        outcome = "no-strategy-file"
                    else:
                        repeat_strategy = proposed
                        outcome = "ok"
                except Exception as exc:
                    # A failed draw: usage stays {} (never a stale value
                    # from a previous draw — the record must not carry
                    # another draw's numbers). The exception's attempt log
                    # (ResearcherRoundFailure.attempts) IS the draw's own
                    # reliability evidence: copy it (external review 4.3 —
                    # the failure path loses the per-attempt record when it
                    # is not carried over).
                    repeat_strategy = _STRATEGY_STUB
                    outcome = f"failed: {type(exc).__name__}: {exc}"
                    failure_attempts = getattr(exc, "attempts", None)
                    if isinstance(failure_attempts, list):
                        draw_attempts = [dict(entry) for entry in failure_attempts]
                usage_record = draw_usage
                # Per-attempt reliability evidence: the retry loop's
                # attempt log distinguishes transport/empty failures
                # from authoring variance (the floor's de-conflation).
                usage_record = dict(usage_record, attempts=draw_attempts)
            else:
                # Scripted arm: the deterministic strategy (sd 0 by
                # construction — the offline shape pin).
                repeat_strategy = _SCRIPTED_STRATEGY
                outcome = "scripted"
                usage_record = {}
            variant_snapshot = _freeze_from_parts(
                s0, f"S1a{repeat}", repeat_strategy, {"notes": [f"author draw {repeat}"]}
            )
            variant_results = evaluate_branches(
                variant_snapshot,
                strategy_text=repeat_strategy,
                offline=args.offline,
                offline_answers=offline_answers,
                seed_suffix=f"-s{args.seed}-ar{repeat}",
                unseen_rotation=args.seed,
            )
            variant_scores.append(_pass_fraction(variant_results))
            variant_records.append(
                {
                    "repeat": repeat,
                    "outcome": outcome,
                    "strategy_head": repeat_strategy[:200],
                    "score": variant_scores[-1],
                    "usage": usage_record,
                }
            )
        author_sd = _sample_sd(variant_scores)
        author_variance = {
            "repeats": args.author_repeats,
            "variant_scores": variant_scores,
            "sd": author_sd,
            "flip_rate": 1.0 - (_modal_share(variant_scores) if variant_scores else 0.0),
            "variants": variant_records,
        }

    elapsed = time.monotonic() - started
    failed_rounds = []
    for round_record in rounds_payload:
        researcher_record = round_record["researcher_record"]
        if isinstance(researcher_record, dict) and str(
            researcher_record.get("round_outcome", "")
        ).startswith("failed:"):
            failed_rounds.append(round_record["round"])
    payload = {
        "mode": "offline" if args.offline else "live",
        "reader_model": None if args.offline else READER_MODEL,
        "seed": args.seed,
        "rounds": args.rounds,
        "failed_rounds": failed_rounds,
        "variance_floor": variance_floor,
        "author_variance": author_variance,
        "world": "research-v3-main-0001",
        "reference_executor": reference,
        "fixed_arm": {
            "snapshot": "F0",
            "dev_totals": fixed_totals,
            "branches": fixed_branches,
        },
        "ds_arm": {
            "snapshot": "S0",
            "dev_totals": ds_dev_totals,
            "rounds": rounds_payload,
            "snapshot_branches": branch_results,
        },
        "elapsed_seconds": round(elapsed, 1),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    print(
        json.dumps(
            {
                k: payload[k]
                for k in (
                    "mode",
                    "seed",
                    "rounds",
                    "failed_rounds",
                    "reference_executor",
                    "elapsed_seconds",
                )
            },
            indent=1,
        )
    )
    print(f"artifact: {args.output}")
    if failed_rounds:
        # A failed researcher round produced this artifact: the matrix
        # was NOT fully produced (the code-review S1 finding — a wholly
        # failed loop must not exit 0 looking like a complete matrix).
        print(
            f"failed rounds: {failed_rounds} (see rounds[].researcher_record)",
            file=sys.stderr,
        )
        return 3
    return 0


def _freeze_from_parts(
    s0: FrozenSnapshot, snapshot_id: str, strategy_text: str, state_update: dict[str, object]
) -> FrozenSnapshot:
    """Freeze S_n = S_{n-1}'s memory (ACCUMULATED) + this round's additions + strategy file.

    The carry contract: legitimate learned material accumulates across
    snapshots. The parent snapshot's notes carry forward and this round's
    notes APPEND (deduplicated, order-preserving); other memory keys from
    the parent survive unless the round's update names the same key.
    """

    memory: dict[str, object] = dict(s0.memory)
    prior_notes = memory.get("notes")
    prior_list: list[object] = list(prior_notes) if isinstance(prior_notes, list) else []
    added_notes = state_update.get("notes")
    if isinstance(added_notes, list):
        seen = {json.dumps(note, sort_keys=True) for note in prior_list}
        for note in added_notes:
            key = json.dumps(note, sort_keys=True)
            if key not in seen:
                prior_list.append(note)
                seen.add(key)
    memory["notes"] = prior_list
    for key, value in state_update.items():
        if key != "notes":
            memory[key] = value
    return FrozenSnapshot.from_parts(
        participant_id=s0.participant_id,
        snapshot_id=snapshot_id,
        memory=memory,
        code_files={"strategy.py": strategy_text},
        skill_files=dict(s0.skill_files),
        schema=s0.schema,
        byte_cap=s0.byte_cap,
    )


# --- researcher mode: the DS model authors the S1 strategy ----------------------

_RESEARCHER_MODEL = "deepseek-ai/deepseek-v4.1-flash"
_STRATEGY_STUB = (
    '"""Migration-commit strategy. The researcher may rewrite this file.\n\n'
    "The harness executes this file once per stage and reads these names:\n"
    "  STRATEGY_RERVERIFY  bool — re-verify in-scope checks after a rule change\n"
    "  WORLD_PROFILES      dict — per-world 'checks' lists and 'domains' maps\n"
    "  PLAN_PREFERENCE     list — plan names preferred over survey order\n"
    "  choose_plan(survey_text) -> str — optional full override\n"
    '"""\n'
    "STRATEGY_RERVERIFY = False\n"
    "WORLD_PROFILES = {}\n"
    "PLAN_PREFERENCE = []\n"
)
#: The harness-scripted strategy (the rehearsal arm): the world-generic
#: scope-aware invalidation fix, with per-world profiles for the main and
#: variant worlds. Round 0 applies it; later scripted rounds keep it.
_SCRIPTED_STRATEGY = (
    "# DS improvement: scope-aware invalidation (world-generic)\n"
    "STRATEGY_RERVERIFY = True\n"
    "WORLD_PROFILES = {\n"
    "  'main': {\n"
    "    'checks': ['online-cutover', 'replica-lag'],\n"
    "    'domains': {'aurora': 'finance', 'borealis': 'finance'},\n"
    "  },\n"
    "  'orinoco': {\n"
    "    'checks': ['soak-window', 'retention'],\n"
    "    'domains': {'kestrel': 'billing', 'lark': 'billing'},\n"
    "  },\n"
    "  'parana': {\n"
    "    'checks': ['checksum-drift', 'acl-audit'],\n"
    "    'domains': {'basalt': 'archive', 'cobble': 'archive'},\n"
    "  },\n"
    "}\n"
    "PLAN_PREFERENCE = ['aurora', 'kestrel', 'basalt']\n"
)


def _researcher_round(
    strategy_stub_path: Path, dev_feedback: bytes, round_index: int
) -> tuple[dict[str, str], dict[str, object], list[dict[str, object]]]:
    """One REAL improvement round: the DS researcher rewrites the strategy.

    Returns (agent_files_changed, usage_record, attempts_log). Failures
    raise — the caller records them as the round's outcome (a failed
    round is a recorded result, never a silent no-change). The attempts
    log is the improver's per-attempt reliability record: the
    retry-loop's view of transport/empty failures, so the caller can
    separate endpoint reliability from authoring variance.
    """

    require_isolated_policy_executor()

    from rsicontext.participant.api_researcher import (
        APIResearcherConfig,
        APIResearcherImprover,
        RetryPolicy,
    )
    from rsicontext.participant.registration import ImprovementRoundInput

    agent_dir = strategy_stub_path.parent
    # The empty-content failure observed in matrix 3 was retry-resistant
    # at the default 3 attempts: strengthen the policy for trajectory
    # rounds (5 attempts, longer backoff) so persistent-but-transient
    # endpoint states recover where the default gave up. Deterministic
    # protocol failures still pass through on the first attempt.
    improver = APIResearcherImprover(
        config=APIResearcherConfig(
            endpoint=READER_ENDPOINT,
            model=_RESEARCHER_MODEL,
            retry=RetryPolicy(max_attempts=5, backoff_seconds=10.0),
        )
    )
    round_input = ImprovementRoundInput(
        round_index=round_index,
        task_text=(
            "Improve the commit strategy for a five-stage migration-decision "
            "workflow. The strategy file is executed by the participant "
            "harness: keep the interface (STRATEGY_RERVERIFY bool, "
            "WORLD_PROFILES dict with per-world 'checks' and 'domains', "
            "PLAN_PREFERENCE list, optional choose_plan(survey_text)). The "
            "known failure mode: after a rule change supersedes specific "
            "checks, the agent commits verification evidence recorded under "
            "the OLD protocol revision and the evaluator gate refuses the "
            "commit. A WORLD-GENERIC policy is required: the strategy runs "
            "on unseen worlds with different plan names, domains, and check "
            "names — hardcoding one world's names will fail elsewhere. "
            "Rewrite strategy.py."
        ),
        restricted_feedback_bytes=dev_feedback,
        current_agent_dir=agent_dir,
        state_path=None,
        remaining_slots=1,
        task_order_seed=11,
    )
    try:
        output = improver.improve(round_input)
    except Exception:
        # Attach the retry loop's attempt log to the failure so the
        # caller's failure record carries the reliability evidence
        # (which attempt failed, with what outcome) — the de-conflation
        # data must survive the exception path.
        attempts = [dict(entry) for entry in improver.attempts()]
        raise ResearcherRoundFailure(attempts) from None
    usage: dict[str, object] = {
        "input_tokens": output.usage.input_tokens,
        "output_tokens": output.usage.output_tokens,
        "wall_seconds": output.usage.wall_seconds,
    }
    attempts = [dict(entry) for entry in improver.attempts()]
    return dict(output.agent_files_changed), usage, attempts


class ResearcherRoundFailure(Exception):
    """Raised with the improver's attempt log attached (``.attempts``)."""

    def __init__(self, attempts: list[dict[str, object]]) -> None:
        super().__init__(f"researcher round failed after {len(attempts)} attempts")
        self.attempts = attempts


def _dev_feedback_bytes(ds_branch_record: object) -> bytes:
    """Restricted feedback from the DS arm's dev session: what failed.

    The F-schema subset the improver consumes: stage-level failures with
    the named causes (the gate's refusal messages), never gold material.
    """

    import json as _json

    failures: list[str] = []
    if isinstance(ds_branch_record, dict):
        for branch in ("continuation", "new_world", "regression"):
            for variant in ds_branch_record.get(branch, []):
                if isinstance(variant, dict):
                    if variant.get("error"):
                        failures.append(f"{branch}: {variant['error']}")
                    for entry in variant.get("final_checks", []):
                        if isinstance(entry, dict):
                            failures.extend(
                                f"{branch}: {failure}" for failure in entry.get("failures", [])
                            )
    payload = {
        "stage": "dev-evaluation",
        "failures": failures[:32],
        "instruction": "The commit gate named these failures on the dev worlds.",
    }
    return _json.dumps(payload).encode("utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
