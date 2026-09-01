"""Fixed initial task text for the open-S harness track. Not a hashed secret."""

TRACK = "open-s-harness-v1"
TASK = (
    "Improve the isolated folder strategy system S so the frozen reader answers "
    "better on long documents under the reader-window pack envelope. Legal "
    "strategies include full-as-fits long context, retrieve/RAG, truncation, "
    "reorder, and hybrid pack; you may not invent unbound summary text. Do not "
    "call the reader, use the network, or answer the questions yourself. This "
    "track is separate from restricted PolicySpecV1 A2."
)
CONSTRAINTS = (
    "Python files only under policy/. One target-model call per item. Each "
    "scored turn must change the policy tree. Invalid submissions consume a "
    "slot. Beat H0 and a matched control before claiming researcher advantage. "
    "The envelope is the frozen reader window, not an 8K cap."
)
