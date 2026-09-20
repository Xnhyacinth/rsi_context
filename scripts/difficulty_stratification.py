#!/usr/bin/env python3
"""Pool widening + difficulty stratification + failure-mode quantification.

Tasks #28 + #29 from docs/arm-comparison-v2-first-20260920.md §Consequences.
The first arm comparison found the binding constraint is item difficulty
structure: items collapsed into all-solve (unambiguous gold) vs all-fail
(alias-normalization or ambiguous-entity span-selection). This script:

1. Widens the candidate pool (load ALL gold-sane-v2 entities, not the
   first N) and measures per world a GOLD-DOMINANCE signal: how strong is
   the answer-bearing passage's position among the survey documents
   (retrieval rank of the first gold doc, gold-token density vs noise)?
2. Stratifies worlds into difficulty tiers by a READER-PROBED hit signal
   on a small panel: probe each world's primary instance once with the
   standard extraction pipeline; worlds split into solved (memory won't
   help), failed-normalization (right span, alias miss — scoring/item
   fix), failed-span-selection (wrong passage — the mid-difficulty tier
   where better memory/notes CAN change outcomes).
3. Quantifies failure modes per item (span-selection vs normalization vs
   refusal) from the probe replies — task #29's deliverable.

Output: artifacts/qualification/difficulty-stratification-<date>.json with
per-world tier + per-item failure mode, and a stratified world manifest
(dev pool recommendation).

Reader probe cost: one stage-1-style call per world (question + survey
docs). No API key -> dry inventory only (tier measurement skipped).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from rsicontext.lifecycle.material_v2 import alias_hit_v2, gold_sane_v2

POPQA_ROWS = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
READER_SYSTEM = (
    "You extract exact answers from supplied evidence. Output ONLY the "
    "answer phrase with no punctuation, no reasoning, no explanation. "
    "If the evidence is insufficient, output INSUFFICIENT."
)


def _ctxs(row: dict) -> list[dict]:
    return [c for c in row.get("ctxs", []) if isinstance(c, dict)]


def _is_gold(ctx: dict) -> bool:
    return ctx.get("has_answer") is True or ctx.get("has_answer") == 1


def _clean(ctx: dict) -> bool:
    return bool(str(ctx.get("text") or "").strip() and str(ctx.get("title") or "").strip())


def decode_aliases(raw: object) -> tuple[str, ...]:
    import json as _json

    decoded = _json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(decoded, list):
        return ()
    return tuple(a for a in decoded if isinstance(a, str) and a.strip())


def normalize_answer(raw: str) -> str:
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
    return line.strip().strip(".").strip()


def gold_dominance(row: dict) -> dict[str, object]:
    """Structural dominance signal for one world's primary survey set."""

    ctxs = _ctxs(row)
    clean = [c for c in ctxs if _clean(c)]
    gold = [c for c in clean if _is_gold(c)]
    noise = [c for c in clean if not _is_gold(c)]
    survey = noise[:8] + gold
    first_gold_rank = next((survey.index(c) + 1 for c in survey if _is_gold(c)), None)
    aliases = decode_aliases(row.get("possible_answers"))
    subject = str(row.get("subj") or row.get("s_wiki_title") or "")
    # Ambiguity: how many noise docs mention the subject or a title variant
    # of the question entity (the Holiday-film pattern)?
    entity_terms = {
        t.lower() for t in (subject, *decode_aliases(row.get("s_aliases") or "[]")) if t
    }
    ambiguous_noise = sum(
        1
        for c in noise[:8]
        if any(
            term in (str(c.get("title") or "") + " " + str(c.get("text") or "")).lower()
            for term in entity_terms
        )
    )
    return {
        "n_gold": len(gold),
        "first_gold_rank": first_gold_rank,
        "survey_size": len(survey),
        "ambiguous_noise_docs": ambiguous_noise,
        "gold_token_share": round(
            sum(len(str(g.get("text") or "")) for g in gold)
            / max(1, sum(len(str(c.get("text") or "")) for c in survey)),
            3,
        ),
    }


def failure_mode(reply: str, aliases: tuple[str, ...], gold_texts: list[str]) -> str:
    """Classify one probe failure: span_selection / normalization / refusal / pass."""

    answer = normalize_answer(reply)
    if not answer:
        return "refusal"
    if answer.lower() == "insufficient":
        return "refusal"
    if alias_hit_v2(answer, aliases):
        return "pass"
    # Did the reply text come from a gold passage (right span, missed alias)
    # or from a noise passage (wrong span)?
    answer_norm = answer.lower()
    for text in gold_texts:
        if answer_norm and answer_norm in str(text).lower():
            return "normalization"
    return "span_selection"


def reader_probe(question: str, docs_text: str) -> str:
    body = {
        "model": READER_MODEL,
        "messages": [
            {"role": "system", "content": READER_SYSTEM},
            {"role": "user", "content": f"Question:\n{question}\n\nEvidence:\n{docs_text}"},
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
    return (message.get("content") or "").strip() or (message.get("reasoning") or "").strip()


def load_pool(max_worlds: int) -> list[dict]:
    pool: list[dict] = []
    seen_rows: set[str] = set()
    seen_entities: set[str] = set()
    with POPQA_ROWS.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = str(row["id"])
            if key in seen_rows:
                continue
            seen_rows.add(key)
            entity = str(row.get("subj_id") or key)
            if entity in seen_entities:
                continue
            if not gold_sane_v2(row):
                continue
            ctxs = _ctxs(row)
            if sum(1 for c in ctxs if _clean(c) and not _is_gold(c)) < 2:
                continue
            seen_entities.add(entity)
            pool.append(row)
            if len(pool) >= max_worlds:
                break
    return pool


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-worlds", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(f"output exists: {args.output}", file=sys.stderr)
        return 2
    started = time.perf_counter()
    pool = load_pool(args.max_worlds)
    have_key = bool(os.environ.get("SIFLOW_API_KEY"))
    worlds_out: list[dict[str, object]] = []
    for row in pool:
        ctxs = _ctxs(row)
        clean = [c for c in ctxs if _clean(c)]
        gold = [c for c in clean if _is_gold(c)]
        noise = [c for c in clean if not _is_gold(c)]
        survey = noise[:8] + gold
        aliases = decode_aliases(row.get("possible_answers"))
        entry: dict[str, object] = {
            "world_id": f"world-{row['id']}",
            "question": str(row.get("question") or "")[:100],
            "aliases": list(aliases[:3]),
            **gold_dominance(row),
        }
        if have_key:
            docs_text = "\n\n".join(
                f"[{c.get('title')}] {str(c.get('text') or '').strip()[:600]}" for c in survey
            )
            reply = reader_probe(str(row.get("question") or ""), docs_text)
            mode = failure_mode(reply, aliases, [str(g.get("text") or "") for g in gold])
            entry["probe_reply"] = reply[:80]
            entry["failure_mode"] = mode
        worlds_out.append(entry)
    modes = [w.get("failure_mode") for w in worlds_out if w.get("failure_mode")]
    summary = {
        "pool_size": len(pool),
        "tier_counts": {
            m: modes.count(m) for m in ("pass", "normalization", "span_selection", "refusal")
        },
        "mid_difficulty_available": modes.count("span_selection") >= 4,
        "recommendation": (
            "span_selection worlds are the mid-difficulty tier where memory "
            "can change outcomes; normalize/alias worlds need scoring or item "
            "fixes before they carry signal"
        ),
    }
    payload = {
        "summary": summary,
        "worlds": worlds_out,
        "meta": {
            "elapsed_seconds": round(time.perf_counter() - started, 1),
            "reader": READER_MODEL if have_key else "none (inventory only)",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
