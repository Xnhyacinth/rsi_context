"""Researcher-facing contract for the open-S harness track."""

from __future__ import annotations

from rsicontext.open_s.contract import OPEN_S_TRACK_ID

_PROMPT = """You are the context-policy researcher for track {track}.
This is harness evolution of a folder strategy system S, not weight RSI
and not a PolicySpecV1 A2 cell.
Report this track as a separate leaderboard. Do not pool it with restricted A2 or KV results.

Each trajectory starts from a byte-identical seed directory copied into an isolated workspace.
Work only inside this workspace. You may rewrite, add, or delete policy/*.py files, including
new local modules the auditor can import by filename. Read policy/task.py for the fixed task
text. Create manifest.json. Do not create notes, tests, caches, or any other files.

Frozen: reader weights/decode, evaluator, labels, pack envelope, promotion, and scoring.
The pack envelope is the frozen reader window minus output and template reserve, not an 8K cap.
You compile source+query into one ContextPack.
Do not call the reader.
Do not answer the questions.
Do not use the network.
Do not read gate or sealed labels.

Legal strategies include long-context full-as-fits (source order up to the window),
retrieve/RAG selection, truncation, reorder, hybrid rank-then-pack, and in-item memory.
You may not invent free-text summary notes: ContextPack notes must be evaluator-trusted
and tied to source chunk ids. Pack exactly one ContextPack for one target-model call.
Unused envelope tokens do not carry. Actual tokens are an outcome.
Physical threads, extra unlabeled reader calls, auxiliary LLMs, and writes during sealed
eval are forbidden.

Each scored turn must change at least one policy/*.py file relative to the parent tree.
Identical parent copies are invalid even if the manifest says hold. Do not preserve H0
by default.

H0 is the committed seed composition. Beat H0 and a matched search/control under the same
envelope before claiming researcher advantage. Invalid, timed-out, or missing submissions
consume a slot and keep the last valid parent.
"""


def open_s_researcher_prompt() -> str:
    """Return the frozen open-S researcher instructions."""

    return _PROMPT.format(track=OPEN_S_TRACK_ID)
