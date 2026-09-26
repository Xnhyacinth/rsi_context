# R15 fixed-reader controls and B/C budget execution ledger

Status: design and offline implementation in progress. The common starting
point is clean `main@dc76d798bfc49e58d599fc77bca8529a40cd063d` (apart
from the original main checkout's unrelated `logs/`). The registry and
`uv.lock` retain SHA256
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`
and `5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`.

R15 uses one new shared development-only Qwen worker profile. Its request
configuration copies the already exercised R12 Qwen settings exactly;
only the profile ID changes to identify this B/C block. Provider revision
remains unobservable. The researcher model profile is separate and is not
activated by this work.

| Owner | Planned bounded evidence |
| --- | --- |
| PEP worker | Benchmark-owned fixed reader for PEP 621/639 with full-source, identity-only and answer-free source-free arms; exact source/visible material/receipt/usage ledger and complete two-session outcomes |
| KEP worker | Benchmark-owned fixed reader for KEP-753 resource order with full-source and controlled no-rule/no-source arms; exact ordered-rule geometry, complete two-session outcomes and refusal conditions |
| Budget worker | Per-card B/C target/auxiliary call and rendered-token envelope bound to immutable task/profile/policy materials; fail-closed admission, no transfer of the old R4 40-call cap |
| Integration | Independently adjudicate controls, freeze actual prompt hashes and stop rules, run canaries and only then a small paid reader block if all gates pass; review, full checks, main merge and cleanup |

The candidate cards remain inspected development material. These probes
cannot make the PEP or KEP lineage a qualified independent parent by
themselves, and a source-free arm must actually call the worker. No
researcher-authored policy is evaluated. The current host still fails
the unchanged jail trust check; therefore no paid researcher-update pretest
may run here. The local credential loader is the adjacent
`/volume/pt-dev/qjiu/wynckeliao-env/ops/env/local-env.sh`; it provides the
key but not the fixed Siflow endpoint, and neither value is recorded here.

Before any paid task call, freeze the exact case list, question-general
policy, source and intervention hashes, request JSON hashes, final rendered
chat token intervals, per-call output ceiling, global provider-token/call
cap, stop rules and pre/post canary identities. A pre-canary or material/
template mismatch stops the task block. Missing provider usage, wrong model
echo or non-stop completion stays in the attempt denominator and halts later
calls. Full-source solvability is checked before spending on difficulty
controls. Report complete-project action/receipt outcomes and provider
input/output usage by source lineage; do not treat versions, variants, calls
or policy turns as independent parents.
