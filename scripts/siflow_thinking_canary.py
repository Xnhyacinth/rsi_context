#!/usr/bin/env python3
"""Two fixed, low-output Siflow canaries for Qwen thinking-mode forwarding."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from r2a_compare import READER_ENDPOINT, READER_MODEL, _reported_usage

OUTPUT = Path("artifacts/rsi-core-v1/siflow-thinking-canary-v1-20260924.json")
PROMPT = "Write only a two-line Python function: def increment(x): then return x + 1."
MAX_OUTPUT_TOKENS = 256


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite canary: {OUTPUT}")
    if not os.environ.get("SIFLOW_API_KEY"):
        raise RuntimeError("SIFLOW_API_KEY is required")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "status": "running",
        "model": READER_MODEL,
        "endpoint_sha256": _sha256(READER_ENDPOINT),
        "prompt_sha256": _sha256(PROMPT),
        "max_output_tokens_per_request": MAX_OUTPUT_TOKENS,
        "planned_requests": 2,
        "temperature": 0.0,
        "seed": 42,
        "results": [],
    }
    OUTPUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    results: list[dict[str, object]] = []
    payload["results"] = results
    for enable_thinking in (None, False):
        body: dict[str, object] = {
            "model": READER_MODEL,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.0,
            "seed": 42,
            "stream": False,
        }
        if enable_thinking is False:
            body["chat_template_kwargs"] = {"enable_thinking": False}
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
                "enable_thinking": enable_thinking,
                "outcome": "ok",
                "model_echo": raw.get("model"),
                "finish_reason": choice.get("finish_reason"),
                "content_chars": len(content),
                "content_sha256": _sha256(content),
                "reasoning_chars": len(reasoning),
                **_reported_usage(raw.get("usage")),
                "wall_seconds": round(time.monotonic() - started, 3),
            }
        except Exception as exc:
            result = {
                "enable_thinking": enable_thinking,
                "outcome": "request_error",
                "error_type": type(exc).__name__,
                "model_echo": None,
                "finish_reason": None,
                "content_chars": None,
                "reasoning_chars": None,
                **_reported_usage(None),
                "wall_seconds": round(time.monotonic() - started, 3),
            }
        results.append(result)
        OUTPUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    payload["status"] = "complete"
    OUTPUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(OUTPUT), "results": results}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
