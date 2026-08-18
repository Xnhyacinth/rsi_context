# A2 environment lock — 2026-08-18 (revised)

Formal `launch_a2_pilot` still refuses on this host (qualification-only plan,
no physical isolation, execution not enabled). Visible qualification analog is
the honest A2-shaped experiment here.

PI 2026-08-18: gold-only ≥0.85 is a diagnostic, not an A2 launch kill. Homemade
32K and RULER qa_2 needle-in-essay are not the A2 task.

## Frozen reader (locked)

| Field         | Value                                                  |
| ------------- | ------------------------------------------------------ |
| Model         | Qwen3.6-27B                                            |
| Path          | `models/qwen3.6-27b`                                   |
| Revision      | `1b559cf7215ebe67ff10758e14f6293ba883223b`             |
| Serve name    | `Qwen/Qwen3.6-27B`                                     |
| vLLM          | 0.25.1                                                 |
| Profile       | `qwen3.6-27b-128k-bf16-h200x8`                         |
| TP            | 8                                                      |
| max_model_len | 131072                                                 |
| dtype         | BF16                                                   |
| prefix cache  | off                                                    |
| thinking      | off                                                    |
| temperature   | 0                                                      |
| seed          | 42                                                     |
| port          | 8017 (ephemeral serve; restore GPU hold after scoring) |

## Fitness cell

Primary: unique HELMET PopQA k1000→8K with planted gold rank ≥200 (Wikipedia
passages, pack 8192). Offline n=16: median source 116506 Qwen tokens, binding
1.0, head 0.0, lexical/hand-hybrid 0.625, disagreement 0.625. Gold from
`has_answer`. Do not use the raw `dep6` prefix; those lines clone each question
at ranks 0/200/400/600/800/999.

Abandoned as A2 task: homemade 32K; RULER qa_2/qa_1; HELMET NQ/Trivia k1000
(head 1.0); HELMET Hotpot k1000 (lexical 1.0).

Second profile is not yet locked. Do not shuffle ranked `ctxs`.

## Scorer

Visible analog uses `extractive_span_match`. Not an official HELMET score.

## Isolation

This host cannot attest sealed policy-worker isolation. Visible qualification
only. Do not set `isolation_formal=true`.
