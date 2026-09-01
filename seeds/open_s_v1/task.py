"""Fixed initial task text for the open-S harness track. Not a hashed secret."""

TRACK = "open-s-harness-v1"
TASK = (
    "Search across packing MODES, not just passage rankers. H0 is source-order "
    "full-as-fits under the reader-window envelope. Legal modes include full, "
    "truncate, rag/retrieve, logical parallel map-merge, select-compress "
    "(smaller packs), and hybrids. Compare token cost against visible score. "
    "Do not call the reader, use the network, invent unbound summaries, or "
    "answer the questions. This track is separate from restricted PolicySpecV1 A2."
)
CONSTRAINTS = (
    "Python files only under policy/. One target-model call per item. Each "
    "scored turn must change the policy tree and should change MODE relative "
    "to a lexical-only parent. Invalid submissions consume a slot. Beat H0 "
    "and a matched control before claiming researcher advantage."
)
