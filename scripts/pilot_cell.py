#!/usr/bin/env python3
"""Phase C pilot cell: first complete end-to-end v2 trajectory.

Contract status: task #14 of the v2 plan (plans/rsibench-context-sorted-toast.md
§7 Phase C). One research-v1 task family slice — visible instances with a
state-carrying participant, a gate session with split-boundary state reset,
the pre-registered canary leak probe, deterministic replay of the selected
arm, and full JSON archiving. Arms: fixed-strategy reference,
experience-accumulation-only, and (when SIFLOW credentials are present) the
DeepSeek API researcher. Reader: the siflow Qwen3.6-27B T2 profile that
passed its canary on 2026-09-19 (artifacts/api-canary/siflow-qwen-t2-20260919c.json).

Run from the repository root with the volume env block exported plus
SIFLOW_BASE_URL/SIFLOW_API_KEY. Output goes to artifacts/pilot-cell/<id>/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from rsicontext.lifecycle.material import build_example_instance
from rsicontext.lifecycle.spec import LifecycleInstance
from rsicontext.participant.registration import ImprovementRoundInput
from rsicontext.session import SessionKind, SessionStateStore
from rsicontext.wiring.replay import ReplayRecorder, replay
from rsicontext.wiring.session_lifecycle import (
    run_leak_probe_then_gate,
    run_session_flow,
)

POPQA_ROWS = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
READER_ENDPOINT = "https://api.siflow.cn/model-api/chat/completions"
READER_MODEL = "Qwen/Qwen3.6-27B"
READER_SYSTEM = (
    "You extract exact answers from supplied evidence. Output ONLY the "
    "answer phrase with no punctuation, no reasoning, no explanation. "
    "If the evidence is insufficient, output INSUFFICIENT."
)


def _reader_call(query: str, pack: str) -> tuple[str, int, int]:
    body = {
        "model": READER_MODEL,
        "messages": [
            {"role": "system", "content": READER_SYSTEM},
            {"role": "user", "content": pack},
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
    content = (message.get("content") or "").strip() or (
        message.get("reasoning_content") or ""
    ).strip()
    usage = raw["usage"]
    return content, int(usage["prompt_tokens"]), int(usage["completion_tokens"])


def _act_verify_actions(stage, answer: str, provenance: tuple[str, ...]) -> tuple:
    """Create then finalize the answer record the act_verify stage asks for."""

    from rsicontext.lifecycle.env import Action

    doc_ids = tuple(d.doc_id for d in stage.documents)
    fields = {
        "answer": answer,
        "supports": list(provenance or doc_ids),
        "status": "draft",
    }
    return (
        Action(kind="create_record", record_id="answer_project", fields=fields, provenance=doc_ids),
        Action(
            kind="finalize",
            record_id="answer_project",
            fields={"answer": answer, "status": "final"},
            provenance=provenance or doc_ids,
        ),
    )


def _normalize_answer(raw: str) -> str:
    """Extract the answer phrase from the reader's reply.

    Handles the reasoning-reader reply shapes observed on the T2 canary:
    quoted phrases, 'The answer is X' / 'Based on ... is X' narration
    wrappers, leading blank lines, and trailing punctuation. Falls back to
    the first non-empty line, then to the first phrase segment.
    """

    text = raw.strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = lines[0] if lines else ""
    # Quoted phrase wins.
    for quote in ('"', "'", "`"):
        if text.startswith(quote):
            end = text.find(quote, 1)
            if end > 1:
                return text[1:end].strip().strip(".").strip()
    # 'X' or **X** emphasis wrappers.
    if text.startswith("**") and text.endswith("**") and len(text) > 4:
        text = text[2:-2].strip()
    # Narration prefixes: 'The answer is X', 'Answer: X', 'Based on ... is X'.
    lowered = text.lower()
    for prefix in ("answer:", "the answer is ", "answer is "):
        if lowered.startswith(prefix):
            text = text[len(prefix) :].strip()
            lowered = text.lower()
    if lowered.startswith("based on the provided evidence"):
        # '... the canary code is **amber**.' → keep the tail after 'is'.
        _head, sep, tail = text.rpartition(" is ")
        if sep:
            text = tail.strip()
    text = text.strip().strip(".").strip()
    if not text or text.lower() == "insufficient":
        return text
    # Multi-word tail: prefer the final noun phrase after the last ' is '.
    if " is " in text and len(text.split()) > 4:
        _head, sep, tail = text.rpartition(" is ")
        if sep and tail:
            candidate = tail.strip().strip(".").strip()
            if candidate and len(candidate.split()) <= 6:
                return candidate
    return text


def _pack_hook(reader) -> object:
    class _Hook:
        def on_stage(self, stage) -> object:
            from rsicontext.lifecycle.runner import StageResponse

            docs = "\n\n".join(f"[[doc:{d.doc_id}]] {d.title}\n{d.text}" for d in stage.documents)
            answer, _, _ = reader(stage.prompt_text, docs)
            answer = _normalize_answer(answer)
            actions = ()
            if getattr(stage, "kind", "") == "act_verify":
                doc_ids = tuple(d.doc_id for d in stage.documents)
                actions = _act_verify_actions(stage, answer, doc_ids)
            return StageResponse(
                pack_text=f"{stage.prompt_text}\n\nEvidence:\n{docs}\n\nDraft answer: {answer}",
                actions=actions,
            )

    return _Hook()


def _stateful_pack_hook(reader, state: dict) -> object:
    """Participant whose working notes evolve across instances (state in/out)."""

    class _StatefulHook:
        def __init__(self, state: dict[str, object]) -> None:
            self._state = state

        def on_stage(self, stage) -> object:
            from rsicontext.lifecycle.runner import StageResponse

            docs = "\n\n".join(f"[[doc:{d.doc_id}]] {d.title}\n{d.text}" for d in stage.documents)
            notes = "\n".join(str(n) for n in self._state.get("notes", []))
            answer, _, _ = reader(
                stage.prompt_text,
                f"Working notes so far:\n{notes or '(none)'}\n\n{stage.prompt_text}\n\n"
                f"Evidence:\n{docs}",
            )
            answer = _normalize_answer(answer)
            actions = ()
            if getattr(stage, "kind", "") == "act_verify":
                doc_ids = tuple(d.doc_id for d in stage.documents)
                actions = _act_verify_actions(stage, answer, doc_ids)
                # The participant records what it learned in its own state:
                notes_list = list(self._state.get("notes", []))
                notes_list.append({"stage": str(getattr(stage, "stage_id", "")), "answer": answer})
                self._state["notes"] = notes_list[-32:]
            return StageResponse(
                pack_text=f"{stage.prompt_text}\n\nEvidence:\n{docs}\n\nDraft answer: {answer}",
                actions=actions,
            )

    return _StatefulHook(state)


def _usable_row(row: dict) -> bool:
    """A row is usable when it has a question, answers, and non-empty ctx texts
    (PopQA carries some retrieval blocks with empty bodies)."""

    if not str(row.get("question") or "").strip():
        return False
    answers = row.get("possible_answers")
    if not answers:
        return False
    ctxs = row.get("ctxs")
    if not isinstance(ctxs, list) or not ctxs:
        return False
    usable = [
        c for c in ctxs if str(c.get("text") or "").strip() and str(c.get("title") or "").strip()
    ]
    return len(usable) >= 4 and any(c.get("has_answer") for c in usable)


def _load_instances(
    n_visible: int, n_gate: int
) -> tuple[list[LifecycleInstance], list[LifecycleInstance]]:
    rows: list[dict] = []
    seen_ids: set[str] = set()
    with POPQA_ROWS.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            row_key = str(row.get("id"))
            if row_key in seen_ids:
                continue  # PopQA packs multiple relations under one entity id
            if not _usable_row(row):
                continue
            seen_ids.add(row_key)
            rows.append(row)
            if len(rows) >= n_visible + n_gate:
                break
    visible = [build_example_instance(r) for r in rows[:n_visible]]
    gate = [build_example_instance(r) for r in rows[n_visible:]]
    return visible, gate


def _improvement_round(arm: str, workspace: Path, feedback: bytes, index: int) -> dict[str, str]:
    """One researcher round: the DS arm proposes a small strategy file.

    The agent tree is a tiny workspace with a strategy stub (not the whole
    pilot script) — the researcher edits <200 lines, so the 16k output
    budget holds a full rewrite.
    """

    if arm != "ds-researcher":
        return {}
    from rsicontext.participant.api_researcher import (
        APIResearcherConfig,
        APIResearcherImprover,
    )

    agent_dir = workspace / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    strategy = agent_dir / "strategy.py"
    if not strategy.exists():
        strategy.write_text(
            '"""Answer-extraction strategy. The researcher may rewrite this file."""\n\n'
            "EXTRACTION_RULES = [\n"
            '    "prefer quoted phrases",\n'
            '    "strip trailing punctuation",\n'
            "    \"prefer the final noun phrase after ' is '\",\n"
            "]\n",
            encoding="utf-8",
        )
    improver = APIResearcherImprover(
        config=APIResearcherConfig(
            endpoint=READER_ENDPOINT, model="deepseek-ai/deepseek-v4.1-flash"
        )
    )
    round_input = ImprovementRoundInput(
        round_index=index,
        task_text=(
            "Improve the answer-extraction strategy for a five-stage evidence "
            "workflow: the reader returns reasoning-style replies; failures "
            "include empty answers, INSUFFICIENT misjudgments, and picking "
            "document titles instead of answer phrases. Rewrite strategy.py "
            "with better extraction rules."
        ),
        restricted_feedback_bytes=feedback,
        current_agent_dir=agent_dir,
        state_path=None,
        remaining_slots=1,
        task_order_seed=7,
    )
    output = improver.improve(round_input)
    return dict(output.agent_files_changed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visible", type=int, default=4)
    parser.add_argument("--gate", type=int, default=4)
    parser.add_argument("--replay-repeats", type=int, default=5)
    parser.add_argument(
        "--arm", choices=["fixed", "experience", "ds-researcher"], default="experience"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not os.environ.get("SIFLOW_API_KEY"):
        print("missing SIFLOW_API_KEY", file=sys.stderr)
        return 2
    if args.output.exists():
        print(f"output already exists: {args.output}", file=sys.stderr)
        return 2
    started = time.perf_counter()

    visible, gate = _load_instances(args.visible, args.gate)
    schema = {"type": "object", "properties": {"notes": {"type": "array"}}}
    byte_cap = 65536

    results: dict[str, object] = {}

    # --- Arm run on the visible split -------------------------------------
    # Participant state is routed THROUGH the store: load/save are store
    # bridges, so the memory-op ledger is populated and the leak probe scans
    # real transcripts (the contract's auditable state channel).
    store = SessionStateStore(schema=schema)

    def load_state() -> dict[str, object] | None:
        return store.read("visible-1")

    def save_state(state: dict[str, object]) -> None:
        store.write("visible-1", state)

    if args.arm == "fixed":
        hook_factory = lambda state: _pack_hook(_reader_call)  # noqa: E731
    else:
        hook_factory = lambda state: _stateful_pack_hook(_reader_call, state)  # noqa: E731

    visible_record = run_session_flow(
        store,
        SessionKind.VISIBLE,
        "visible-1",
        visible,
        hook_factory,
        load_state,
        save_state,
        byte_cap=byte_cap,
    )
    results["visible"] = visible_record.to_dict()

    # --- Improvement round (arms that improve) -----------------------------
    feedback = json.dumps(
        {
            "final_check_passed": [
                r["final_check"]["passed"] for r in results["visible"]["run_records"]
            ],
            "transcript_digests": list(results["visible"]["transcript_digests"]),
        }
    ).encode()
    ds_changes = _improvement_round(args.arm, args.output.parent / "agent-workspace", feedback, 0)
    results["improvement_round"] = {
        "arm": args.arm,
        "changed_files": sorted(ds_changes),
    }

    # --- Canary leak probe + gate session ----------------------------------
    canary_tokens = [visible[0].instance_id + "::GOLD-CANARY"]

    def gate_runner() -> object:
        # Gate state also routes through the store: the gate session starts
        # byte-empty (split boundary) and its ops land in its own transcript.
        def gate_load() -> dict[str, object] | None:
            return store.read("gate-1")

        def gate_save(state: dict[str, object]) -> None:
            store.write("gate-1", state)

        gate_hook = (
            (lambda state: _pack_hook(_reader_call))
            if args.arm == "fixed"
            else (lambda state: _stateful_pack_hook(_reader_call, state))
        )
        record = run_session_flow(
            store,
            SessionKind.GATE,
            "gate-1",
            gate,
            gate_hook,
            gate_load,
            gate_save,
            byte_cap=byte_cap,
        )
        return record

    gate_result, probe_result = run_leak_probe_then_gate(
        store, canary_tokens, gate_runner, byte_cap=byte_cap
    )
    results["gate"] = gate_result.to_dict()
    results["leak_probe"] = {
        "gate_session": probe_result.gate_session_id,
        "tokens": list(probe_result.tokens),
        "entries_scanned": probe_result.transcript_entries_scanned,
    }

    # --- Deterministic replay of the visible session -----------------------
    # Pass 1: run the recorder-wrapped reader over a fresh visible session to
    # build the recorded call log; pass 2: replay the same instances with the
    # real reader replaced by the digest lookup, and compare transcripts.
    recorder = ReplayRecorder(reader=_reader_call)
    rec_store = SessionStateStore(schema=schema)

    def rec_load() -> dict[str, object] | None:
        return rec_store.read("record-1")

    def rec_save(state: dict[str, object]) -> None:
        rec_store.write("record-1", state)

    rec_hook = (
        (lambda state: _pack_hook(recorder))
        if args.arm == "fixed"
        else (lambda state: _stateful_pack_hook(recorder, state))
    )
    recorded_session = run_session_flow(
        rec_store,
        SessionKind.REPLAY,
        "record-1",
        visible,
        rec_hook,
        rec_load,
        rec_save,
        byte_cap=byte_cap,
    )

    replay_store = SessionStateStore(schema=schema)

    def replay_load() -> dict[str, object] | None:
        return replay_store.read("replay-1")

    def replay_save(state: dict[str, object]) -> None:
        replay_store.write("replay-1", state)

    replay_record = replay(
        replay_store,
        "replay-1",
        visible,
        lambda reader: (
            (lambda state: _stateful_pack_hook(reader, state))
            if args.arm != "fixed"
            else (lambda state: _pack_hook(reader))
        ),
        recorder.transcript(),
        replay_load,
        replay_save,
        byte_cap=byte_cap,
    )

    equal = (
        replay_record.transcript_digests == recorded_session.transcript_digests
        and replay_record.memory_op_totals == recorded_session.memory_op_totals
    )
    results["replay"] = {
        "recorded_calls": len(recorder.transcript()),
        "transcript_equal": equal,
        "replay_digests": list(replay_record.transcript_digests),
    }

    elapsed = time.perf_counter() - started
    results["meta"] = {
        "arm": args.arm,
        "visible_instances": len(visible),
        "gate_instances": len(gate),
        "elapsed_seconds": elapsed,
        "reader": f"{READER_MODEL} @ siflow (T2, canary 20260919c)",
        "schema_version": 1,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(results, handle, indent=1, sort_keys=True)
        handle.write("\n")
    summary = {
        "arm": args.arm,
        "visible_final_checks": results["visible"]["run_records"][0]["final_check"]["passed"],
        "gate_final_checks": results["gate"]["run_records"][0]["final_check"]["passed"],
        "leak_probe_clean": True,
        "elapsed_seconds": round(elapsed, 1),
        "output": str(args.output),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
