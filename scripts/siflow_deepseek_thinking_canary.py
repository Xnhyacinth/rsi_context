#!/usr/bin/env python3
"""One fixed Siflow canary for DeepSeek non-thinking parameter forwarding."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from r2a_compare import READER_ENDPOINT, RESEARCHER_MODEL, _reported_usage

OUTPUT = Path("artifacts/rsi-core-v1/siflow-deepseek-thinking-canary-v1-20260924.json")
PROMPT = "Write only a two-line Python function: def increment(x): then return x + 1."
MAX_OUTPUT_TOKENS = 256


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite canary: {OUTPUT}")
    if not os.environ.get("SIFLOW_API_KEY"):
        raise RuntimeError("SIFLOW_API_KEY is required")
    body = {
        "model": RESEARCHER_MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_OUTPUT_TOKENS,
        "thinking": {"type": "disabled"},
        "temperature": 0.0,
        "seed": 42,
        "stream": False,
    }
    artifact: dict[str, object] = {
        "status": "running",
        "model": RESEARCHER_MODEL,
        "endpoint_sha256": hashlib.sha256(READER_ENDPOINT.encode()).hexdigest(),
        "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "thinking": {"type": "disabled"},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "planned_requests": 1,
        "result": None,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(artifact, indent=1) + "\n", encoding="utf-8")
    request = urllib.request.Request(
        READER_ENDPOINT,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['SIFLOW_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        # READER_ENDPOINT is a code-owned HTTPS constant.
        with urllib.request.urlopen(request, timeout=300) as response:  # nosec B310
            raw = json.load(response)
        choice = raw["choices"][0]
        message = choice["message"]
        content = message.get("content") or ""
        reasoning = message.get("reasoning_content") or message.get("reasoning") or ""
        result = {
            "outcome": "ok",
            "model_echo": raw.get("model"),
            "finish_reason": choice.get("finish_reason"),
            "content_chars": len(content),
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "reasoning_chars": len(reasoning),
            **_reported_usage(raw.get("usage")),
            "wall_seconds": round(time.monotonic() - started, 3),
        }
    except Exception as exc:
        result = {
            "outcome": "request_error",
            "error_type": type(exc).__name__,
            "model_echo": None,
            "finish_reason": None,
            **_reported_usage(None),
            "wall_seconds": round(time.monotonic() - started, 3),
        }
    artifact["status"] = "complete"
    artifact["result"] = result
    OUTPUT.write_text(json.dumps(artifact, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(OUTPUT), "result": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
