"""The STRONG MODEL-FIXED baseline (R2a arm 1, stats-contract §1).

The honest control the reviews demanded: the SAME worker model the
update arm uses, driven through ``turn.ask_model`` — the policy code
below ONLY ORCHESTRATES (batching, record construction, citation
assembly); every CONTENT decision (which supplier, what to conclude,
what the diagnosis is) is the worker's answer, parsed from its reply.
No answer strings are hardcoded: swap the world's facts and the
baseline's outputs follow the model's reading of the material.

The three long-axis behaviors a competent-but-static system shows:
- LONG MEMORY: at survey it asks the worker to COMPRESS the corpus into
  working conclusions (it does not keep raw text); at follow-ups it
  feeds the retained conclusions back — what was kept is the model's
  choice, not the harness's.
- LONG CONTEXT: the corpus is larger than one comfortable prompt, so
  the policy BATCHES the survey (the batching policy is the fixed
  part; reading each batch is the model's).
- LONG HORIZON: at the award it asks the model to CHOOSE from the
  retained conclusions; at follow-up 2 it asks the model to diagnose
  currency from the receipts and retained scope notes.
"""

from __future__ import annotations

STRONG_MODEL_FIXED_POLICY = """
BATCH_DOCS = 6
KEEP_KEYS = ("award", "calibration", "scopes")


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
    if kind == "act_verify":
        choice = _ask(
            turn,
            "Retained notes: " + _notes(state)
            + "\\nConstraint analysis: " + state.get("constraint_reply", "")
            + "\\n\\nName the ONE supplier to award (the one whose "
            "qualification satisfies the required check). Reply with "
            "exactly 'supplier=<name>' and nothing else.",
        )
        supplier = _extract_value(choice, "supplier")
        check = _extract_value(state.get("constraint_reply", ""), "check")
        if not check:
            # The check name comes from the MODEL's constraint analysis;
            # no world-specific name is hardwired. Unparseable -> ask the
            # notes once directly.
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
        return {
            "pack_text": "award " + supplier,
            "actions": (
                turn.actions.request_verification(
                    "sf-v1", check, supplier
                ),
                turn.actions.create_record(
                    "candidate_status-" + supplier,
                    {"plan": supplier, "domain": "shipping"},
                ),
                turn.actions.create_record(
                    "migration_commit", {"plan": supplier}
                ),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": supplier, "status": "final"},
                    ("sf-v1", "candidate_status-" + supplier),
                ),
            ),
        }
    if kind == "follow_up":
        doc = turn.view.documents[0].text if turn.view.documents else ""
        if "calibration" in doc:
            reply = _ask(
                turn,
                "A lab calibration partner is needed for the awarded "
                "corridor. Retained notes: " + _notes(state)
                + "\\n\\nWhich instrument supplier covers the same "
                "checkpoints? Reply with exactly 'supplier=<name>'.",
            )
            supplier = _extract_value(reply, "supplier")
            return {
                "pack_text": "calibration " + str(supplier),
                "actions": (
                    turn.actions.create_record(
                        "followup_conclusion-calibration",
                        {"supplier": supplier},
                    ),
                ),
            }
        reply = _ask(
            turn,
            "The corridor contract is up for review. Retained notes: "
            + _notes(state)
            + "\\nRule analyses held: "
            + state.get("rule_reply", "")
            + "\\n\\nWas the award's verification evidence acquired "
            "before or after the latest rule change that affects its "
            "check? Is that evidence still current? Reply with exactly "
            "'status=<current or reverify>'.",
        )
        status = _extract_value(reply, "status")
        if status not in ("current", "reverify"):
            # Unparseable answer: ask once more, then report an
            # explicit undetermined diagnosis (a named failure, never a
            # silently biased default).
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
                    "followup_conclusion-corridor", {"status": status}
                ),
            ),
        }
    return {"pack_text": "ok"}


def _notes(state):
    return "\\n".join(state.get("notes", {}).values())[:4000]


def _extract_value(text, key):
    text = str(text)
    marker = key + "="
    if marker in text:
        tail = text[text.index(marker) + len(marker) :]
        value = tail.split()[0] if tail.split() else ""
        return value.strip(".,;'\\n")
    return ""
""".lstrip()


def strong_model_fixed_policy_text() -> str:
    """The model-driven strong-fixed baseline (carried by snapshots)."""

    return STRONG_MODEL_FIXED_POLICY
