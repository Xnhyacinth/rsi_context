# R19 Gemma 4 tokenizer intake plan

**Pre-acquisition review.** At this point only registry and read-only plans
existed; the later [acquisition audit](r19-gemma-tokenizer-intake-audit-20260927.md)
records the six-file snapshot. This entry supports an offline tokenizer and
chat-template feasibility check for a possible reader profile. It does not
register local weights, establish serving compatibility, or qualify a
benchmark parent.

The official [pinned model repository](https://huggingface.co/google/gemma-4-31B-it/tree/842da3794eaa0b77d5f08bae87a17459d91ff475)
and Hugging Face revision API returned repository SHA
`842da3794eaa0b77d5f08bae87a17459d91ff475`, `gated=false`,
`private=false`, and model-card license `apache-2.0` on 2026-09-27. The
`gemma-4-31b-it-tokenizer-intake` model entry records that exact revision.
Registry SHA-256: `7ac3a92dcbf9128c2b39ef16978bb9d08854612a85126b98165f62ecd8a9c1a0`.

The read-only [registry plan](/volume/pt-dev/qjiu/rsi_context_external/r19-preflight/gemma-registry-plan.json)
has SHA-256 `e797440a7e955c6423b047a91e971fb34ce508e240b3640a0c982ef8142ff0aa`.
It reports `dry_run=true`, one unknown-size artifact and no warnings. Its
generic `hf download` command requests the **whole 62.6 GB model**. That
command and its whole-repository verification command are unsuitable for this
intake and must not be executed.

The separate [pinned file metadata](/volume/pt-dev/qjiu/rsi_context_external/r19-preflight/gemma-selected-hf-metadata.json)
has SHA-256 `34b5271ea52be8c932059c4062acc503c0443c122f473f9a2f690832341a04a0`.
The six selected files sum to 32,197,909 bytes:

| File | Reported bytes | Git blob or LFS SHA-256 |
| --- | ---: | --- |
| `chat_template.jinja` | 18,683 | `4741bf6e4132ba23a5537f9d6e74e9a6d613d7cd` |
| `config.json` | 4,621 | `5f291aa9973fbb38982f9bade924989edc7b895d` |
| `generation_config.json` | 208 | `e605bb4523b1462ea9d9a3810b9e3ecf7ab7b1f6` |
| `processor_config.json` | 1,689 | `5465974d23e1eca2c46c2809b26c997946ce0d90` |
| `tokenizer.json` | 32,169,626 | LFS `cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f` |
| `tokenizer_config.json` | 3,082 | `6068e357379d36f823c377e30efb101fa2c67fe4` |

After plan review, acquire those six named files only at the registered SHA
into an external snapshot. Verify exact file set, byte counts, each regular
file's Git blob ID or LFS SHA-256, final local SHA-256, and the absence of
weights. Load `AutoTokenizer` and `AutoProcessor` with `local_files_only=True`
under a pinned runtime; report incompatibility explicitly if the current
runtime cannot load this snapshot. No provider or GPU call belongs to this
intake. Freeze reader launches only after integration records the registry,
snapshot and runtime identities together.
