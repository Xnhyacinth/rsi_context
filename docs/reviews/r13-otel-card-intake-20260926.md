# R13 OpenTelemetry database task-card intake, 2026-09-26

Status: **one new source-adjudicated development card, two deferred proposals;
no reader or researcher qualification**. This intake began from clean
`main@add0a6387d374d78eeb840f552189e88cc693cb6` with `uv.lock` SHA256
`5b24847780908a3481e8b6757480531c165ff87517bc1d48acf250baa6cc9352`
and registry SHA256
`c071cbfc5c33f69b01abb8b0c58033590711482adbad66bb0c261bc5ef6b67e2`.
The source checkouts were clean and detached at the registered 1.24
`cafda7127683b7f667e27cdbd3220510b6f998c9` and 1.43
`89aae438b3b3b0a8dd33003c9d70592baf7dbd0d` revisions. The complete
selected source file hashes are `49a05d5eec2357782876527574b2a544163f4ebf36d193456c77c07a8b6dffa6`
and `1f94aa548e00736bcf7e580318f868eeac36acfdb3e1cb9919da7e02f90e4c91`.

## Intake decision

| Candidate | Pinned source evidence (inclusive lines; SHA256 of exact LF-terminated bytes) | Decision |
| --- | --- | --- |
| DBMS system key | 1.24 `docs/database/database-spans.md:68` `99e1986e9cd0d98faf560eaafc5992f0e7343e4420ddf43e0d5fb531824087a3`; 1.43 `docs/db/database-spans.md:116` `22e5b0916dbaa212cc0298745320c20f9fa1090d8ff7ecf91061fa231102149c` | Admit one **development** card. Both say Required. For a new PostgreSQL client talking to PostgreSQL, product identity agrees; the matching legal attribute keys are `db.system` and `db.system.name`. |
| Operation-name key | 1.24 lines 191–197 `dfb1ab0e8dac6246f3721fb8d77738546ecf822ebb006e29e3a4b912e35655bb`; 1.43 line 119 `69c6ff4b97c90e224b3ca727ee62034e2c1eb7d932a578bb4fc6834501570ef5`, lines 151–156 `54771ffbf67e6f2634804daa6c7a55a0576d90dd6c8a02a97574430edbaad2e1` | Defer. Old Required condition depends on `db.statement` being inapplicable; new condition depends on a single readily available operation. No matched, required action has been frozen. |
| Database namespace/name key | 1.24 lines 191–195 `5034dd3f804a6f61e52d8b71af8251afa43e3ab189080c47e5d78fe790c2e776`; 1.43 line 118 `c59604b555370cc89ddf3a879af00391d9ab0c26c94cc3be62e206520d2b`, lines 147–149 `c9b492cba6bda4b09042d70bf2cfed8797ecab2447de1ef95ff01ef1f15840b5` | Defer. Old `db.name` chooses a database-name layer; new `db.namespace` may join multiple components. A same-target request and oracle require further adjudication. |

The DBMS card reuses the pinned full-source and license presentation, two-session
project state, review receipt and commit chain from the R10 OTel source-contrast
world. The constructed request and private oracle are new. The request names
the DBMS product decision without showing either candidate key or the source
revision; both revisions use the same request bytes. Both get a review receipt
for either key, so a receipt cannot reveal the private legal answer. The
evaluator accepts only the key prescribed by its pinned source revision after
the first session's verified review is finalized. The project asks for new
instrumentation to avoid existing-instrumentation stability and dual-emission
rules altering the answer.

The constructed request SHA256 is
`3c3d74b6ae87eda893283daf08bcc8d940a5605bfc1bc928274851c17306454d`.
Canonical first/second session SHA256s are, respectively,
`ccc4a6edd87cb24c767552b902dd33fea4c0f2a9dfd908304504f44d1ba56c88` /
`bbc984440a74bd572efc7b5f9a9804b8f2bc29c5570e520a3266db14e679bbd7`
for 1.24 and
`0216e4c486c671de19f8e2ad0708c76f7d4c5b1dbf41576d21c6c1c5e76f3d1c` /
`a4ba891aeaf8d8addcd292cb7e6f6e7e372c8cb24b06bb58f5b406419598edf5`
for 1.43. Regenerate the machine-readable source-span and material ledger:

```bash
uv run --frozen --no-sync python scripts/r13_otel_card_intake.py \
  --otel124-root /volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.24.0 \
  --otel143-root /volume/pt-dev/qjiu/rsi_context_external/data/otel-semconv-v1.43.0
```

The ledger validates selected-file and nominated-span hashes. Checkout HEAD
and cleanliness must be verified separately with `git status --porcelain` and
`git rev-parse HEAD`; the existing R10 source-contrast tests check them against
the manifest and registry.

## Offline verification and limit

Seven focused tests passed with both pinned source roots. A deterministic
source-reading test double completed both sessions and selected opposite keys;
fixed source-free choices failed one revision, swapped source changed the
action and failed the original oracle, and withheld source, dropped carry or
missing prior commit prevented completion. These tests check the world and
oracle behavior. **They are not model difficulty or causal-dependency
measurements.** This card has no new Siflow run or token usage, no frozen
question-general reader policy, and no second model family. It is one decision
inside the same OTel parent lineage, not an additional independent parent.
Qualified independent-parent count remains zero. Gate 2 and researcher
admission remain closed.

The older Required row sits under connection-level attributes, while the newer
row sits in the span definition. An independent semantic adjudicator must
confirm that these scopes support the same requested client-span decision
before the pair is admitted to the experimental panel.

Before using this card in a paid panel, freeze a question-general reader
policy, exact model/profile/template and token geometry, source-free
model-invoked arm, target-rule intervention that controls residual source
cues, and an equal-budget second reader. The existing R12 query-text screen
cannot stand in for those checks.
