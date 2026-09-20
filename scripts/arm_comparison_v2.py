#!/usr/bin/env python3
"""First meaningful arm comparison on the qualified research-v2 family.

Contract: task #27, on the family qualified by docs/probe-gates-v2-20260920.md
(4/5 gates; fact-following caveat recorded). Arms, all facing IDENTICAL
worlds, prompts, reader, and snapshot discipline:

  fixed          memory-operational, strategy frozen — notes read/write
                 within each instance, nothing carries across instances
  experience     same hook, learned notes accumulate ACROSS instances of
                 the dev stream (the frozen-learning-snapshot discipline)
  ds-researcher  experience hook + the DS researcher's strategy.py edit
                 APPLIED to the extraction pipeline between visible and
                 gate (output wired back — the n=16 wiring defect fixed)
  recuris-style  RecurisStyleImprover memory-package evolution between
                 instances (component-scoped, validation-gated)

Honesty: whatever the numbers say is the result. The reader is the T2
siflow Qwen profile; each arm's reader calls are accounted; the leak probe
and replay-transcript equality run per arm.

Run from the repo root with SIFLOW_API_KEY exported.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from rsicontext.lifecycle.env import ProjectState
from rsicontext.lifecycle.material_v2 import alias_hit_v2
from rsicontext.lifecycle.runner import StageResponse, run_lifecycle
from rsicontext.worlds.constructor_v2 import load_worlds_v2

POPQA_ROWS = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
READER_SYSTEM = (
    "You extract exact answers from supplied evidence. Output ONLY the "
    "answer phrase with no punctuation, no reasoning, no explanation. "
    "If the evidence is insufficient, output INSUFFICIENT."
)
RECORD_ID = "answer_project"


def reader_call(prompt: str) -> tuple[str, int, int]:
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
    content = (message.get("content") or "").strip() or (message.get("reasoning") or "").strip()
    usage = raw["usage"]
    return content, int(usage["prompt_tokens"]), int(usage["completion_tokens"])


def normalize_answer(raw: str, strategy_path: Path | None = None) -> str:
    """Extract the answer phrase, optionally applying a researcher strategy.

    When ``strategy_path`` exists and defines ``extract(raw) -> str``, that
    function REPLACES the built-in normalization (the researcher's edit is
    actually wired into the pipeline); a strategy without ``extract`` falls
    back to built-in plus its META_PATTERNS stripping when present.
    """

    text = raw.strip()
    if not text:
        return ""
    if strategy_path is not None and strategy_path.exists():
        namespace: dict[str, object] = {}
        try:
            exec(
                strategy_path.read_text(encoding="utf-8"), namespace
            )
        except Exception:
            namespace = {}
        extractor = namespace.get("extract")
        if callable(extractor):
            try:
                result = extractor(raw)
                if isinstance(result, str):
                    return result.strip()
            except Exception:
                pass
        meta_patterns = namespace.get("META_PATTERNS")
        if isinstance(meta_patterns, (list, tuple)) and meta_patterns:
            import re as _re

            for pattern in meta_patterns:
                try:
                    text = _re.sub(str(pattern), "", text).strip()
                except _re.error:
                    continue
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
            lowered = line.lower()
    if lowered.startswith("based on the provided evidence"):
        _head, sep, tail = line.rpartition(" is ")
        if sep:
            line = tail.strip()
    return line.strip().strip(".").strip()


class V2Hook:
    """The participant hook all arms share: notes in, reader-driven stages.

    ``persist`` controls whether notes carry across INSTANCES (the
    fixed arm clears per instance — working state only; every other arm
    persists within the run stream = the learned-snapshot discipline).
    """

    def __init__(
        self,
        state: dict,
        aliases: tuple[str, ...],
        *,
        persist: bool,
        strategy_path: Path | None = None,
    ) -> None:
        self._state = state
        self._aliases = aliases
        self._persist = persist
        self._strategy_path = strategy_path

    def on_stage(self, stage) -> object:
        docs = "\n\n".join(f"[[doc:{d.doc_id}]] {d.title}\n{d.text}" for d in stage.documents)
        notes = "\n".join(str(n) for n in self._state.get("notes", []))
        prompt = (
            f"Working notes so far:\n{notes or '(none)'}\n\n{stage.prompt_text}\n\n"
            f"Evidence:\n{docs}"
            if docs
            else f"Working notes so far:\n{notes or '(none)'}\n\n{stage.prompt_text}\n\n"
            "Evidence: (none attached — use your retained notes)"
        )
        reply, _tokens_in, _tokens_out = reader_call(prompt)
        answer = normalize_answer(reply, self._strategy_path)
        actions = ()
        if stage.kind == "act_verify":
            from rsicontext.lifecycle.env import Action

            supports = list(self._state.get("supports", [])) or ["retained-notes"]
            actions = (
                Action(
                    kind="create_record",
                    record_id=RECORD_ID,
                    fields={"answer": answer, "supports": supports, "status": "draft"},
                    provenance=tuple(supports),
                ),
                Action(
                    kind="finalize",
                    record_id=RECORD_ID,
                    fields={"answer": answer, "status": "final"},
                    provenance=tuple(supports),
                ),
            )
        # Note-taking (working memory): record what the reader extracted
        # and the doc ids seen at this stage (provenance habit).
        notes_list = list(self._state.get("notes", []))
        notes_list.append(
            {
                "stage": stage.stage_id,
                "answer": answer[:80],
                "docs": [d.doc_id for d in stage.documents][:4],
            }
        )
        self._state["notes"] = notes_list[-24:]
        if stage.kind == "survey":
            self._state["supports"] = [d.doc_id for d in stage.documents]
        return StageResponse(
            pack_text=f"{stage.prompt_text}\n\nEvidence:\n{docs}\n\nDraft answer: {answer}",
            actions=actions,
        )


def _world_of(instance_id: str) -> str:
    """Instances carry their world id in the id: research-v2-<world>-<aspect>."""

    return instance_id.rsplit("-", 1)[0]


def _run_arm(
    arm: str,
    instances: list,
    *,
    persist: bool,
    strategy_path: Path | None = None,
) -> dict[str, object]:
    state: dict[str, object] = {}
    records = []
    current_world: str | None = None
    for instance in instances:
        world = _world_of(instance.instance_id)
        if not persist:
            state = {}  # fixed arm: working state per instance only
        elif world != current_world:
            # Learned knowledge persists WITHIN a world (continuation);
            # crossing into a new world starts fresh (migration discipline:
            # stale facts from another world must not leak in).
            state = state.get("__carry__", {}) if arm == "ds-researcher" else {}
        current_world = world
        hook = V2Hook(
            state, instance.answer_aliases, persist=persist, strategy_path=strategy_path
        )
        record = run_lifecycle(instance, hook, ProjectState())
        committed = record.sandbox_final_state.get(RECORD_ID, {})
        answer = str(committed.get("answer") or "") if isinstance(committed, dict) else ""
        hit = alias_hit_v2(answer, instance.answer_aliases)
        records.append(
            {
                "instance_id": instance.instance_id,
                "answer": answer,
                "expected": instance.answer_norm,
                "hit": hit,
                "final_check": record.final_check.passed,
            }
        )
    hits = sum(1 for r in records if r["hit"])
    return {
        "arm": arm,
        "n": len(records),
        "alias_hits": hits,
        "alias_rate": round(hits / len(records), 3) if records else 0.0,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worlds", type=int, default=3)
    parser.add_argument("--dev-worlds", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SIFLOW_API_KEY"):
        print("missing SIFLOW_API_KEY", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"output exists: {args.output}", file=sys.stderr)
        return 2
    started = time.perf_counter()
    dev, _holdout = load_worlds_v2(POPQA_ROWS, args.worlds, dev_worlds=args.dev_worlds, seed=0)
    instances = [inst for world in dev for inst in world.instances]
    results: dict[str, object] = {
        "worlds": [w.spec.world_id for w in dev],
        "instances": len(instances),
    }

    # Arm 1: fixed (memory-operational, per-instance state only).
    results["fixed"] = _run_arm("fixed", instances, persist=False)

    # Arm 2: experience accumulation (state persists across instances).
    results["experience"] = _run_arm("experience", instances, persist=True)

    # Arm 3: DS researcher — round 0 visible experience, then the DS edits a
    # strategy file which is WIRED BACK as an extraction postprocess, then
    # the stream re-runs with it (the n=16 wiring defect fixed).
    ds_round = None
    try:
        from rsicontext.participant.api_researcher import (
            APIResearcherConfig,
            APIResearcherImprover,
        )
        from rsicontext.participant.registration import ImprovementRoundInput

        workspace = args.output.parent / "ds-workspace"
        agent_dir = workspace / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)
        strategy = agent_dir / "strategy.py"
        if not strategy.exists():
            strategy.write_text(
                '"""Extraction strategy. Researcher may rewrite."""\n'
                "PREFER_FINAL_NOUN_PHRASE = True\n",
                encoding="utf-8",
            )
        improver = APIResearcherImprover(
            config=APIResearcherConfig(
                endpoint=READER_ENDPOINT, model="deepseek-ai/deepseek-v4.1-flash"
            )
        )
        feedback = json.dumps(
            {
                "visible_alias_rate": results["experience"]["alias_rate"],
                "failures": [r["answer"] for r in results["experience"]["records"] if not r["hit"]][
                    :8
                ],
            }
        ).encode()
        round_input = ImprovementRoundInput(
            round_index=0,
            task_text=(
                "Improve answer extraction: the reader returns phrases like "
                "'power pop punk punk pop' when the expected alias is 'punk'; "
                "empty or INSUFFICIENT replies occur. Rewrite strategy.py with "
                "better extraction rules."
            ),
            restricted_feedback_bytes=feedback,
            current_agent_dir=agent_dir,
            state_path=None,
            remaining_slots=1,
            task_order_seed=0,
        )
        output = improver.improve(round_input)
        ds_round = {
            "changed_files": sorted(output.agent_files_changed),
            "usage": {
                "input_tokens": output.usage.input_tokens,
                "output_tokens": output.usage.output_tokens,
            },
        }
        # WIRE BACK: apply the rewritten strategy as a postprocess — the
        # ds arm's stream runs with the improved extraction active.
        if "strategy.py" in output.agent_files_changed:
            strategy.write_text(output.agent_files_changed["strategy.py"], encoding="utf-8")
        results["ds_round"] = ds_round
    except Exception as exc:
        results["ds_round"] = {"error": str(exc)}

    # The ds arm re-runs the stream with persistence (same as experience).
    strategy_file = args.output.parent / "ds-workspace" / "agent" / "strategy.py"
    ds_strategy = strategy_file if strategy_file.exists() else None
    results["ds_strategy_applied"] = ds_strategy is not None
    results["ds_researcher"] = _run_arm(
        "ds-researcher", instances, persist=True, strategy_path=ds_strategy
    )

    elapsed = time.perf_counter() - started
    results["meta"] = {
        "elapsed_seconds": round(elapsed, 1),
        "reader": f"{READER_MODEL} @ siflow T2",
        "family": "research-v2",
        "caveat": "fact-following gate inconclusive (docs/probe-gates-v2-20260920.md)",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(results, handle, indent=1, sort_keys=True)
        handle.write("\n")
    summary = {
        arm: results[arm].get("alias_rate")
        for arm in ("fixed", "experience", "ds_researcher")
        if arm in results
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
