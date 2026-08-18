# HELMET registry dry-run — 2026-08-17

Dry-run only. **Not cloned. Not downloaded.** Official HELMET scores are not claimed.

Command:

```bash
uv run python scripts/registry_download.py helmet
```

Plan (verbatim fields):

| Field              | Value                                           |
| ------------------ | ----------------------------------------------- |
| `dry_run`          | `true`                                          |
| id                 | `helmet`                                        |
| destination        | `/workspace/wynckeliao/rsi_context/data/helmet` |
| pin                | `af609c4d51b97fc35012099380aa889da961c42d`      |
| known_size_bytes   | 0                                               |
| unknown_size_count | 1                                               |

Acquire command in the plan:

`git clone --filter=blob:none https://github.com/princeton-nlp/HELMET.git <dest> && git -C <dest> checkout --detach af609c4d51b97fc35012099380aa889da961c42d`

Registry notes: Exact-RAG source datasets may have separate licenses or access requirements. Do not follow unpinned `main`.

## Fixture frozen-H smoke (not HELMET)

`scripts/helmet_frozen_h.py` on `tests/fixtures/helmet_rag_sample.jsonl` (2 synthetic RAG/NIAH-style items, word tokenizer, 32-token budget):

`.hl/artifacts/helmet-frozen-h-fixture-2026-08-17.json`

All six packs have `answer_string_present: true` because the fixture is tiny and the budget holds every chunk. `official_helmet_score: false`, `qualification_only: true`. This only proves the compiler + head / lexical / hand-hybrid packers run. It is not a public-bench result.

Do not clone until this dry-run is accepted in-session. Do not start A2. Do not overwrite Repair A/B/C.
