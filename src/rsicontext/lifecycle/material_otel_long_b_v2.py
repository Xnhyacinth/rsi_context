"""Versioned OTel long B candidate with a verified prior-award dependency.

This opts into the common session-entry prior-verification gate. The R5
candidate and its material hashes remain unchanged. The same pinned source
files and constructed local documents are used in both versions.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from rsicontext.lifecycle.material_otel_long_b import build_otel_long_b_sessions
from rsicontext.lifecycle.spec import LifecycleInstance


def build_otel_long_b_v2_sessions(source_root: Path) -> tuple[LifecycleInstance, LifecycleInstance]:
    """Build the R6 development variant; no benchmark split is registered."""

    first, second = build_otel_long_b_sessions(source_root)
    award = second.stages[2]
    if award.commit_precondition is None:
        raise ValueError("OTel second-session award lacks its commit gate")
    gate = dict(award.commit_precondition)
    gate["prior_verification"] = {
        "check": "dual-emission",
        "plan_field": "plan",
        "allowed_later_plans": {
            "database/dup": ["hold-raw-enable-parameterized"],
        },
    }
    upgraded = replace(award, commit_precondition=gate)
    return (
        replace(first, instance_id="research-v5-otel-long-b-s1-dev-v2-0001"),
        replace(
            second,
            instance_id="research-v5-otel-long-b-s2-dev-v2-0001",
            stages=(*second.stages[:2], upgraded, *second.stages[3:]),
        ),
    )


__all__ = ["build_otel_long_b_v2_sessions"]
