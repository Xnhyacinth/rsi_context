from rsicontext.policy import Artifact, Budget, DocumentChunk
from rsicontext.policy.baselines import LexicalPolicy, TruncationPolicy


def make_artifact() -> Artifact:
    texts = (
        ("a", "irrelevant opening"),
        ("b", "mars has two moons"),
        ("c", "irrelevant ending"),
    )
    return Artifact(
        document_id="doc",
        chunks=tuple(
            DocumentChunk(
                chunk_id=chunk_id,
                document_id="doc",
                start=index * 20,
                end=index * 20 + len(text),
                text=text,
                token_count=len(text.split()),
            )
            for index, (chunk_id, text) in enumerate(texts)
        ),
    )


def test_truncation_modes_are_deterministic_and_never_overrun_budget() -> None:
    artifact = make_artifact()
    budget = Budget(max_tokens=4)

    assert TruncationPolicy("head").assemble(artifact, "", budget).ordering == ("a",)
    assert TruncationPolicy("tail").assemble(artifact, "", budget).ordering == ("c",)
    assert TruncationPolicy("middle").assemble(artifact, "", budget).ordering == ("b",)
    head_tail = TruncationPolicy("head_tail").assemble(artifact, "", budget)
    assert head_tail.ordering == ("a", "c")
    assert head_tail.token_count <= budget.max_tokens

    assert TruncationPolicy("tail").assemble(artifact, "", Budget(6)).ordering == (
        "b",
        "c",
    )
    assert TruncationPolicy("head_tail").assemble(artifact, "", Budget(8)).ordering == (
        "a",
        "b",
        "c",
    )


def test_lexical_policy_ranks_query_evidence_and_has_stable_ties() -> None:
    artifact = make_artifact()
    policy = LexicalPolicy()

    pack = policy.assemble(artifact, "How many moons does Mars have?", Budget(4))
    assert pack.ordering == ("b",)

    tied = policy.assemble(artifact, "unseen terms", Budget(4))
    assert tied.ordering == ("a", "c")
