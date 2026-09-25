# B/C Gate 1 offline admission (2026-09-25)

This admission uses the tracked B/C development builders and scripted local
responses. It makes **zero** Siflow or GPU calls, makes **zero** researcher
draws, and does not run the evaluation worlds. The planned denominator remains
two researcher draws per group for a future isolated, versioned live pilot;
there is no valid-update-rate estimate here. Run with:

```bash
uv run --no-sync python scripts/r3_bc_researcher_pilot.py \
  --preflight configs/r3_gate1_offline_preflight_v1.json \
  --output artifacts/rsi-core-v1/r3-bc-gate1-offline-admission-v1-20260925.json
```

The initial admission used the identical preflight bytes from the coordinator
worktree, SHA256 `bb89244b37b10b212c7f67a06e2e21c4790eadb3390aa837354148cf44b2ccd5`.
The executable checks all declared model IDs, thinking controls, request caps,
seed, temperature and evaluation-selection rule against a pinned pilot contract,
and checks the hashes of `uv.lock`, API profiles, budget, registry and open-S
seed. The artifact contains the source, policy, full dev/eval material and
configuration hashes. Evaluator-only material is hashed for identity only.
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
| B/2 | `research-v5-b1-s2-0001` | `8e3f7e244683cdc720f18e2827c9a27b748b9a49a42e964cdf8615ac8009a595` |
| B/3 | `research-v5-b1-s3-0001` | `fce2451235489a22f773bec28255b0a3cd7b24d0817e9826cb38fb93b2c88503` |
| C/1 | `research-v5-c1-s1-0001` | `1449e319d2d1480862b104702dc4499b346e4ace1760459eef4f1bb20934b08e` |
| C/2 | `research-v5-c1-s2-0001` | `9af6bfb7adc849a28084a202267fa3de31163a17ea0a5fad1aa87f4c9f67858c` |

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
