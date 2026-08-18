from __future__ import annotations

from rsicontext.baselines.hand_hybrid import HAND_HYBRID_NAME, HAND_HYBRID_SPEC_V1
from rsicontext.policy import CANONICAL_POLICY_SPECS_V1


def test_hand_hybrid_is_a_named_canonical_v1_spec() -> None:
    assert HAND_HYBRID_NAME == "hand-hybrid"
    assert HAND_HYBRID_SPEC_V1 in CANONICAL_POLICY_SPECS_V1
    assert HAND_HYBRID_SPEC_V1.canonical_key.startswith("v1:query_bm25:2:rank")
