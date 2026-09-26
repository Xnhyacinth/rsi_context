# R16 researcher jail host audit

**Decision: no live researcher draws on this host.** This is a host preflight
refusal before candidate execution or provider dispatch, not a measured zero
effective-update rate. The R13 brokered pretest currently has no live
researcher/worker adapter and prints `live_ready=false` even after a passing
host probe.

Current filesystem ownership is decisive:

| Path | UID:GID | Mode | Role |
| --- | --- | --- | --- |
| `/usr` | `0:0` | `0755` | Parent |
| `/usr/bin` | `1000:1000` | `0755` | Fixed `setpriv`, `unshare`, `ldd` launch paths |
| `/usr/lib` | `1000:1000` | `0755` | `libseccomp` path ancestor |

The pinned CPython executable
`/volume/pt-dev/qjiu/.local/share/uv/python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12`
has SHA256 `f7c6210eb40fadcd3c2889dddd24a15fc2c9f926aec5a03bf9da66e12d581526`.
The host probe was rerun from clean `work/r16-integration`:

```bash
uv run --frozen --no-sync python scripts/r13_brokered_researcher_pretest.py \
  --python-executable /volume/pt-dev/qjiu/.local/share/uv/python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12 \
  --expected-python-sha256 f7c6210eb40fadcd3c2889dddd24a15fc2c9f926aec5a03bf9da66e12d581526
```

It exited 2 with `JailSetupError: non-root-owned path ancestor: /usr/bin`
and `live_ready=false`. Focused `test_policy_jail.py` and
`test_jailed_broker_integration.py` gave **4 passed, 15 skipped**; all 15
launch/adverse cases skipped at the same trust gate. The independent audit
also checked the wider jail/broker tests (34 passed, 15 skipped). This is
consistent with the full R15 suite's same 15 jail skips.

The trust check in `security/policy_jail.py` verifies root-owned,
non-writable ancestors of the fixed launcher/library material before staging
candidate policy code; launch rechecks the hashes. The old
`scripts/r3_researcher_pilot.py` has a separate unconditional isolated-policy
executor guard. Removing either guard would move untrusted candidate code
toward the evaluator process and would invalidate the intended boundary.
The audit found no installed trusted root-owned container runtime or daemon
socket that currently supplies the missing launcher/library path, and no
confirmed exploitable bypass of the existing check.

**Next admission condition:** use a trusted host or separately pinned,
root-owned and non-writable launcher/interpreter/library image; rerun the
unskipped jail, adversarial-policy and broker integration tests there. Then
freeze the researcher model/endpoint, task materials, attempt denominator and
target/auxiliary token budgets before a paid pretest. Do not change ownership
of the current `/usr` tree or relax its trust check as a shortcut.
