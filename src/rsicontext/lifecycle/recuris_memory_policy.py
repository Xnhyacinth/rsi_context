"""The memory-aware frozen worker policy (Recuris-adapted arm's A0).

Design (recuris agent, 2026-09-23): the machine is BYTE-FROZEN — this
policy never changes after round 0; the MEMORY (state['recuris_memory'],
a MemoryPackage mapping injected by the arm loop) is the only thing the
improver edits. The delivery rule here executes Recuris's rho: which
cards enter which stage's ask_model prompts. The card text PHYSICALLY
enters the metered prompt (audit transcript proves it), so a memory edit
changes the worker's input — the memory→behavior path is real, offline
and live.

What this policy adds over strong_model_fixed:
- the delivery renderer (reads the package's invocation rule + cards;
  prepends a '## Prior-failure memory' section to matching prompts);
- delivery logging (state['memory_delivered'][stage] = [card ids]) —
  the trace's E_t and the gate's fingerprint evidence;
- an observation log (state['obs'] = receipts seen) — the trace's o_t;
- it NEVER writes the 'recuris_memory' key (memory is the improver's).
"""

from __future__ import annotations

RECURIS_MEMORY_POLICY = """
BATCH_DOCS = 6
MEMORY_KEY = "recuris_memory"
DELIVERED_KEY = "memory_delivered"
OBS_KEY = "obs"


def _ask(turn, prompt):
    reply = turn.ask_model(prompt)
    return reply.content if reply.ok else ""


def _memory(turn):
    pkg = turn.state.get(MEMORY_KEY)
    return pkg if isinstance(pkg, dict) else None


def _deliver(turn, kind):
    \"\"\"The rho rule, executed: which card bodies enter this stage.\"\"\"
    pkg = _memory(turn)
    if not pkg:
        return ""
    rho = pkg.get("invocation") or {}
    stages = rho.get("invoked_on_stages") or []
    cap = rho.get("max_cards_per_stage") or 0
    if kind not in stages or cap < 1:
        return []
    entries = pkg.get("entries") or []
    matching = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stage = entry.get("stage")
        field = entry.get("requires_field")
        if stage not in (kind, "*"):
            continue
        if field is not None and field not in turn.state:
            continue
        matching.append(entry)
    matching.sort(key=lambda e: str(e.get("id", "")))
    return matching[:cap]


def _render(cards):
    if not cards:
        return ""
    lines = ["## Prior-failure memory (delivered)"]
    for card in cards:
        lines.append("- [" + str(card.get("id", "?")) + "] " + str(card.get("body", "")))
    return "\\n".join(lines) + "\\n\\n"


def _log(turn, key, value):
    log = turn.state.get(key)
    if not isinstance(log, list):
        log = []
        turn.state[key] = log
    log.append(value)


def on_turn(turn):
    kind = turn.view.kind
    state = turn.state
    # Observation log (the trace's o_t): receipts the policy actually saw.
    if turn.receipts:
        for receipt in turn.receipts:
            _log(turn, OBS_KEY, [receipt.action_kind, receipt.record_id,
                                 receipt.applied, receipt.verdict, receipt.cause[:60]])
    if kind == "survey":
        docs = turn.view.documents
        state.setdefault("notes", {})
        cards = _deliver(turn, kind)
        _log(turn, DELIVERED_KEY, [kind] + [str(c.get("id")) for c in cards])
        for start in range(0, len(docs), BATCH_DOCS):
            batch = docs[start : start + BATCH_DOCS]
            body = "\\n\\n".join(d.text for d in batch)
            reply = _ask(
                turn,
                _render(cards)
                + "You are building working notes for a supplier-selection "
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
        cards = _deliver(turn, kind)
        _log(turn, DELIVERED_KEY, [kind] + [str(c.get("id")) for c in cards])
        reply = _ask(
            turn,
            _render(cards)
            + "Project constraint received: " + constraint
            + "\\n\\nFrom your retained notes: " + _notes(state)
            + "\\n\\nWhich verification check does this constraint require "
            "for the award, and which supplier(s) from the notes could "
            "satisfy it? Reply with one line: 'check=<name> "
            "candidate=<supplier>'.",
        )
        state["constraint_reply"] = reply
        return {"pack_text": "constraint analyzed"}
    if kind == "rule_change":
        rule = "\\n".join(d.text for d in turn.view.documents)
        cards = _deliver(turn, kind)
        _log(turn, DELIVERED_KEY, [kind] + [str(c.get("id")) for c in cards])
        reply = _ask(
            turn,
            _render(cards)
            + "Rule change received: " + rule
            + "\\n\\nFrom your retained notes: " + _notes(state)
            + "\\n\\nDoes this change invalidate any verification evidence "
            "you hold? Reply with one line: 'invalidates=<check or none>'.",
        )
        state["rule_reply"] = reply
        return {"pack_text": "rule change analyzed"}
    if kind == "act_verify":
        cards = _deliver(turn, kind)
        _log(turn, DELIVERED_KEY, [kind] + [str(c.get("id")) for c in cards])
        choice = _ask(
            turn,
            _render(cards)
            + "Retained notes: " + _notes(state)
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
        return {
            "pack_text": "award " + supplier,
            "actions": (
                turn.actions.request_verification("sf-v1", check, supplier),
                turn.actions.create_record(
                    "candidate_status-" + supplier, {"plan": supplier, "domain": "shipping"}
                ),
                turn.actions.create_record("migration_commit", {"plan": supplier}),
                turn.actions.finalize(
                    "migration_commit",
                    {"plan": supplier, "status": "final"},
                    ("sf-v1", "candidate_status-" + supplier),
                ),
            ),
        }
    if kind == "follow_up":
        doc = turn.view.documents[0].text if turn.view.documents else ""
        cards = _deliver(turn, kind)
        _log(turn, DELIVERED_KEY, [kind] + [str(c.get("id")) for c in cards])
        if "calibration" in doc:
            reply = _ask(
                turn,
                _render(cards)
                + "A lab calibration partner is needed for the awarded "
                "corridor. Retained notes: " + _notes(state)
                + "\\n\\nWhich instrument supplier covers the same "
                "checkpoints? Reply with exactly 'supplier=<id>' where "
                "<id> is the supplier's kebab-case id exactly as printed "
                "in the card headers (the id after 'Supplier card:'), and "
                "nothing else.",
            )
            supplier = _extract_value(reply, "supplier")
            return {
                "pack_text": "calibration " + str(supplier),
                "actions": (
                    turn.actions.create_record(
                        "followup_conclusion-calibration", {"supplier": supplier}
                    ),
                ),
            }
        reply = _ask(
            turn,
            _render(cards)
            + "The corridor contract is up for review. Retained notes: "
            + _notes(state)
            + "\\nRule analyses held: " + state.get("rule_reply", "")
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
""".lstrip()  # noqa: E501


def recuris_memory_policy_text() -> str:
    """The byte-frozen memory-aware worker policy (the arm's A0)."""

    return RECURIS_MEMORY_POLICY


__all__ = ["recuris_memory_policy_text"]
