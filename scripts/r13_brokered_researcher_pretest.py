"""R13 prospective researcher pretest: immutable host preflight only.

No researcher or worker API adapter is installed. A successful preflight is
one necessary condition, never authorization to draw or exercise candidates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rsicontext.experiment.brokered_researcher_pretest import preflight_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-executable", required=True, type=Path)
    parser.add_argument("--expected-python-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        evidence = preflight_runtime(
            python_executable=args.python_executable,
            expected_python_sha256=args.expected_python_sha256,
        )
    except Exception as exc:
        # Error type and cause are useful admission evidence; no secrets enter
        # this CLI, and no provider or candidate code has been reached.
        print(
            json.dumps(
                {
                    "live_ready": False,
                    "status": "host-preflight-failed",
                    "error_type": type(exc).__name__,
                    "cause": str(exc),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"live_ready": False, "status": "host-preflight-passed", **evidence}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
