# B/C Gate 1 offline admission (2026-09-25)

This admission uses the tracked B/C development builders and scripted local
responses. It makes **zero** Siflow or GPU calls, makes **zero** researcher
draws, and does not run the evaluation worlds. The planned denominator remains
two researcher draws per group for a future isolated, versioned live pilot;
there is no valid-update-rate estimate here. Run with:

```bash
uv run --no-sync python scripts/r3_bc_researcher_pilot.py \
  --preflight configs/r3_gate1_offline_preflight_v3.json \
  --resource-root /volume/pt-dev/qjiu/rsi_context_worktrees/resources/r3_visible_dev_7052c06 \
  --output artifacts/rsi-core-v1/r3-bc-gate1-offline-admission-v3-20260925.json
```

The initial v1 admission used uncommitted coordinator preflight bytes, SHA256
`bb89244b37b10b212c7f67a06e2e21c4790eadb3390aa837354148cf44b2ccd5`.
Keep that artifact as a historical wiring diagnostic. The committed v2
preflight and B/C rerun at `cd5b7ae` precede the new source registry entries;
their artifact remains tied to that code and registry SHA. The command above
uses v3 with the same B/C causal materials and the updated registry SHA.
The executable checks the full pilot contract, the committed manifest bytes,
the visible development-feedback resource, and the hashes of `uv.lock`, API
profiles, budget, registry, open-S seed and built B/C dev/eval worlds before
creating output. The artifact records that preflight result plus source,
policy, material and configuration hashes. Evaluator-only material is hashed
for identity only.
The old shared R3 snapshot was not loaded or used as B/C feedback; its B/C
scores are not a valid experiment input.

| Group | Scripted baseline calls by session | Synthetic admitted candidate calls by session | Frozen v1 cap | Failure-feedback probe | Recuris delivery |
| --- | ---: | ---: | ---: | --- | --- |
| B | 9 + 11 + 11 = 31 | 11 + 11 + 13 = 35 | 16 per draw | 6 failure strings | card in every session's `act_verify` model prompt and `memory_delivered`, absent from survey prompts |
| C | 9 + 9 = 18 | 11 + 9 = 20 | 16 per draw | 4 failure strings | same checks pass in both sessions |

B sessions 1 and 2 share a project environment; session 3 uses a fresh one.
Both C sessions share one project environment. The B baseline's scripted six
decision checks passed; C's scripted first recovery failed. The failure probe
used each group's current baseline with an empty scripted worker response and
passed only **development** failure detail through `_dev_experience`. The
synthetic candidate changed the `BATCH_DOCS` value, passed `PolicyAuditor` on
both source text and its Python-only directory with a byte match, then ran on
the scripted responder. These are wiring and lower-bound call-demand probes,
not model-researcher updates or capability scores.

The complete development material hashes are:

| Group/session | Instance ID | Full material SHA256 |
| --- | --- | --- |
| B/1 | `research-v5-b1-s1-0001` | `37d1788acbdd95278e02ce434f5266e98b910cea211b0c5d75222cfcbdb4aeb1` |
| B/2 | `research-v5-b1-s2-0001` | `16aed363fb85ec0cf5dcbcc8d2aee10fd6b3cbeb75f7d643a0bc3ae62bdd7c36` |
| B/3 | `research-v5-b1-s3-0001` | `fce2451235489a22f773bec28255b0a3cd7b24d0817e9826cb38fb93b2c88503` |
| C/1 | `research-v5-c1-s1-0001` | `1449e319d2d1480862b104702dc4499b346e4ace1760459eef4f1bb20934b08e` |
| C/2 | `research-v5-c1-s2-0001` | `7a0a0d0aff2082a58f0e299a61ca9d8283f2806f239f6eb3d05ad05687667bfa` |

The script records the evaluation-twin hashes in the private local artifact
without running or exposing them to the researcher. The B/C baseline policy
SHA256 values are respectively
`08f99ed87bfacf5f08b5ca029da211f8406645a91e9fa82230cb348a946e52e0`
and `c6e46093bd8875636f1bf2e5f31e5a946c5df9eadd76942eeca17497db58b26a`.

Gate 1 v1 is **infeasible** for a complete B/C worker run because both
scripted baselines exceed 16 calls. This does not establish the live model's
call demand. A v2 contract should be frozen only after an isolated executor
and a bounded real-model canary, with a stated headroom rule and comparable
researcher opportunity across groups. The Siflow Qwen API profile still says
1,024 max output tokens while the declared effective worker request uses
2,048; reconcile this before a scored run. The live entry fails closed because
the current policy loader executes Python in the host process and no isolated
candidate executor is available.
