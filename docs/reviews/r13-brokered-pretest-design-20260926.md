# R13 brokered researcher pretest admission, 2026-09-26

Status: **offline admission contract only; `live_ready=false`**. No paid
researcher draw, candidate jail launch, worker exercise, or update-rate result
has been produced by this entrypoint. The legacy `require_isolated_policy_executor`
gate and legacy R3/R2a scripts remain unchanged.

## Why this path is separate

The R12 boundary audit found two independent blockers. This host fails the
unchanged jail trust check because `/usr/bin` and `/usr/lib` have non-root-owned
ancestors. The legacy pilot would load researcher-authored policy in the
evaluator after its guard, so bypassing the guard is inadmissible. This module
adds an admission path that never imports candidate source. It is intentionally
incapable of issuing provider requests or evaluating candidate success.

## Current contract

1. The operator declares a SHA256 pin for a trusted Python 3.12 interpreter.
   `preflight_runtime` stages a **code-owned probe**, launches the unchanged
   jailed child, and completes one broker turn. It records the interpreter,
   probe policy, and jail manifest hashes. Failure stops before any researcher
   draw or output artifact. The CLI only performs this preflight:

   ```bash
   uv run --frozen --no-sync python scripts/r13_brokered_researcher_pretest.py \
     --python-executable /path/to/trusted/python3.12 \
     --expected-python-sha256 <predeclared-64-hex-sha256>
   ```

2. `AdmissionPlan` freezes the planned draw count (1–16), source, visible
   feedback, baseline-policy hashes, model names, and candidate byte cap.
   `run_offline_admission` requires the exact baseline, source, and visible
   feedback bytes and checks each against its declared hash **before** host
   preflight, output creation, or draw. An unchanged candidate is compared
   with the verified baseline bytes. It writes all planned draw rows with the
   denominator before the first offline draw. Timeout, adapter failure,
   invalid bytes, source
   audit failure, unchanged policy, model-echo mismatch, non-stop completion,
   unknown usage, and cap refusal remain in that denominator.
3. The output parent must be owned and private (0700). The admission output,
   candidate directories, and exact `policy/seed.py` snapshot are private;
   source and result files are 0600. The sole candidate file is read back,
   SHA256 checked, and passed to `PolicyAuditor.audit_tree` and `scan_policy`.
   Neither function executes the source. The snapshot records its exact byte
   length and hash, plus only audit codes, not raw source in `result.json`.
   `stage_audited_snapshot` can later recheck the same sole file and declared
   hash before handing its exact bytes to `stage_policy_jail`; it has no
   candidate launch or exercise call.
4. `valid_submitted` counts changed, audited submissions with exact expected
   model echo, stop completion, and internally consistent provider-reported
   input/output/total tokens. `audited_and_exercised` remains zero because no
   candidate exercise exists here. These are offline contract counters, not
   measured researcher rates. The worker model budget and provider usage are
   likewise **unmeasured** in this slice.

## Remaining gates for live researcher updates

- A trusted immutable host must pass the full unskipped policy-jail and broker
  integration suites, including adverse isolation, deadline, and cleanup tests.
- Add a candidate-specific jailed exercise path. Reverify the snapshot bytes,
  stage `policy/seed.py` with `stage_audited_snapshot`, launch it with
  `launch_policy_jail`, and bind `BrokeredPolicyHook` to the actual B/C session
  runner. The parent owns all visible observations, tool caps, worker Siflow
  calls, and `MeteredModelReply` usage provenance. Candidate source must not
  reach host `load_policy` or in-process `PolicyHook`.
- Register strict researcher and worker Siflow profiles and pass fresh
  model-echo, finish-reason, and provider-usage canaries. The old DeepSeek
  researcher alias did not meet exact echo; do not normalize that mismatch.
- Freeze both B/C tasks, visible feedback, baseline policy, call/token budgets,
  model profiles, code and material hashes, and planned attempts before any
  researcher draw. Account for every target and auxiliary worker call and
  report `valid_submitted / all_planned` separately from
  `audited_and_exercised / all_planned` and task success.

Focused offline tests cover refusal ordering, exact private snapshots, all
planned-denominator accounting, invalid source, provider metadata refusal,
byte caps, and failed-preflight cleanup. They cannot substitute for an actual
trusted-host jail exercise.

## Current-host preflight evidence

With the separately measured Python 3.12 executable SHA256
`f7c6210eb40fadcd3c2889dddd24a15fc2c9f926aec5a03bf9da66e12d581526`,
the CLI exited 2 before candidate output or provider dispatch and reported:

```json
{"cause": "non-root-owned path ancestor: /usr/bin", "error_type": "JailSetupError", "live_ready": false, "status": "host-preflight-failed"}
```

This is the first causal refusal from the unchanged jail staging checks on
this host. No credential was loaded, and no Siflow request was made.
