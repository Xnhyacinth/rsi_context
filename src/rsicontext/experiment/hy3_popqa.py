"""Pinned PopQA and tokenizer inputs shared by hy3 qualification CLIs."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import cast

from rsicontext.datasets import EncodedWindowTokenizer
from rsicontext.eval import EvaluationItem
from rsicontext.policy import ContextPolicy, TruncationPolicy

POPQA_SOURCE = Path("data/helmet-data/data/kilt/popqa_test_1000_k1000_dep6.jsonl")
POPQA_SOURCE_ID = "princeton-nlp/HELMET/popqa_test_1000_k1000_dep6.jsonl"
POPQA_SOURCE_REVISION = "bc560a6b8165c696ad4bc3d1612c64b5794ba328"
POPQA_SOURCE_SHA256 = "ca74dec945e9c837be4d7739da2194fbb09b6f8d5affa9823d979936c63fc89f"
QWEN_TOKENIZER = Path("models/qwen3.6-27b")
QWEN_TOKENIZER_REVISION = "Qwen/Qwen3.6-27B@1b559cf7215ebe67ff10758e14f6293ba883223b"
QWEN_TOKENIZER_FILES = (
    ("merges.txt", "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d"),
    ("tokenizer.json", "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42"),
    (
        "tokenizer_config.json",
        "dbfb3c20ce3d5b8370faeecd548e771c1dcc8e4fdcf636797fc24b0d0733fb02",
    ),
    ("vocab.json", "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003"),
)
QWEN_TOKENIZER_CLASS = "transformers.models.qwen2.tokenization_qwen2.Qwen2Tokenizer"


def head_policy() -> ContextPolicy:
    """Return a fresh whole-chunk head truncation policy."""

    return TruncationPolicy("head")


def load_qwen_tokenizer(path: Path) -> EncodedWindowTokenizer:
    """Load only the pinned local tokenizer implementation and files."""

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(path),
        local_files_only=True,  # nosec B615
    )
    tokenizer_class = f"{type(tokenizer).__module__}.{type(tokenizer).__qualname__}"
    if tokenizer_class != QWEN_TOKENIZER_CLASS:
        raise RuntimeError(f"unexpected canonical tokenizer class: {tokenizer_class}")
    init_kwargs = tokenizer.init_kwargs
    for field, filename in (("vocab_file", "vocab.json"), ("merges_file", "merges.txt")):
        observed = init_kwargs.get(field)
        if not isinstance(observed, str) or Path(observed).resolve() != (path / filename).resolve():
            raise RuntimeError(f"canonical tokenizer did not bind {filename}")
    if init_kwargs.get("tokenizer_file") is not None:
        raise RuntimeError("canonical tokenizer unexpectedly uses tokenizer_file")
    return cast(EncodedWindowTokenizer, tokenizer)


def source_token_summary(items: tuple[EvaluationItem, ...]) -> dict[str, float | int]:
    """Summarize actual source tokens without retaining item-level values."""

    totals = tuple(sum(chunk.token_count for chunk in item.artifact.chunks) for item in items)
    return {
        "maximum": max(totals),
        "median": statistics.median(totals),
        "minimum": min(totals),
    }
