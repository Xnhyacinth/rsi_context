# R14 offline brokered B/C candidate exercise, 2026-09-26

Status: **interface and offline transport tests only; `live_ready=false`**.
No researcher draw, Siflow request, GPU run, or candidate execution occurred on
this host. The legacy `require_isolated_policy_executor` guard remains intact.

`exercise_candidate_sequence` accepts an existing private candidate snapshot,
its declared SHA256, frozen evaluator-owned `research-v5` sessions and project
states, a fresh bounded tool budget, a pinned Python executable, and an
offline target responder. The evaluator must also supply a task-specific
`decision_rules` callback; omission or a non-callable value is rejected before
staging. This prevents the sequence runner's legacy award/calibration default
from assigning unrelated B/C decisions. It recomputes a hash over the complete task objects,
including evaluator-only fields, and records an initial-environment hash over
records, receipts, revisions, and whether sessions share the same project.
It stages one independently audited jail per session **before launching any
child**. `stage_audited_snapshot` rereads and
reaudits the sole `policy/seed.py` file; `stage_policy_jail` checks the host
trust boundary and copies immutable runtime material. The launcher then creates
one jailed child and one `BrokeredPolicyHook` per session. The existing
`run_session_sequence` binds the broker to the actual evaluator environment,
shared budget, and revealed-document registry and closes it after each session.
Candidate source never reaches host `load_policy` or in-process `PolicyHook`.

The return value keeps the evaluator-only `SequenceRecord` separate from
admission's `valid_submitted / all_planned` rate. It records task decisions,
session checks, every dispatched target call, provider usage provenance,
provider-token totals only when **all** target usage is reported, and the
shared tool ledger. A broker or runner exception returns `status=failed` and
the calls observed so far; an unknown usage source returns
`status=usage-unverified`. These states must remain failures in the registered
researcher pretest denominator. `live_ready` is always false in this slice.
The trusted responder wrapper strips exception messages and failed-response
bodies/causes before the broker sends a receipt to the candidate; unknown
usage remains explicitly unknown. A completed exercise status describes
transport/accounting completion, while task success stays in the evaluator's
`SequenceRecord`.

Delegation is explicitly disabled: the broker installs no `delegate_runner`.
Attempted delegate requests receive a refusal and are counted in
`auxiliary_attempts_refused`; `auxiliary_calls` is therefore exactly zero. This
avoids treating the existing string-only delegate interface as a metered model
channel. A future live adapter must add provider-grounded auxiliary usage and
strict target-model echo checks before allowing that channel.

The caller owns staged jail roots and their cleanup. A trusted host must run
the unchanged policy-jail and broker integration suites without trust skips,
then execute source-pinned B/C candidate and adverse isolation cases. On this
host the fixed `/usr/bin` and `/usr/lib` ancestors have UID 1000; the real
staging test confirms refusal before launch or responder dispatch. Offline
thread peers in the other tests exercise the typed broker and sequence runner,
but are **not** evidence that the actual jail can execute here.

Focused verification:

```bash
uv run --frozen --no-sync pytest -q tests/test_brokered_researcher_exercise.py tests/test_brokered_sequence.py tests/test_brokered_researcher_pretest.py
uv run --frozen --no-sync ruff check src/rsicontext/experiment/brokered_researcher_exercise.py tests/test_brokered_researcher_exercise.py
uv run --frozen --no-sync mypy --strict src/rsicontext/experiment/brokered_researcher_exercise.py tests/test_brokered_researcher_exercise.py
uv run --frozen --no-sync bandit -q src/rsicontext/experiment/brokered_researcher_exercise.py
```

These focused tests plus the existing broker-sequence and R13 admission tests
passed **36/36**; touched-file Ruff, strict mypy, and Bandit reported no issues.
The repository-wide merge gate remains the integration owner's responsibility.
