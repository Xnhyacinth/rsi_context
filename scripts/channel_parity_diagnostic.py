#!/usr/bin/env python3
"""Channel-equivalence diagnostic (review 2026-09-20 §四.1).

Purpose: with identical, sufficient, SHORT evidence and an identical prompt
shape, verify that semantically valid reader outputs are received
identically across the conditions that previously differed (bare prompt vs
working-notes preamble). This separates reader channel sensitivity from
task difficulty. NOT a benchmark arm; a development diagnostic probe.

Conditions per item:
  A. bare     — "Question:
{q}

Evidence:
{gold}" (the fixed arm's shape)
  B. preamble — "Working notes so far:
(none)

{q}

Evidence:
{gold}" (the stateful arm's shape, empty notes)
  C. notes    — B plus a real method note (no answer content)

If A scores far below B/C, the channel is format-sensitive and the n=16
panel's 0/24-vs-24/24 is channel-dominated, confirming the root-cause
report; if A≈B≈C, the channel is fine and the panel difference needs a
different explanation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import TypedDict


class _Item(TypedDict):
    id: str
    question: str
    answer: str
    gold_text: str


class _ConditionResult(TypedDict):
    hits: int
    n: int
    rate: float
    per_item: list[dict[str, object]]


POPQA_ROWS = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
MODEL = "Qwen/Qwen3.6-27B"
SYSTEM = (
    "You extract exact answers from supplied evidence. Output ONLY the "
    "answer phrase with no punctuation, no reasoning, no explanation. "
    "If the evidence is insufficient, output INSUFFICIENT."
)


def _reader(prompt: str) -> str:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 2048,
        "temperature": 0.0,
        "seed": 42,
        "stream": False,
    }
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['SIFLOW_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    # ENDPOINT is the fixed HTTPS Siflow chat-completions URL.
    with urllib.request.urlopen(request, timeout=300) as response:  # nosec B310
        raw = json.loads(response.read())
    message = raw["choices"][0]["message"]
    return (message.get("content") or "").strip()


def _load_items(n: int) -> list[_Item]:
    items: list[_Item] = []
    seen: set[str] = set()
    with POPQA_ROWS.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = str(row["id"])
            if key in seen:
                continue
            seen.add(key)
            gold = [
                c
                for c in row["ctxs"]
                if c.get("has_answer")
                and str(c.get("text") or "").strip()
                and str(c.get("title") or "").strip()
            ]
            if not gold:
                continue
            answers = json.loads(row["possible_answers"])
            items.append(
                {
                    "id": key,
                    "question": str(row["question"]),
                    "answer": str(answers[0]),
                    "gold_text": str(gold[0]["text"]),
                }
            )
            if len(items) >= n:
                break
    return items


def _hit(reply: str, answer: str) -> bool:
    text = reply.strip().strip(".").strip()
    if not text:
        return False
    if text.lower() == "insufficient":
        return False
    return answer.lower() in text.lower() or text.lower() in answer.lower()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SIFLOW_API_KEY"):
        print("missing SIFLOW_API_KEY", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"output exists: {args.output}", file=sys.stderr)
        return 2
    items = _load_items(args.n)
    method_note = (
        "When several genres are listed, the question usually targets the named "
        "entity's field; prefer the phrase adjacent to the entity mention."
    )
    conditions: dict[str, _ConditionResult] = {}
    for condition, template in (
        ("A_bare", "Question:\n{q}\n\nEvidence:\n{g}"),
        ("B_preamble", "Working notes so far:\n(none)\n\nQuestion:\n{q}\n\nEvidence:\n{g}"),
        (
            "C_notes",
            "Working notes so far:\n- {note}\n\nQuestion:\n{q}\n\nEvidence:\n{g}",
        ),
    ):
        hits = 0
        per_item: list[dict[str, object]] = []
        for item in items:
            prompt = template.format(q=item["question"], g=item["gold_text"], note=method_note)
            reply = _reader(prompt)
            hit = _hit(reply, item["answer"])
            hits += hit
            per_item.append(
                {"id": item["id"], "reply": reply[:120], "expected": item["answer"], "hit": hit}
            )
        conditions[condition] = {
            "hits": hits,
            "n": len(items),
            "rate": round(hits / len(items), 3) if items else 0.0,
            "per_item": per_item,
        }
    a = conditions["A_bare"]["rate"]
    b = conditions["B_preamble"]["rate"]
    c = conditions["C_notes"]["rate"]
    verdict = {
        "channel_format_sensitive": (b - a) >= 0.25 or (c - a) >= 0.25,
        "rates": {"A_bare": a, "B_preamble": b, "C_notes": c},
    }
    results = {"conditions": conditions, "verdict": verdict}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(results, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
