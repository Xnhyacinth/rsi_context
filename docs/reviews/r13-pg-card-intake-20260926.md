# R13 PostgreSQL task-card intake, 2026-09-26

Status: **two constructed development cards, one rejected proposal; zero newly qualified tasks**. These are three different project decisions within the *same PostgreSQL parent lineage*. The 16.0 and 17.0 versions are matched source variants, not independent projects. No model or live PostgreSQL server was run.

## Source identity and decisive spans

The detached, clean checkouts are `postgresql-rel-16-0@c372fbbd8e911f2412b80a8c39d7079366565d67` and `postgresql-rel-17-0@d7ec59a63d745ba74fba0e280bbf85dc6d1caa3e`. Their `doc/src/sgml/ref/create_subscription.sgml` full-file SHA-256 values are `8f306cfd871d45b829bde1419e92bbc7cd58d28e068a4de823ee9208745d745d` and `935c1a67d7c013410012b753ca81d75e84ed5ce2f622b195601ce1e688e97340`, respectively. The builder checks these and the pinned `COPYRIGHT` files through the existing source-contrast loader. The source manifest remains `configs/r9_postgresql16_source_manifest_v1.json` / `configs/r7_postgresql_source_manifest_v1.json`; no source revision or registry entry changed.

The span digest below hashes the exact bytes beginning at the opening `<varlistentry>` (or `<para>` for the note) and ending at its closing tag, including line breaks. Byte offsets are half-open. IDs changed between PostgreSQL 16 and 17; the relevant rules did not change.

| Rule | 16.0 line / byte range / SHA-256 | 17.0 line / byte range / SHA-256 |
| --- | --- | --- |
| `connect` | 112–137 / 3698–4987 / `1266ee9c19eda3fb0da9cebfbc41095a14db7c316a51f7c57dcfb8f9157d55a0` | 112–138 / 3722–5061 / `9bb8279eddf8bd9c819ad6dd07886a2ec72de3b6e4e6172d42abe87d14f0b8f1` |
| `binary` | 195–230 / 7182–9122 / `6a60456fd5f78d2506a49256a2bf5563624d6526b62ec4a9edd2bd4368d1f236` | 211–246 / 8192–10139 / `4d1c2f8e221d50fe9f244345c35b8725440e3f3cbe06d788b69c787868cb7ebf` |
| `origin` | 383–401 / 15964–16957 / `4854db46bb1a8c00a10ef78141a8d8cc8eabe6143884188e8606379c658c7765` | 400–418 / 17128–18128 / `68b549734f013a5d591f5eddf582f665e05b224b0386f5500f16cdeedf6caa3a` |
| `origin` and initial-copy note | 482–492 / 20638–21306 / `d8e6e0d77f2334b3633efc93f33d8fc8afcf1fe0007575beafe6668b752a1f10` | 511–521 / 22344–23012 / `d8e6e0d77f2334b3633efc93f33d8fc8afcf1fe0007575beafe6668b752a1f10` |

## Adjudication

| Card | Same constructed request in both revisions | Source rule and legal action | Intake decision |
| --- | --- | --- | --- |
| `connect-offline` | Publisher inaccessible during setup; proposed `connect=false, create_slot=true, enabled=true, copy_data=true` with immediate copy. Other prerequisites hold and later manual steps are available. | Both SGML files say `connect=false` forces the latter three flags false, cannot combine them with true, and subscribes no tables until later slot creation, enablement, and refresh. The only allowed action among `launch-with-copy` and `stage-disconnected` is `stage-disconnected`. | Constructed development card. Same answer in 16/17; no version contrast. |
| `binary-initial-copy` | Initial copy required; a publisher type has binary send but subscriber lacks binary receive; compatible text input/output and other prerequisites are stipulated. | Both SGML files say initial binary synchronization needs send **and** receive for every type and cross-version transfer fails when subscriber receive is absent. Among `use-binary-copy` and `use-text-copy`, only `use-text-copy` is legal under the stated assumptions. | Constructed development card. Same answer in 16/17; a source-free model may guess the default `binary=false`. |
| `origin=none` plus `copy_data=true` | Original proposal did not specify which publisher rows came from upstream or what the project may retain. | Both SGML files say copied rows lose true-origin knowledge; a warning marks a *potential* issue and the user must check whether origins are acceptable. The source offers a query to identify potentially affected tables, not a universal accept/reject outcome. | **Reject as a binary action card.** A legal end-to-end action depends on data provenance and project acceptance criteria absent from the proposed request. No private oracle is invented from a warning. |

For each admitted card, session 1 exposes the same full pinned SGML and notice under a source identity check, then requires an environment-issued source-review receipt and final record. A reset separates session 2, which presents the constructed request and requires a decision-review receipt before finalizing `task_decision`. The private legal plan is an evaluator precondition; the review oracle approves **both** proposed plans, so a receipt does not reveal correctness. The card builder keeps every non-source `StageView` field identical across 16/17. The source, request, receipt, carry, and project records remain different kinds of evidence; no SQL command is executed.

The same offline test policy for both cards reads the SGML rules in session 1 and carries rule flags over the reset. It sees the card request only in session 2 and then chooses a plan. In both revisions it completes both sessions with the legal plan. Replacing source documents with withheld markers preserves the project request and receipt path but makes session 2 fail. This establishes wiring of the constructed oracle and action chain, **not** model difficulty or a unique natural-language causal attribution. Because both source versions warrant the same action, a fixed source-free guess can pass both; these cards contribute no opposite-action pair to the planned ≥20% disagreement diagnostic. Their source-aware test policy and oracle are inspected development material and cannot become a sealed gate.

Next intake work must review the project request and legal action independently, test a question-general fixed model policy, run a genuinely model-invoked source-free arm, and measure complete-project outcomes before admitting either card to the 16-case difficulty panel. The original failover card remains the only PostgreSQL decision here with an observed source-version action flip. If opposite-action pairs are required throughout, find additional pinned parent projects rather than counting these variants twice.

Focused reproduction from the project root with the existing local environment:

```sh
RSICONTEXT_POSTGRESQL16_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/postgresql-rel-16-0 \
RSICONTEXT_POSTGRESQL_SOURCE_ROOT=/volume/pt-dev/qjiu/rsi_context_external/data/postgresql-rel-17-0 \
uv run --frozen --no-sync pytest -q tests/test_postgresql_task_cards.py
uv run --frozen --no-sync ruff check src/rsicontext/lifecycle/material_postgresql_task_cards.py tests/test_postgresql_task_cards.py
uv run --frozen --no-sync mypy --strict src/rsicontext/lifecycle/material_postgresql_task_cards.py tests/test_postgresql_task_cards.py
uv run --frozen --no-sync bandit -q src/rsicontext/lifecycle/material_postgresql_task_cards.py
```
