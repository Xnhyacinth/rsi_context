"""The B/C GROUP BASELINES (r3design §3/4, research-v5).

Two controls grown from ``strong_model_fixed`` — the SAME worker model
through ``turn.ask_model``, the SAME orchestration-only contract (no
hardcoded world answers; swap the facts and the outputs follow the
model's reading of the material):

- B_BASELINE ("carry-aware strong-fixed"): everything strong-fixed
  does, plus the four session-boundary behaviors — distill at
  session_end into ``state['carry']``, distrust stale carry at
  session_start, re-derive the survey in a NEW project (never answer
  from carry), and re-request a NEW verification id at the CURRENT
  revision for the post-rule-change re-award.
- C_BASELINE ("receipt-reading strong-fixed"): everything B does,
  plus the execution-recovery loop — probe-verify the chosen candidate
  ONLY and end the turn (the verdict arrives as a receipt next turn),
  accumulate receipts into ``state['seen_receipts']`` every turn
  (receipts drain per turn), commit only on a seen pass, ask the
  worker for the next candidate on a seen fail, and re-verify
  post-mutation before committing in session 2.

The action SHAPES (verification id provenance, finalize provenance,
record names) are lifted from the B/C acceptance tests' pinned
skeletons; every NAME of a supplier or check is the worker's parsed
reply, never a literal.
"""

from __future__ import annotations

B_BASELINE = """
BATCH_DOCS = 6
CARRY_LIMIT = 6000

RECORD_COMMIT = "migration_commit"
RECORD_REAWARD = "corridor_reaward"
RECORD_STATUS = "candidate_status-"
RECORD_CONCLUSION = "followup_conclusion-"


def _ask(turn, prompt):
    reply = turn.ask_model(prompt)
    return reply.content if reply.ok else ""


def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        docs = turn.view.documents
        state.setdefault("notes", {})
        for start in range(0, len(docs), BATCH_DOCS):
            batch = docs[start : start + BATCH_DOCS]
            body = "\\n\\n".join(d.text for d in batch)
            reply = _ask(
                turn,
                "You are building working notes for a supplier-selection "
                "project. From the material below, extract ONLY: (a) any "
                "supplier whose EXCEPTION CLAUSE qualifies them for a "
                "verification check (quote the clause), (b) any supplier "
                "with a buried DISQUALIFYING condition (quote it), (c) any "
                "supplier described as covering specific checkpoints or "
                "hubs, (d) the names of any verification checks mentioned. "
                "Reply in <= 120 words of notes.\\n\\n" + body,
            )
            if reply:
                state["notes"]["batch-%d" % start] = reply
        return {"pack_text": "survey notes built"}
    if kind == "constraint_injection":
        constraint = "\\n".join(d.text for d in turn.view.documents)
        reply = _ask(
            turn,
            "Project constraint received: " + constraint
            + "\\n\\nFrom your retained notes: "
            + _notes(state)
            + "\\n\\nWhich verification check does this constraint require "
            "for the award, and which supplier(s) from the notes could "
            "satisfy it? Reply with one line: 'check=<name> "
            "candidate=<supplier>'.",
        )
        state["constraint_reply"] = reply
        return {"pack_text": "constraint analyzed"}
    if kind == "rule_change":
        rule = "\\n".join(d.text for d in turn.view.documents)
        reply = _ask(
            turn,
            "Rule change received: " + rule
            + "\\n\\nFrom your retained notes: " + _notes(state)
            + "\\n\\nDoes this change invalidate any verification evidence "
            "you hold? Reply with one line: 'invalidates=<check or none>'.",
        )
        state["rule_reply"] = reply
        return {"pack_text": "rule change analyzed"}
    if kind == "session_start":
        # Re-hydrate: the carry is already in state (the sequence runner
        # seeds it). Ask the worker whether any retained conclusion
        # might be stale given the last known rule analyses.
        carry = _carry(state)
        if not carry:
            return {"pack_text": "resume (empty carry)"}
        reply = _ask(
            turn,
            "Session resume. Retained conclusions from the previous "
            "session:\\n" + carry
            + "\\nRule analyses held: " + state.get("rule_reply", "")
            + "\\n\\nMight any retained conclusion be stale given the last "
            "known state? Reply with one line: "
            "'stale=<conclusion or none>'.",
        )
        state["carry_check"] = reply
        return {"pack_text": "resume checked"}
    if kind == "session_end":
        # Distill: ask the worker over the retained notes what must
        # survive; the reply becomes the carry (byte-capped by the
        # runner's flush, not by the policy). The structured facts the
        # worker already produced (its parsed replies) ride along so a
        # session-2 decision can re-cite them.
        reply = _ask(
            turn,
            "Session end. Working state is about to be destroyed; only "
            "state['carry'] persists (byte-capped). Retained notes:\\n"
            + _notes(state)
            + "\\n\\nWhat must survive to the next session? Distill the "
            "load-bearing conclusions (award, calibration, scope) in <= "
            "150 words.",
        )
        carry = state.get("carry", {})
        if not isinstance(carry, dict):
            carry = {}
        carry["distilled"] = (reply or "")[:CARRY_LIMIT]
        if state.get("supplier"):
            carry["award"] = state["supplier"]
        if state.get("constraint_reply"):
            carry["check_reply"] = state["constraint_reply"][:2000]
        if state.get("rule_reply"):
            carry["rule_reply"] = state["rule_reply"][:2000]
        notes = _notes(state)
        if notes:
            carry["notes"] = notes[:CARRY_LIMIT]
        state["carry"] = carry
        return {"pack_text": "carry distilled"}
    if kind == "act_verify":
        stage_id = turn.view.stage_id
        re_award = "re-award" in stage_id or "reaward" in stage_id
        if re_award:
            return _re_award(turn, state)
        return _award(turn, state)
    if kind == "follow_up":
        doc = turn.view.documents[0].text if turn.view.documents else ""
        if "calibration" in doc:
            reply = _ask(
                turn,
                "A lab calibration partner is needed for the awarded "
                "corridor. Retained conclusions:\\n" + _carry(state)
                + "\\nRetained notes: " + _notes(state)
                + "\\n\\nWhich instrument supplier covers the same "
                "checkpoints? Reply with exactly 'supplier=<id>' where "
                "<id> is the supplier's kebab-case id exactly as "
                "printed in the card headers (the id after 'Supplier "
                "card:'), and nothing else.",
            )
            supplier = _extract_value(reply, "supplier")
            return {
                "pack_text": "calibration " + str(supplier),
                "actions": (
                    turn.actions.create_record(
                        RECORD_CONCLUSION + "calibration",
                        {"supplier": supplier},
                    ),
                ),
            }
        reply = _ask(
            turn,
            "The corridor contract is up for review. Retained notes: "
            + _notes(state)
            + "\\nRetained conclusions:\\n" + _carry(state)
            + "\\nRule analyses held: "
            + state.get("rule_reply", "")
            + "\\n\\nWas the award's verification evidence acquired "
            "before or after the latest rule change that affects its "
            "check? Is that evidence still current? Reply with exactly "
            "'status=<current or reverify>'.",
        )
        status = _extract_value(reply, "status")
        if status not in ("current", "reverify"):
            retry = _ask(
                turn,
                "Your previous answer was not parseable. Answer with "
                "exactly 'status=<current or reverify>' and nothing else.",
            )
            status = _extract_value(retry, "status")
        if status not in ("current", "reverify"):
            status = "undetermined"
        return {
            "pack_text": "corridor " + str(status),
            "actions": (
                turn.actions.create_record(
                    RECORD_CONCLUSION + "corridor", {"status": status}
                ),
            ),
        }
    return {"pack_text": "ok"}


def _award(turn, state):
    choice = _ask(
        turn,
        "Retained notes: " + _notes(state)
        + "\\nConstraint analysis: " + state.get("constraint_reply", "")
        + "\\n\\nName the ONE supplier to award (the one whose "
        "qualification satisfies the required check). Reply with "
        "exactly 'supplier=<id>' where <id> is the supplier's "
        "kebab-case id exactly as printed in the card headers "
        "(the id after 'Supplier card:'), and nothing else.",
    )
    supplier = _extract_value(choice, "supplier")
    check = _extract_value(state.get("constraint_reply", ""), "check")
    if not check:
        check = _extract_value(
            _ask(
                turn,
                "From your retained notes: " + _notes(state)
                + "\\n\\nName the verification check the award "
                "requires. Reply with exactly 'check=<name>'.",
            ),
            "check",
        )
    if not check:
        check = "undetermined-check"
    if not supplier:
        supplier = "unknown"
    state["supplier"] = supplier
    ver = "b1-v-" + turn.view.stage_id
    return {
        "pack_text": "award " + supplier,
        "actions": (
            turn.actions.request_verification(ver, check, supplier),
            turn.actions.create_record(
                RECORD_STATUS + supplier,
                {"plan": supplier, "domain": "shipping"},
            ),
            turn.actions.create_record(RECORD_COMMIT, {"plan": supplier}),
            turn.actions.finalize(
                RECORD_COMMIT,
                {"plan": supplier, "status": "final"},
                (ver, RECORD_STATUS + supplier),
            ),
        ),
    }


def _re_award(turn, state):
    # Re-award after a rule change in session 2: request a NEW
    # verification id at the CURRENT revision before finalizing (the
    # old session-1 evidence is stale for this decision).
    choice = _ask(
        turn,
        "The corridor contract renews. Retained conclusions:\\n"
        + _carry(state)
        + "\\nConstraint analysis: " + state.get("constraint_reply", "")
        + "\\nRule analyses held: " + state.get("rule_reply", "")
        + "\\n\\nName the ONE supplier to re-award at the CURRENT "
        "protocol revision. Reply with exactly 'supplier=<id>' where "
        "<id> is the supplier's kebab-case id exactly as printed in "
        "the card headers (the id after 'Supplier card:'), and "
        "nothing else.",
    )
    supplier = _extract_value(choice, "supplier")
    check = _extract_value(state.get("constraint_reply", ""), "check")
    if not check:
        check = _extract_value(
            _ask(
                turn,
                "From your retained notes: " + _notes(state)
                + "\\n\\nName the verification check the re-award "
                "requires. Reply with exactly 'check=<name>'.",
            ),
            "check",
        )
    if not check:
        check = "undetermined-check"
    if not supplier:
        supplier = state.get("supplier", "unknown")
    ver = "b1-rev-" + turn.view.stage_id
    return {
        "pack_text": "re-award " + supplier,
        "actions": (
            turn.actions.request_verification(ver, check, supplier),
            turn.actions.create_record(RECORD_REAWARD, {"plan": supplier}),
            turn.actions.finalize(
                RECORD_REAWARD,
                {"plan": supplier, "status": "final"},
                (ver,),
            ),
        ),
    }


def _notes(state):
    return "\\n".join(state.get("notes", {}).values())[:4000]


def _carry(state):
    carry = state.get("carry", {})
    if not isinstance(carry, dict):
        return ""
    return "\\n".join(
        str(v) for v in carry.values() if v
    )[:4000]


def _extract_value(text, key):
    text = str(text)
    marker = key + "="
    if marker in text:
        tail = text[text.index(marker) + len(marker) :]
        value = tail.split()[0] if tail.split() else ""
        return value.strip(".,;'\\n")
    return ""
""".lstrip()


C_BASELINE = """
BATCH_DOCS = 6
CARRY_LIMIT = 6000

RECORD_COMMIT = "migration_commit"
RECORD_REAWARD = "corridor_reaward"
RECORD_STATUS = "candidate_status-"
RECORD_CONCLUSION = "followup_conclusion-"


def _ask(turn, prompt):
    reply = turn.ask_model(prompt)
    return reply.content if reply.ok else ""


def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    if kind == "survey":
        docs = turn.view.documents
        state.setdefault("notes", {})
        for start in range(0, len(docs), BATCH_DOCS):
            batch = docs[start : start + BATCH_DOCS]
            body = "\\n\\n".join(d.text for d in batch)
            reply = _ask(
                turn,
                "You are building working notes for a supplier-selection "
                "project. From the material below, extract ONLY: (a) any "
                "supplier whose EXCEPTION CLAUSE qualifies them for a "
                "verification check (quote the clause), (b) any supplier "
                "with a buried DISQUALIFYING condition (quote it), (c) any "
                "supplier described as covering specific checkpoints or "
                "hubs, (d) the names of any verification checks mentioned. "
                "Reply in <= 120 words of notes.\\n\\n" + body,
            )
            if reply:
                state["notes"]["batch-%d" % start] = reply
        return {"pack_text": "survey notes built"}
    if kind == "constraint_injection":
        constraint = "\\n".join(d.text for d in turn.view.documents)
        reply = _ask(
            turn,
            "Project constraint received: " + constraint
            + "\\n\\nFrom your retained notes: "
            + _notes(state)
            + "\\n\\nWhich verification check does this constraint require "
            "for the award, and which supplier(s) from the notes could "
            "satisfy it? Reply with one line: 'check=<name> "
            "candidate=<supplier>'.",
        )
        state["constraint_reply"] = reply
        return {"pack_text": "constraint analyzed"}
    if kind == "rule_change":
        rule = "\\n".join(d.text for d in turn.view.documents)
        reply = _ask(
            turn,
            "Notice received: " + rule
            + "\\n\\nFrom your retained notes: " + _notes(state)
            + "\\nRetained conclusions:\\n" + _carry(state)
            + "\\n\\nDoes this change invalidate any verification evidence "
            "you hold, or flip any prior verdict? Reply with one line: "
            "'invalidates=<check or none>'.",
        )
        state["rule_reply"] = reply
        return {"pack_text": "notice analyzed"}
    if kind == "session_start":
        carry = _carry(state)
        if not carry:
            return {"pack_text": "resume (empty carry)"}
        reply = _ask(
            turn,
            "Session resume. Retained conclusions from the previous "
            "session:\\n" + carry
            + "\\nRule analyses held: " + state.get("rule_reply", "")
            + "\\n\\nMight any retained conclusion be stale given the last "
            "known state? Reply with one line: "
            "'stale=<conclusion or none>'.",
        )
        state["carry_check"] = reply
        return {"pack_text": "resume checked"}
    if kind == "session_end":
        # Distill the probe OUTCOMES into the carry: which subject
        # passed, which failed, at which revision.
        seen = _seen_receipts(state)
        outcomes = "\\n".join(
            "record=%s subject=%s verdict=%s" % (rid, sub, ver)
            for rid, sub, ver in seen
        )
        reply = _ask(
            turn,
            "Session end. Working state is about to be destroyed; only "
            "state['carry'] persists (byte-capped). Retained notes:\\n"
            + _notes(state)
            + "\\nProbe outcomes so far:\\n" + (outcomes or "(none)")
            + "\\n\\nWhat must survive to the next session? Distill the "
            "load-bearing conclusions (probed subjects and their "
            "verdicts, award, scope) in <= 150 words.",
        )
        carry = state.get("carry", {})
        if not isinstance(carry, dict):
            carry = {}
        carry["distilled"] = (reply or "")[:CARRY_LIMIT]
        if state.get("supplier"):
            carry["award"] = state["supplier"]
        if state.get("constraint_reply"):
            carry["check_reply"] = state["constraint_reply"][:2000]
        if state.get("rule_reply"):
            carry["rule_reply"] = state["rule_reply"][:2000]
        if seen:
            carry["outcomes"] = _receipt_lines(seen)
        notes = _notes(state)
        if notes:
            carry["notes"] = notes[:CARRY_LIMIT]
        state["carry"] = carry
        return {"pack_text": "carry distilled"}
    if kind == "act_verify":
        stage_id = turn.view.stage_id
        re_award = "re-award" in stage_id or "reaward" in stage_id
        if re_award:
            return _re_award(turn, state)
        return _probe_commit(turn, state)
    return {"pack_text": "ok"}


def _probe_commit(turn, state):
    # The receipt-reading loop: accumulate EVERY turn (receipts drain
    # per turn; a one-turn memory loses earlier verdicts).
    seen = _accumulate(state, turn.receipts)
    check = _extract_value(state.get("constraint_reply", ""), "check")
    if not check:
        check = _extract_value(
            _ask(
                turn,
                "From your retained notes: " + _notes(state)
                + "\\n\\nName the verification check the award "
                "requires. Reply with exactly 'check=<name>'.",
            ),
            "check",
        )
    if not check:
        check = "undetermined-check"
    # Ask the worker for the candidate to probe NOW (the worker sees
    # the fail receipts and prior probes in the prompt).
    receipt_lines = _receipt_lines(seen)
    choice = _ask(
        turn,
        "Retained notes: " + _notes(state)
        + "\\nConstraint analysis: " + state.get("constraint_reply", "")
        + "\\nVerification outcomes seen so far:\\n"
        + (receipt_lines or "(none yet)")
        + "\\n\\nName the ONE supplier to verify now (a candidate whose "
        "verification has not failed). Reply with exactly 'supplier=<id>' "
        "where <id> is the supplier's kebab-case id exactly as printed "
        "in the card headers (the id after 'Supplier card:'), and "
        "nothing else.",
    )
    supplier = _extract_value(choice, "supplier")
    if not supplier:
        supplier = "unknown"
    # Verdict-gated: has a PASS already been seen for this supplier?
    passed = [sub for rid, sub, ver in seen if ver == "pass" and sub == supplier]
    if passed:
        return _commit(turn, state, supplier, check, seen)
    # No seen pass for the chosen candidate: probe it and END the turn
    # (the verdict arrives as a receipt next turn; max_turns is the
    # caller's contract).
    ver = "c1-v-" + turn.view.stage_id + "-" + str(len(seen))
    state["probing"] = supplier
    return {
        "pack_text": "probe " + supplier,
        "actions": (
            turn.actions.request_verification(ver, check, supplier),
        ),
    }


def _commit(turn, state, supplier, check, seen):
    # Commit gated on a SEEN pass for the committed subject.
    pass_ids = [
        rid for rid, sub, ver in seen if ver == "pass" and sub == supplier
    ]
    if not pass_ids:
        return {"pack_text": "no passing evidence for " + supplier}
    ver_id = pass_ids[0]
    state["supplier"] = supplier
    return {
        "pack_text": "commit " + supplier,
        "actions": (
            turn.actions.create_record(
                RECORD_STATUS + supplier,
                {"plan": supplier, "domain": "shipping"},
            ),
            turn.actions.create_record(RECORD_COMMIT, {"plan": supplier}),
            turn.actions.finalize(
                RECORD_COMMIT,
                {"plan": supplier, "status": "final"},
                (ver_id, RECORD_STATUS + supplier),
            ),
        ),
    }


def _re_award(turn, state):
    # Session 2: re-verify the post-mutation winner BEFORE committing
    # (a carried pass from session 1 may be stale after the mutation).
    seen = _accumulate(state, turn.receipts)
    receipt_lines = _receipt_lines(seen)
    # The stage's own documents (a renewal notice, when the world
    # attaches one) are decision material: the re-award can be GOVERNED
    # by the notice's rule, so the worker reads it here, not only the
    # distilled one-line analysis.
    stage_docs = "\\n\\n".join(d.text for d in turn.view.documents)
    choice = _ask(
        turn,
        "The corridor contract renews after a state change. Retained "
        "conclusions:\\n" + _carry(state)
        + "\\nRule analyses held: " + state.get("rule_reply", "")
        + "\\nVerification outcomes seen so far:\\n"
        + (receipt_lines or "(none yet)")
        + ("\\nRenewal material attached:\\n" + stage_docs if stage_docs else "")
        + "\\n\\nName the ONE supplier to verify now at the CURRENT "
        "revision (prior verdicts may be superseded). Reply with exactly "
        "'supplier=<id>' where <id> is the supplier's kebab-case id "
        "exactly as printed in the card headers (the id after 'Supplier "
        "card:'), and nothing else.",
    )
    supplier = _extract_value(choice, "supplier")
    check = _extract_value(state.get("constraint_reply", ""), "check")
    if not check:
        check = _extract_value(
            _ask(
                turn,
                "From your retained notes: " + _notes(state)
                + "\\nRetained conclusions:\\n" + _carry(state)
                + "\\n\\nName the verification check the re-award "
                "requires. Reply with exactly 'check=<name>'.",
            ),
            "check",
        )
    if not check:
        check = "undetermined-check"
    if not supplier:
        supplier = state.get("supplier", "unknown")
    passed = [sub for rid, sub, ver in seen if ver == "pass" and sub == supplier]
    if passed:
        pass_ids = [
            rid for rid, sub, ver in seen if ver == "pass" and sub == supplier
        ]
        return {
            "pack_text": "re-award " + supplier,
            "actions": (
                turn.actions.create_record(
                    RECORD_REAWARD, {"plan": supplier}
                ),
                turn.actions.finalize(
                    RECORD_REAWARD,
                    {"plan": supplier, "status": "final"},
                    (pass_ids[0],),
                ),
            ),
        }
    ver = "c1-rev-" + turn.view.stage_id + "-" + str(len(seen))
    return {
        "pack_text": "probe " + supplier,
        "actions": (
            turn.actions.request_verification(ver, check, supplier),
        ),
    }


def _accumulate(state, receipts):
    # Receipts drain per turn: the POLICY remembers them.
    seen = state.setdefault("seen_receipts", [])
    for r in receipts:
        entry = (r.record_id, r.subject, r.verdict)
        if entry not in seen:
            seen.append(entry)
    return seen


def _seen_receipts(state):
    seen = state.get("seen_receipts", [])
    if not isinstance(seen, list):
        return []
    out = []
    for entry in seen:
        try:
            rid, sub, ver = entry
        except (TypeError, ValueError):
            continue
        out.append((str(rid), str(sub), str(ver)))
    return out


def _receipt_lines(seen):
    return "\\n".join(
        "record=%s subject=%s verdict=%s" % (rid, sub, ver)
        for rid, sub, ver in seen
    )


def _notes(state):
    return "\\n".join(state.get("notes", {}).values())[:4000]


def _carry(state):
    carry = state.get("carry", {})
    if not isinstance(carry, dict):
        return ""
    return "\\n".join(
        str(v) for v in carry.values() if v
    )[:4000]


def _extract_value(text, key):
    text = str(text)
    marker = key + "="
    if marker in text:
        tail = text[text.index(marker) + len(marker) :]
        value = tail.split()[0] if tail.split() else ""
        return value.strip(".,;'\\n")
    return ""
""".lstrip()


def group_b_basline_policy_text() -> str:
    """The B-group baseline: carry-aware strong-fixed (carried by snapshots)."""

    return B_BASELINE


def group_c_baseline_policy_text() -> str:
    """The C-group baseline: receipt-reading strong-fixed (carried by snapshots)."""

    return C_BASELINE


__all__ = [
    "B_BASELINE",
    "C_BASELINE",
    "group_b_basline_policy_text",
    "group_c_baseline_policy_text",
]
