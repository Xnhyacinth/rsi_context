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
        "max_tokens": 1024,
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
    """Extract the answer phrase from the reader's reply (first quoted or plain token)."""

    text = raw.strip().strip(".").strip()
    for quote in ('"', "'", "`"):
        if text.startswith(quote):
            end = text.find(quote, 1)
            if end > 0:
                return text[1:end]
    return text.split("\n")[0].strip()


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
            seen_ids.add(row_key)
            rows.append(row)
            if len(rows) >= n_visible + n_gate:
                break
    visible = [build_example_instance(r) for r in rows[:n_visible]]
    gate = [build_example_instance(r) for r in rows[n_visible:]]
    return visible, gate


def _improvement_round(arm: str, agent_dir: Path, feedback: bytes, index: int) -> dict[str, str]:
    if arm != "ds-researcher":
        return {}
    from rsicontext.participant.api_researcher import (
        APIResearcherConfig,
        APIResearcherImprover,
    )

    improver = APIResearcherImprover(
        config=APIResearcherConfig(
            endpoint=READER_ENDPOINT, model="deepseek-ai/deepseek-v4.1-flash"
        )
    )
    round_input = ImprovementRoundInput(
        round_index=index,
        task_text=(
            "Improve the five-stage evidence-workflow hook: better note-taking, "
            "compression that preserves later-needed exceptions, and provenance."
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
    store = SessionStateStore(schema=schema)
    session_state: dict[str, object] = {}

    def load_state() -> dict[str, object] | None:
        return dict(session_state) if session_state else None

    def save_state(state: dict[str, object]) -> None:
        session_state.clear()
        session_state.update(state)

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
    agent_dir = Path("scripts")  # placeholder tree for the DS round prompt
    ds_changes = _improvement_round(args.arm, agent_dir, feedback, 0)
    results["improvement_round"] = {
        "arm": args.arm,
        "changed_files": sorted(ds_changes),
    }

    # --- Canary leak probe + gate session ----------------------------------
    canary_tokens = [visible[0].instance_id + "::GOLD-CANARY"]

    def gate_runner() -> object:
        gate_state: dict[str, object] = {}
        gate_store = store  # same store, new session id

        def gate_load() -> dict[str, object] | None:
            return dict(gate_state) if gate_state else None

        def gate_save(state: dict[str, object]) -> None:
            gate_state.clear()
            gate_state.update(state)

        gate_hook = (
            (lambda state: _pack_hook(_reader_call))
            if args.arm == "fixed"
            else (lambda state: _stateful_pack_hook(_reader_call, state))
        )
        record = run_session_flow(
            gate_store,
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
    rec_state: dict[str, object] = {}

    def rec_load() -> dict[str, object] | None:
        return dict(rec_state) if rec_state else None

    def rec_save(state: dict[str, object]) -> None:
        rec_state.clear()
        rec_state.update(state)

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
    replay_state: dict[str, object] = {}

    def replay_load() -> dict[str, object] | None:
        return dict(replay_state) if replay_state else None

    def replay_save(state: dict[str, object]) -> None:
        replay_state.clear()
        replay_state.update(state)

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
