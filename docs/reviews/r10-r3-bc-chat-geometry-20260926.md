# R10 legacy R3 B/C worker request geometry

Status: **offline transport and local-template measurement only**. This run
uses the existing fixed B/C baseline policy and development worlds. It is
not a model-driven test of the R9 PostgreSQL source contrast, a fixed-reader
difficulty result, or a Gate 2 qualification.

`scripts/r10_chat_geometry.py` runs the real R3 sequence runner and frozen
policy hook with the existing scripted offline responder. It records every
full prompt at the `turn.ask_model` dispatch. It then intercepts the real
`_live_responder_factory()` HTTP request locally for each prompt; the
interceptor accepts only the frozen Siflow endpoint and returns a fabricated
empty response without network access. Each captured prompt SHA256 must match
the hook transcript's prompt digest, and the number of captured prompts must
equal the number of dispatched model calls. The artifact contains complete
request JSON without any authorization header or credential.

The legacy `scripts/r3_compare.py` caller invokes `_live_responder_factory()`
with its default argument. Its actual request **omits**
`chat_template_kwargs`, while the later R4 frozen worker profile specifies
`enable_thinking=false`. The counts below use the pinned local Qwen tokenizer
and its default chat-template behavior, with the system role and assistant
generation prefix. They are exact for that local rendering. The Siflow
provider's template and default behavior were not independently attested, so
these are **not certified provider input-token counts**. The API's
provider-reported usage remains the authority for paid runs. The hook's
`model_tokens_in` is a word estimate and is not used for these counts.

| Development cell | Dispatched calls | Largest local rendered input | Unique same-call document→later-question spans | Offline result |
| --- | ---: | ---: | ---: | --- |
| B fixed baseline | 31 | 873 tokens | 5 | PASS |
| C fixed baseline | 18 | 591 tokens | 2 | FAIL |

Example half-open token intervals in the complete rendered chat: B
`s2-constraint` has its visible constraint document at `[25, 76)` and its
full later question at `[388, 411)`, a 312-token intervening gap; C
`c1-mutation` has its visible notice at `[24, 120)` and full later question at
`[555, 571)`, a 435-token gap. These are **document-to-question** positions,
not validated decisive evidence clauses. Calls without a unique document
and later question in the same prompt have explicit unavailable offsets.
This measurement does not establish long-source dependency or robustness to
evidence position.

The tokenizer is `Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b`.
Both tokenizer files are SHA256-verified before loading; their canonical
manifest digest is
`8ff74a229e5d1771200efaaa7e411028fd6ab68a080d93138d76476e9e494290`.
The runtime uses locked `transformers==5.15.0`, `tokenizers==0.22.2`, and
`jinja2==3.1.6`. The script fails if these versions, tokenizer files, or
rendered token-ID/offset mappings disagree. No optional package is added to
the project dependencies.

Replay from the repository root with the pinned tokenizer snapshot available:

```bash
uv run --frozen --no-sync \
  --with 'transformers==5.15.0' \
  --with 'tokenizers==0.22.2' \
  --with 'jinja2==3.1.6' \
  python scripts/r10_chat_geometry.py \
  --tokenizer-path models/qwen3.6-27b \
  --output artifacts/rsi-core-v1/r10-r3-bc-legacy-chat-geometry-v2-20260926.json
```

The ignored raw artifact has SHA256
`88a53b3ab04a75d6b682eda80b63347675a4201229822364cb8dab7e7c1d9e92`.
It carries the full request bodies, per-call identities, exact local token
counts and unique offset intervals, as well as source and world hashes. The
next model-driven R9 task must capture its own requests under a fixed profile
and compare full, withheld, swapped, and decisive-deletion material.

The first raw artifact (`r10-r3-bc-legacy-chat-geometry-20260926.json`, SHA256
`20f3f1dd325d43a3a589c85451d13c3cbb6a72ed89a65089463cd0b479d8a8dd`)
is retained as superseded evidence. Code review found that it reported only
the opening phrase of each question as the query interval. Version 2 extends
each unique question anchor through its `?` terminator. The query **start**
and evidence-to-query distances are unchanged; the full question intervals
and this report supersede the first artifact.
