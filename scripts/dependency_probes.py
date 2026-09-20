#!/usr/bin/env python3
"""Dependency and counterfactual probes for the research-v1 task family.

Implements the remaining step-3 diagnostic probes from the external review
(2026-09-20), per docs/root-cause-24-of-24-20260920.md §Consequences and
docs/task-family-research-v1.md §Qualification gates 4-5: on alias-scored
items, verify the family's REAL dependency structure — does the final
answer actually depend on the long evidence, on cross-stage memory, and on
the answer-relevant facts? These are development diagnostics, NOT benchmark
arms; they never enter scoring.

Probes (one JSON artifact per run: per-item detail + summary rates):
  longdoc-necessity       full gold evidence vs question-only (no evidence).
                          If the no-evidence condition scores near the
                          evidence condition, the long documents are not
                          load-bearing (family failure). Reader probe.
  no-history              run_lifecycle with a stateful scripted hook vs
                          the same hook with state forced EMPTY at each
                          stage. If empty ≈ stateful, cross-stage memory is
                          not necessary — the review's "last-stage input
                          already repeats everything" check. No reader key:
                          extraction is an oracle (alias-presence in the
                          stage documents), so the probe measures
                          information availability, not reader ability.
  fact-swap               replace the answer phrase inside the gold passage
                          with a fixed alternate value; the reader's answer
                          must follow the edited fact (flip rate). Low flip
                          rate = answers do not depend on evidence.
  irrelevant-perturbation append an alias-free distractor sentence to the
                          gold passage; the answer must stay correct
                          (stability rate).
  evidence-missing       the gold-drop counterfactual (qualification gate 4):
                          question with NO evidence and NO permission to
                          answer from memory — the system prompt's
                          INSUFFICIENT rule is the only compliant output.
                          Metric: appropriate-refusal rate vs stale/
                          parametric answers. This is longdoc-necessity's
                          condition (b) minus the knowledge-permission
                          sentence: a different readout (does the reader
                          TREAT the documents as necessary?) rather than
                          load-bearingness given parametric knowledge.

Loader discipline follows scripts/channel_parity_diagnostic.py (dedup by id
— PopQA packs multiple relations under one entity id — plus clean-gold-ctx
filtering) with one addition shared by all four probes: at least one clean
NON-gold ctx (build_example_instance requires it and the perturbation probe
draws its distractor there), so every probe runs over the same item set.
Answer matching is alias-aware over the row's FULL possible_answers list,
implemented locally over the raw rows (the material constructor still pins
possible_answers[0]; the alias-scoring workstream owns the lifecycle side).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rsicontext.lifecycle import (
    Action,
    DocumentRef,
    LifecycleRunRecord,
    ProjectState,
    StageResponse,
    StageView,
    build_example_instance,
    run_lifecycle,
)

POPQA_ROWS = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
READER_SYSTEM = (
    "You extract exact answers from supplied evidence. Output ONLY the "
    "answer phrase with no punctuation, no reasoning, no explanation. "
    "If the evidence is insufficient, output INSUFFICIENT."
)
RECORD_ID = "answer_project"

# Verdict thresholds (the rates themselves are the deliverable; the booleans
# follow the channel-parity diagnostic's 0.25 contrast margin where a
# difference between conditions is the signal).
_NECESSITY_MARGIN = 0.25
_FLIP_FLOOR = 0.5
_STABILITY_FLOOR = 0.75
_REFUSAL_FLOOR = 0.75

_PROBES = (
    "longdoc-necessity",
    "no-history",
    "fact-swap",
    "irrelevant-perturbation",
    "evidence-missing",
)

# Fixed alternate values for the fact-swap probe: real phrase-shaped values
# chosen to collide with PopQA aliases and gold passages rarely; the editor
# skips any alternate that collides with the row's aliases or text.
_ALTERNATES: tuple[str, ...] = (
    "Luxembourg",
    "blacksmith",
    "chamber music",
    "volcanology",
    "Liechtenstein",
    "lacrosse",
    "cartography",
    "mandolin",
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


# --- shared matching -----------------------------------------------------------


def _contains(needle: str, haystack: str) -> bool:
    """Case-insensitive whole-phrase containment (word-boundary safe).

    Lookarounds instead of ``\\b`` so aliases ending in punctuation (for
    example PopQA's ``polit.``) still match at sentence ends; and so short
    aliases (``POL``) do not match inside longer words (``polarity``).
    """

    if not needle or not haystack:
        return False
    pattern = rf"(?<!\w){re.escape(needle)}(?!\w)"
    return re.search(pattern, haystack, flags=re.IGNORECASE) is not None


def _normalize_reply(raw: str) -> str:
    """Reduce a reader reply to the answer phrase candidate.

    Compact port of scripts/pilot_cell.py's _normalize_answer (proven
    against the reasoning reader's reply shapes): first non-empty line,
    quoted phrase, emphasis and narration wrappers, trailing punctuation.
    """

    text = raw.strip()
    if not text:
        return ""
    line = next((entry.strip() for entry in text.split("\n") if entry.strip()), "")
    for quote in ('"', "'", "`"):
        if line.startswith(quote):
            end = line.find(quote, 1)
            if end > 1:
                return line[1:end].strip().strip(".").strip()
    if line.startswith("**") and line.endswith("**") and len(line) > 4:
        line = line[2:-2].strip()
    lowered = line.lower()
    for prefix in ("answer:", "the answer is ", "answer is "):
        if lowered.startswith(prefix):
            line = line[len(prefix) :].strip()
            break
    return line.strip().strip(".").strip()


def alias_hit(reply: str, aliases: Sequence[str]) -> bool:
    """Alias-aware answer match over the FULL possible_answers list.

    Bidirectional whole-phrase containment between the normalized reply and
    any alias; empty replies and INSUFFICIENT verdicts are misses.
    """

    text = _normalize_reply(reply)
    if not text or text.lower() == "insufficient":
        return False
    return any(
        _contains(alias, text) or _contains(text, alias) for alias in aliases if alias.strip()
    )


def decode_aliases(raw: object) -> tuple[str, ...]:
    """Decode a row's possible_answers (JSON list string or list)."""

    decoded: object = raw
    if isinstance(raw, str):
        decoded = json.loads(raw)
    if not isinstance(decoded, list):
        return ()
    return tuple(entry.strip() for entry in decoded if isinstance(entry, str) and entry.strip())


# --- loader --------------------------------------------------------------------


def _clean_ctxs(ctxs: Sequence[object]) -> list[Mapping[str, object]]:
    return [
        ctx
        for ctx in ctxs
        if isinstance(ctx, Mapping)
        and str(ctx.get("text") or "").strip()
        and str(ctx.get("title") or "").strip()
    ]


def _is_gold(ctx: Mapping[str, object]) -> bool:
    return ctx.get("has_answer") is True or ctx.get("has_answer") == 1


def _usable_row(row: Mapping[str, object]) -> bool:
    """Channel-parity discipline plus one clean non-gold ctx (see module doc)."""

    if not str(row.get("question") or "").strip():
        return False
    if not decode_aliases(row.get("possible_answers")):
        return False
    ctxs = row.get("ctxs")
    if not isinstance(ctxs, list):
        return False
    clean = _clean_ctxs(ctxs)
    gold = [ctx for ctx in clean if _is_gold(ctx)]
    return bool(gold) and len(clean) > len(gold)


def load_rows(path: Path, n: int) -> list[dict[str, Any]]:
    """First ``n`` usable rows: dedup by id, clean gold + non-gold ctxs."""

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = str(row["id"])
            if key in seen:
                continue
            seen.add(key)
            if not _usable_row(row):
                continue
            rows.append(row)
            if len(rows) >= n:
                break
    return rows


@dataclass(frozen=True)
class ProbeItem:
    """The participant-side material one reader probe needs per row."""

    id: str
    question: str
    aliases: tuple[str, ...]
    gold_text: str
    gold_title: str
    distractor: str | None


def pick_distractor(ctxs: Sequence[object], aliases: Sequence[str]) -> str | None:
    """First alias-free sentence (>= 5 words) from a non-gold ctx, if any."""

    for ctx in ctxs:
        if not isinstance(ctx, Mapping) or _is_gold(ctx):
            continue
        text = str(ctx.get("text") or "").strip()
        if not text:
            continue
        for sentence in _SENTENCE_SPLIT.split(text):
            candidate = sentence.strip()
            if len(candidate.split()) < 5:
                continue
            if any(_contains(alias, candidate) for alias in aliases if alias.strip()):
                continue
            return candidate
    return None


def to_probe_item(row: Mapping[str, object]) -> ProbeItem:
    ctxs = row.get("ctxs")
    assert isinstance(ctxs, list)
    gold = next(ctx for ctx in _clean_ctxs(ctxs) if _is_gold(ctx))
    aliases = decode_aliases(row.get("possible_answers"))
    return ProbeItem(
        id=str(row.get("id")),
        question=str(row.get("question") or ""),
        aliases=aliases,
        gold_text=str(gold.get("text") or "").strip(),
        gold_title=str(gold.get("title") or ""),
        distractor=pick_distractor(ctxs, aliases),
    )


# --- editors (fact-swap, irrelevant perturbation) ------------------------------


def fact_swap(
    gold_text: str,
    aliases: Sequence[str],
    alternates: Sequence[str] = _ALTERNATES,
) -> tuple[str, str, str] | None:
    """Minimally edit ``gold_text`` so the answer-relevant fact changes.

    Replaces every whole-phrase occurrence of each alias (longest first)
    with one fixed alternate value. Returns ``(edited_text, replaced_alias,
    alternate)`` or None when no alias occurs in the text, or no collision-
    free alternate exists, or an original alias would survive the swap.
    """

    lowered = {alias.lower() for alias in aliases if alias.strip()}
    alternate: str | None = None
    for candidate in alternates:
        if candidate.lower() in lowered:
            continue
        if _contains(candidate, gold_text):
            continue
        if any(
            _contains(alias, candidate) or _contains(candidate, alias)
            for alias in aliases
            if alias.strip()
        ):
            continue
        alternate = candidate
        break
    if alternate is None:
        return None
    edited = gold_text
    replaced: str | None = None
    for alias in sorted((a for a in aliases if a.strip()), key=len, reverse=True):
        pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
        if re.search(pattern, edited, flags=re.IGNORECASE):
            edited = re.sub(pattern, alternate, edited, flags=re.IGNORECASE)
            replaced = replaced or alias
    if replaced is None:
        return None
    if any(_contains(alias, edited) for alias in aliases if alias.strip()):
        return None
    if not _contains(alternate, edited):
        return None
    return edited, replaced, alternate


def append_distractor(gold_text: str, distractor: str) -> str:
    """The irrelevant-perturbation editor: append one sentence, change nothing else."""

    return f"{gold_text}\n\n{distractor}"


# --- reader --------------------------------------------------------------------


def siflow_reader(prompt: str) -> str:
    """One Qwen T2 reader call (the pilot cell's call shape, system held fixed)."""

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
    with urllib.request.urlopen(request, timeout=300) as response:
        raw = json.loads(response.read())
    message = raw["choices"][0]["message"]
    return (message.get("content") or "").strip() or (
        message.get("reasoning_content") or ""
    ).strip()


def _evidence_prompt(question: str, evidence: str) -> str:
    return f"Question:\n{question}\n\nEvidence:\n{evidence}"


def _rate(hits: int, n: int) -> float:
    return round(hits / n, 3) if n else 0.0


# --- probe 1: longdoc-necessity ------------------------------------------------


def run_longdoc_necessity(
    items: Sequence[ProbeItem], reader: Callable[[str], str]
) -> dict[str, Any]:
    """Full gold evidence vs question-only: are the long documents load-bearing?

    The system prompt is held fixed across conditions (channel parity); only
    the evidence block differs. The no-evidence instruction explicitly
    permits answering from the reader's own knowledge — a compliant reader
    may still refuse (INSUFFICIENT counts as a miss), which is itself the
    signal that the reader treats the documents as necessary.
    """

    per_item: list[dict[str, Any]] = []
    hits = {"gold_evidence": 0, "short_rule_only": 0}
    for item in items:
        conditions: dict[str, dict[str, Any]] = {}
        for condition, prompt in (
            (
                "gold_evidence",
                _evidence_prompt(item.question, item.gold_text),
            ),
            (
                "short_rule_only",
                (
                    f"Question:\n{item.question}\n\n"
                    "No evidence is supplied. Answer from your own knowledge "
                    "with the exact answer phrase only."
                ),
            ),
        ):
            reply = reader(prompt)
            hit = alias_hit(reply, item.aliases)
            hits[condition] += hit
            conditions[condition] = {"reply": reply[:120], "hit": hit}
        per_item.append({"id": item.id, "expected_aliases": list(item.aliases), **conditions})
    n = len(items)
    summary = {
        condition: {"hits": count, "n": n, "rate": _rate(count, n)}
        for condition, count in hits.items()
    }
    verdict = {
        "longdoc_necessary": (summary["gold_evidence"]["rate"] - summary["short_rule_only"]["rate"])
        >= _NECESSITY_MARGIN,
        "rates": {condition: entry["rate"] for condition, entry in summary.items()},
    }
    return {
        "probe": "longdoc-necessity",
        "n": n,
        "per_item": per_item,
        "summary": summary,
        "verdict": verdict,
    }


# --- probe 2: no-history -------------------------------------------------------


def _oracle_extract(documents: tuple[DocumentRef, ...], aliases: Sequence[str]) -> str:
    """Perfect-reader simulation: the first alias present in the documents."""

    ordered = sorted((alias for alias in aliases if alias.strip()), key=len, reverse=True)
    for document in documents:
        for alias in ordered:
            if _contains(alias, document.text):
                return alias
    return ""


class _OracleStatefulHook:
    """Scripted participant for the no-history probe.

    Oracle extraction over each stage's documents (it never parses answers
    out of the stage prompt text). Its notes state evolves across stages;
    the final answer is the most recent note carrying an answer — carried
    memory or the final stage's own evidence, whichever came last. With
    ``force_empty`` the state is cleared at every stage entry, so the final
    answer can only come from the final stage's own input. The contrast
    between the two conditions therefore measures whether the final stage's
    input alone already carries everything needed.
    """

    def __init__(
        self, state: dict[str, object], aliases: Sequence[str], *, force_empty: bool
    ) -> None:
        self._state = state
        self._aliases = tuple(
            sorted((alias for alias in aliases if alias.strip()), key=len, reverse=True)
        )
        self._force_empty = force_empty

    def on_stage(self, stage: StageView) -> StageResponse:
        if self._force_empty:
            self._state.clear()
        notes_raw = self._state.get("notes")
        notes: list[object] = list(notes_raw) if isinstance(notes_raw, list) else []
        found = _oracle_extract(stage.documents, self._aliases)
        if found:
            notes.append({"stage": stage.stage_id, "answer": found})
        self._state["notes"] = notes[-32:]
        anchor = stage.documents[0].doc_id if stage.documents else "no-doc"
        if stage.kind != "act_verify":
            return StageResponse(pack_text=f"working notes [[doc:{anchor}]]")
        answer = ""
        for note in reversed(notes):
            if isinstance(note, dict) and isinstance(note.get("answer"), str) and note["answer"]:
                answer = note["answer"]
                break
        doc_ids = tuple(document.doc_id for document in stage.documents)
        return StageResponse(
            pack_text=f"final commit [[doc:{anchor}]] {answer}",
            actions=(
                Action(
                    kind="create_record",
                    record_id=RECORD_ID,
                    fields={
                        "answer": answer,
                        "supports": list(doc_ids),
                        "status": "draft",
                    },
                    provenance=doc_ids,
                ),
                Action(
                    kind="finalize",
                    record_id=RECORD_ID,
                    fields={"answer": answer, "status": "final"},
                    provenance=doc_ids,
                ),
            ),
        )


def _committed_answer(record: LifecycleRunRecord) -> str:
    entry = record.sandbox_final_state.get(RECORD_ID)
    if not isinstance(entry, dict):
        return ""
    answer = entry.get("answer")
    return answer if isinstance(answer, str) else ""


def run_no_history(rows: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    """Stateful lifecycle vs state-forced-empty: is cross-stage memory necessary?

    Runs ``run_lifecycle`` (real runner, real sandbox actions) twice per
    instance: once with the stateful scripted hook, once with the same hook
    forced empty at each stage. Scoring is alias-aware on the committed
    answer (the instance's expected_state_delta still pins
    possible_answers[0], so the runner's final_check is not the metric
    here). Also records, per item, whether any alias occurs verbatim in the
    act_verify prompt text — the structural "the answer is handed to the
    participant at the last stage" fact.
    """

    per_item: list[dict[str, Any]] = []
    hits = {"stateful": 0, "empty_state": 0}
    for row in rows:
        aliases = decode_aliases(row.get("possible_answers"))
        instance = build_example_instance(row)
        stateful_record = run_lifecycle(
            instance,
            _OracleStatefulHook({}, aliases, force_empty=False),
            ProjectState(),
        )
        empty_record = run_lifecycle(
            instance,
            _OracleStatefulHook({}, aliases, force_empty=True),
            ProjectState(),
        )
        stateful_answer = _committed_answer(stateful_record)
        empty_answer = _committed_answer(empty_record)
        stateful_hit = alias_hit(stateful_answer, aliases)
        empty_hit = alias_hit(empty_answer, aliases)
        hits["stateful"] += stateful_hit
        hits["empty_state"] += empty_hit
        final_prompt = instance.stages[-1].prompt_text
        per_item.append(
            {
                "id": str(row.get("id")),
                "aliases": list(aliases),
                "stateful_answer": stateful_answer,
                "stateful_hit": stateful_hit,
                "empty_answer": empty_answer,
                "empty_hit": empty_hit,
                "answer_in_final_prompt": any(
                    _contains(alias, final_prompt) for alias in aliases if alias.strip()
                ),
            }
        )
    n = len(rows)
    summary = {
        condition: {"hits": count, "n": n, "rate": _rate(count, n)}
        for condition, count in hits.items()
    }
    verdict = {
        "memory_necessary": (summary["stateful"]["rate"] - summary["empty_state"]["rate"])
        >= _NECESSITY_MARGIN,
        "rates": {condition: entry["rate"] for condition, entry in summary.items()},
    }
    return {
        "probe": "no-history",
        "n": n,
        "per_item": per_item,
        "summary": summary,
        "verdict": verdict,
    }


# --- probe 3: fact-swap --------------------------------------------------------


def run_fact_swap(items: Sequence[ProbeItem], reader: Callable[[str], str]) -> dict[str, Any]:
    """Swap the answer-relevant fact; the answer must follow the edit."""

    per_item: list[dict[str, Any]] = []
    flips = 0
    evaluated = 0
    for item in items:
        swap = fact_swap(item.gold_text, item.aliases)
        if swap is None:
            per_item.append({"id": item.id, "skipped": "no swappable answer span"})
            continue
        edited, replaced, alternate = swap
        reply = reader(_evidence_prompt(item.question, edited))
        followed = alias_hit(reply, (alternate,))
        repeated_original = alias_hit(reply, item.aliases)
        flips += followed
        evaluated += 1
        per_item.append(
            {
                "id": item.id,
                "replaced": replaced,
                "alternate": alternate,
                "reply": reply[:120],
                "followed_swap": followed,
                "repeated_original": repeated_original,
            }
        )
    flip_rate = _rate(flips, evaluated)
    summary = {
        "flip_rate": flip_rate,
        "evaluated": evaluated,
        "skipped": len(items) - evaluated,
    }
    return {
        "probe": "fact-swap",
        "n": len(items),
        "per_item": per_item,
        "summary": summary,
        "verdict": {"evidence_dependent": flip_rate >= _FLIP_FLOOR, **summary},
    }


# --- probe 4: irrelevant-perturbation ------------------------------------------


def run_irrelevant_perturbation(
    items: Sequence[ProbeItem], reader: Callable[[str], str]
) -> dict[str, Any]:
    """Append an irrelevant sentence; the answer must stay correct."""

    per_item: list[dict[str, Any]] = []
    stable = 0
    evaluated = 0
    for item in items:
        if item.distractor is None:
            per_item.append({"id": item.id, "skipped": "no alias-free distractor"})
            continue
        evidence = append_distractor(item.gold_text, item.distractor)
        reply = reader(_evidence_prompt(item.question, evidence))
        hit = alias_hit(reply, item.aliases)
        stable += hit
        evaluated += 1
        per_item.append(
            {
                "id": item.id,
                "distractor": item.distractor[:120],
                "reply": reply[:120],
                "hit": hit,
            }
        )
    stability_rate = _rate(stable, evaluated)
    summary = {
        "stability_rate": stability_rate,
        "evaluated": evaluated,
        "skipped": len(items) - evaluated,
    }
    return {
        "probe": "irrelevant-perturbation",
        "n": len(items),
        "per_item": per_item,
        "summary": summary,
        "verdict": {"stable": stability_rate >= _STABILITY_FLOOR, **summary},
    }


# --- probe 5: evidence-missing --------------------------------------------------


def run_evidence_missing(
    items: Sequence[ProbeItem], reader: Callable[[str], str]
) -> dict[str, Any]:
    """The gold-drop counterfactual (qualification gate 4), strict readout.

    Same evidence-free condition as longdoc-necessity's (b), minus the
    knowledge-permission sentence: the reader is handed only the question
    and the system prompt's INSUFFICIENT rule. An appropriate refusal is a
    normalized INSUFFICIENT; anything else (including a correct parametric
    answer) is a failure of this gate — a reader that answers from memory
    when the evidence is gone treats the documents as unnecessary, so the
    family cannot rely on them. Reports the refusal rate, the parametric-
    answer rate (answers that would have scored a hit with evidence), and
    other-answer rate separately.
    """

    per_item: list[dict[str, Any]] = []
    refusals = 0
    parametric = 0
    evaluated = 0
    for item in items:
        prompt = f"Question:\n{item.question}\n\nNo evidence is supplied."
        reply = reader(prompt)
        normalized = _normalize_reply(reply)
        refused = normalized.lower() == "insufficient"
        parametric_hit = not refused and alias_hit(reply, item.aliases)
        refusals += refused
        parametric += parametric_hit
        evaluated += 1
        per_item.append(
            {
                "id": item.id,
                "reply": reply[:120],
                "refused": refused,
                "parametric_answer": parametric_hit,
            }
        )
    refusal_rate = _rate(refusals, evaluated)
    summary = {
        "refusal_rate": refusal_rate,
        "parametric_answer_rate": _rate(parametric, evaluated),
        "other_answer_rate": _rate(evaluated - refusals - parametric, evaluated),
        "evaluated": evaluated,
        "skipped": len(items) - evaluated,
    }
    return {
        "probe": "evidence-missing",
        "n": len(items),
        "per_item": per_item,
        "summary": summary,
        "verdict": {
            "reader_treats_evidence_as_necessary": refusal_rate >= _REFUSAL_FLOOR,
            **summary,
        },
    }


# --- artifact + CLI ------------------------------------------------------------


def write_artifact(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one JSON artifact (refuses to overwrite; parents created)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, indent=1, sort_keys=True)
        handle.write("\n")


def main_with_args(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--probe", choices=_PROBES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.probe != "no-history" and not os.environ.get("SIFLOW_API_KEY"):
        print(f"missing SIFLOW_API_KEY (required by --probe {args.probe})", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"output exists: {args.output}", file=sys.stderr)
        return 2
    rows = load_rows(POPQA_ROWS, args.n)
    if not rows:
        print("no usable rows", file=sys.stderr)
        return 2
    if len(rows) < args.n:
        print(f"warning: only {len(rows)} usable rows (asked {args.n})", file=sys.stderr)
    if args.probe == "no-history":
        payload: dict[str, Any] = run_no_history(rows)
    else:
        items = [to_probe_item(row) for row in rows]
        runners: dict[
            str, Callable[[Sequence[ProbeItem], Callable[[str], str]], dict[str, Any]]
        ] = {
            "longdoc-necessity": run_longdoc_necessity,
            "fact-swap": run_fact_swap,
            "irrelevant-perturbation": run_irrelevant_perturbation,
            "evidence-missing": run_evidence_missing,
        }
        payload = runners[args.probe](items, siflow_reader)
    payload = {"run_date": datetime.now(UTC).date().isoformat(), **payload}
    write_artifact(args.output, payload)
    print(json.dumps(payload["verdict"], indent=2, sort_keys=True))
    return 0


def main() -> int:
    return main_with_args(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
