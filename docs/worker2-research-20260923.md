# Worker-2 model research (2026-09-23)

Source: the worker2 agent's live research (all network checks run from
this box that day; primary sources; UNVERIFIED marks preserved). This
record + the profile entry below are the durable outputs.

## Verified corrections to earlier assumptions

- **WITHDRAWN (2026-09-24 review): the "gpt-5.4 does not exist" claim
  was wrong.** OpenAI announced GPT-5.4 on 2026-03-05; the deprecations
  page's `gpt-5.4-cyber` entry showed a DEPRECATED VARIANT, not the
  family's nonexistence. "Model exists", "our account can access it",
  "Siflow offers it", and "the variant is deprecated" are four
  distinct questions — the original reasoning conflated them. The
  current documented chat family is GPT-6 (`gpt-6-astra/sol/luna`);
  gpt-5.4's API availability from this account remains UNVERIFIED —
  verify before any closed-source provisioning decision.
- **Siflow is not Qwen-only**: live `/v1/models` query (HTTP 200) shows
  16 models across 6 families (Qwen, DeepSeek, Z.ai GLM, Gemma, Kimi,
  gpt-oss-120b) — but NO closed-source frontier family.
- **All three closed-source endpoints are network-reachable from this
  box** (401/403 = auth-only missing). No OpenAI/Anthropic/Google keys
  exist here; provisioning is UNVERIFIED.

## Decisions

1. **Registered now (zero code changes): `siflow-glm-5.2`** — a
   second model FAMILY (Z.ai) through the existing channel, verified
   LIVE today with the exact frozen worker payload (seed 42 / temp 0.0
   / max_tokens 2048 / chat-completions / extractor system prompt):
   content returned, finish stop, model echo, full usage. Honest tier:
   `provider_revision: null` (replication-only, same as the current
   Qwen reader). CAVEAT (pinned in the profile via max_output_tokens
   4096): it is a REASONING model — on a trivial probe 172/176
   completion tokens were reasoning; budgets must leave room for
   visible content.
2. **Primary closed-source candidate (once a key is provisioned):
   OpenAI `gpt-6-luna`** ($0.10/$0.50 per 1M; 1.05M ctx / 128K out;
   protocol-native — zero reader changes; each gpt-6 id is a
   documented pinned snapshot). One live probe needed once a key
   exists: max_tokens acceptance (gpt-6 may require
   max_completion_tokens — a one-field change in a frozen reader, its
   own reviewed diff), temperature-0.0, seed (beta).
3. **Fallback: `gemini-3.8-flash`** via Google's OpenAI-compat
   endpoint (config-only) — caveats: beta passthrough UNVERIFIED
   (silent param-ignore risk), rolling non-pinned id (register at
   replication-only tier), promo pricing flips 2026-12-31.
4. **Rejected: Claude** — best pinning but the worst protocol fit
   (proprietary Messages API, no seed, temperature-0 "may be rejected"
   post-Opus-4.6; a ~200-400-line adapter touching a frozen boundary);
   haiku-4.5 additionally hits its retirement window Oct 15, 2026.

## What was added to the repo

- `configs/api_profiles.json`: the `siflow-glm-5.2-worker2` profile
  (protocol-validated by the existing profile tests; 4096 output — the
  reasoning-burn headroom; replication-only tier).
- This record.

## Not yet done (the honest boundary)

- The closed-source arm (gpt-6-luna): blocked on key provisioning.
- The second-family arm's RUN: the profile is registered but no run
  uses it yet — wiring it into a comparison entry is the next step
  after the audit fixes.
- The raw Siflow catalog snapshot lives in a job-scoped tmp (not
  durable); re-fetchable from `https://api.siflow.cn/model-api/v1/models`.
