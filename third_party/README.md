# Third-party artifacts

External models, datasets, and baseline implementations are intentionally absent from this
repository. `configs/registry.json` records their provenance and access constraints.

Integration modes have precise meanings:

- `direct`: consumed by the benchmark after an explicit, reviewed acquisition.
- `adapter`: optional upstream code that requires an RSIBench adapter and compatibility audit.
- `cite-only`: literature evidence only; no stable licensed artifact is registered.

Review a dry-run acquisition plan with:

```bash
python scripts/registry_download.py qwen3.6-27b ruler-v1
```

The script only prints commands. It has no execute mode. Git sources are pinned to upstream HEADs
resolved on 2026-08-14; Hugging Face sources are pinned to repository revisions. Entries with an
unavailable checksum and gated/manual entries emit explicit warnings. Re-resolve revisions only as
an intentional, reviewed registry update.

Run read-only host checks with:

```bash
python scripts/registry_preflight.py qwen3.6-27b llama-3.3-70b-instruct
```

Preflight queries GPU inventory, free disk space, the presence (not contents) of Hugging Face
credentials, and the workspace GPU-hold wrapper. It does not authenticate, reserve GPUs, create
directories, download files, or execute the displayed wrapper command. Before an actual GPU job,
run it through the suggested `hold.sh wrap ... -- <COMMAND>` form.

The three conservative BF16 vLLM profiles in `configs/serving_profiles.json` can be rendered with:

```bash
python scripts/serve_dry_run.py qwen3.6-27b-262k-bf16-h200x8
```

The emitted command is wrapped for all eight H200s, but is not executed. Prefix caching is disabled
for the reproducibility baseline. Qwen uses language-only mode and the Qwen3 reasoning parser;
remove language-only mode only in a separately validated multimodal profile.

Every artifact remains governed by its upstream license and dataset terms. In particular,
Llama-3.3-70B-Instruct requires Meta license acceptance and an authorized Hugging Face token.
