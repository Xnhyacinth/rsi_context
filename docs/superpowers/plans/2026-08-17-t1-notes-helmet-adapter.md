# T1 notes + HELMET frozen-H adapter

> Inline execution. Do not start A2. Do not download HELMET until dry-run is reviewed. Do not commit unless asked.

**Status:** Done. HELMET clone still not executed.

**Goal:** Evaluator extractive `CompressedNote`s on dense gold scores; policy may substitute trusted notes; HELMET RAG compiler works on fixtures; registry dry-run recorded.

**Architecture:** Notes are generated with chunk provenance after `_chunks`. `substitute_extractive_notes` replaces selected source spans with trusted notes when it saves tokens. HELMET adapter maps passages → `Artifact` without researcher code.

## Task 1: Dense extractive notes + substitution

- Modify `src/rsicontext/datasets/hard_long_context.py`
- Create `src/rsicontext/policy/notes.py`
- Tests: `tests/test_hard_long_context.py`, `tests/test_extractive_notes.py`

## Task 2: HELMET fixture adapter + dry-run

- Create `src/rsicontext/datasets/helmet_rag.py`
- Tests: `tests/test_helmet_rag.py`
- Script: `scripts/helmet_frozen_h.py`
- Record: `.hl/artifacts/helmet-dry-run-2026-08-17.md`
