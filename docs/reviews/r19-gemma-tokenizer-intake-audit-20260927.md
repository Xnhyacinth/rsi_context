# R19 Gemma 4 tokenizer snapshot audit

**Status: six-file tokenizer snapshot acquired and verified; text tokenizer
load passes, processor load is incomplete.** This is metadata intake for
offline prompt geometry, not a model-weight download or reader result.

The preceding [plan](r19-gemma-tokenizer-intake-plan-20260927.md) pinned the
official `google/gemma-4-31B-it` repository at
`842da3794eaa0b77d5f08bae87a17459d91ff475`. The parent reviewed its
registry dry-run before acquisition. Acquisition selected exactly these six
filenames by `hf download` positional file arguments at that SHA:

```bash
hf download google/gemma-4-31B-it \
  chat_template.jinja config.json generation_config.json \
  processor_config.json tokenizer.json tokenizer_config.json \
  --revision 842da3794eaa0b77d5f08bae87a17459d91ff475 \
  --local-dir /volume/pt-dev/qjiu/rsi_context_external/models/gemma-4-31b-it-tokenizer-intake
```

The acquired six files were copied into the clean, read-only
[revision-named snapshot](/volume/pt-dev/qjiu/rsi_context_external/models/gemma-4-31b-it-tokenizer-842da3794eaa0b77d5f08bae87a17459d91ff475).
The snapshot directory has mode `555`; its six regular files have mode `444`.
There are no other snapshot entries, symlinks, safetensors or model weights.
The exact file set totals **32,197,909 bytes**.

The [machine-readable audit](/volume/pt-dev/qjiu/rsi_context_external/r19-preflight/gemma-tokenizer-snapshot-audit.json)
has SHA-256 `4f44798feb258d3aaf684171a69384914e052bcec0f55ad5d0e8d1fad69537c5`.
It records each file's name, byte count, local SHA-256, Git blob ID and
registered-source ID. Every regular-file Git blob ID matches the pinned
Hugging Face tree. The 32,169,626-byte `tokenizer.json` matches its pinned LFS
SHA-256 `cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f`.
The project's `verify_tokenizer_snapshot` returns manifest SHA-256
`40b849c70758c1d03765aac8d6388c943b3f3689ef3ef6d105f9936af140a074`.

The pinned [revision metadata](/volume/pt-dev/qjiu/rsi_context_external/r19-preflight/gemma-revision-metadata.json)
has SHA-256 `f5a1f8eae54e13c32beff5bda938fea259833c298cb709c6d7317b1cf89fc805`.
It reports `gated=false`, `private=false` and model-card license
`apache-2.0`. The pinned repository top-level file list contains no
`LICENSE` or `LICENSE.txt`; **the license evidence is model-card metadata**, not
a downloaded standalone license file.

With `transformers==5.15.0`, `tokenizers==0.22.2` and `jinja2==3.1.6`,
`AutoTokenizer.from_pretrained(snapshot, local_files_only=True,
trust_remote_code=False, use_fast=True)` loads as `GemmaTokenizer`.
`apply_chat_template` for one user message and an assistant generation prefix
returns a `BatchEncoding` with **17 `input_ids`**; its mapping length is two
(`input_ids` and `attention_mask`) and is not a token count. The tokenizer
reports vocabulary size 262,144, BOS ID 2 and EOS ID 1.

`AutoProcessor.from_pretrained(..., local_files_only=True)` first failed
because Pillow was absent. An ephemeral retry with the lockfile's
`pillow==12.3.0` then failed because `Gemma4Processor` imports PyTorch, absent
from this lightweight environment. No heavy processor or model dependencies
were installed for this text-tokenizer intake. This snapshot is therefore
verified for **text chat-template geometry only**; processor-backed
multimodal geometry and local model execution remain unverified.

Any reader launch using this candidate must bind the integrated registry SHA,
these six local file SHA-256 values, the manifest digest and the exact
tokenizer runtime before running. The snapshot alone does not establish a
provider endpoint, context length, serving compatibility or benchmark score.
