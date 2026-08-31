from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from rsicontext.experiment.elastic_envelope import (
    ElasticContextEnvelope,
    ElasticItemRequest,
    ElasticLengthPreference,
    RenderedInputObservation,
    allocate_elastic_batch,
    count_rendered_chat_input,
    preflight_rendered_batch,
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _envelope(*, items: int = 3) -> ElasticContextEnvelope:
    return ElasticContextEnvelope(
        token_axis_sha256="a" * 64,
        max_rendered_input_tokens=20,
        mean_rendered_input_tokens=10,
        items_per_split=items,
        output_reserve_tokens=5,
        endpoint_model_limit=25,
    )


def _request(label: str, overhead: int, desired: int, priority: int) -> ElasticItemRequest:
    return ElasticItemRequest(
        public_input_digest=_digest(label),
        fixed_overhead_tokens=overhead,
        preference=ElasticLengthPreference(desired, priority),
    )


def test_weighted_water_filling_is_order_invariant_and_uses_the_batch_cap() -> None:
    requests = (
        _request("a", 2, 20, 1),
        _request("b", 2, 20, 2),
        _request("c", 2, 6, 1),
    )

    forward = allocate_elastic_batch(requests, _envelope())
    reverse = allocate_elastic_batch(tuple(reversed(requests)), _envelope())

    assert forward == reverse
    assert forward.total_rendered_input_tokens == 30
    assert {
        allocation.public_input_digest: allocation.rendered_input_tokens
        for allocation in forward.allocations
    } == {
        _digest("a"): 9,
        _digest("b"): 15,
        _digest("c"): 6,
    }


def test_water_filling_caps_desire_and_breaks_exact_ties_by_public_digest() -> None:
    low = "0" * 64
    high = "f" * 64
    envelope = ElasticContextEnvelope(
        token_axis_sha256="b" * 64,
        max_rendered_input_tokens=10,
        mean_rendered_input_tokens=6,
        items_per_split=2,
        output_reserve_tokens=2,
        endpoint_model_limit=12,
    )
    requests = (
        ElasticItemRequest(high, 2, ElasticLengthPreference(100, 1)),
        ElasticItemRequest(low, 1, ElasticLengthPreference(100, 1)),
    )

    result = allocate_elastic_batch(requests, envelope)

    assert tuple(item.public_input_digest for item in result.allocations) == (low, high)
    assert tuple(item.payload_tokens for item in result.allocations) == (5, 4)
    assert tuple(item.rendered_input_tokens for item in result.allocations) == (6, 6)


def test_allocator_rejects_duplicate_items_and_an_infeasible_overhead_floor() -> None:
    duplicate = _request("same", 6, 10, 1)

    with pytest.raises(ValueError, match="unique"):
        allocate_elastic_batch((duplicate, duplicate), _envelope(items=2))
    with pytest.raises(ValueError, match="overhead"):
        allocate_elastic_batch(
            (
                _request("a", 11, 11, 1),
                _request("b", 11, 11, 1),
            ),
            _envelope(items=2),
        )
    with pytest.raises(ValueError, match="per-item maximum"):
        allocate_elastic_batch((_request("a", 21, 21, 1),), _envelope(items=1))


def test_preflight_requires_the_complete_batch_and_refuses_over_quota_before_dispatch() -> None:
    requests = tuple(_request(label, 2, 20, 1) for label in ("a", "b", "c"))
    allocation = allocate_elastic_batch(requests, _envelope())
    observations = tuple(
        RenderedInputObservation(item.public_input_digest, item.rendered_input_tokens)
        for item in allocation.allocations
    )

    summary = preflight_rendered_batch(allocation, requests, observations, _envelope())

    assert summary.item_count == 3
    assert summary.total_rendered_input_tokens == 30
    with pytest.raises(ValueError, match="complete item set"):
        preflight_rendered_batch(allocation, requests, observations[:-1], _envelope())
    first = observations[0]
    over_quota = (
        RenderedInputObservation(first.public_input_digest, first.rendered_input_tokens + 1),
        *observations[1:],
    )
    with pytest.raises(ValueError, match="allocation"):
        preflight_rendered_batch(allocation, requests, over_quota, _envelope())


def test_preflight_revalidates_allocation_integrity_instead_of_trusting_a_dataclass() -> None:
    requests = tuple(_request(label, 2, 20, 1) for label in ("a", "b", "c"))
    allocation = allocate_elastic_batch(requests, _envelope())
    observations = tuple(
        RenderedInputObservation(item.public_input_digest, item.rendered_input_tokens)
        for item in allocation.allocations
    )
    forged_item = replace(
        allocation.allocations[0],
        payload_tokens=allocation.allocations[0].payload_tokens + 1,
    )
    forged = replace(allocation, allocations=(forged_item, *allocation.allocations[1:]))

    with pytest.raises(ValueError, match="internally inconsistent"):
        preflight_rendered_batch(forged, requests, observations, _envelope())


def test_preflight_rejects_an_internally_consistent_non_frozen_allocation() -> None:
    requests = tuple(_request(label, 2, 20, 1) for label in ("a", "b", "c"))
    allocation = allocate_elastic_batch(requests, _envelope())
    first, second, third = allocation.allocations
    shifted_first = replace(
        first,
        payload_tokens=first.payload_tokens + 1,
        rendered_input_tokens=first.rendered_input_tokens + 1,
    )
    shifted_second = replace(
        second,
        payload_tokens=second.payload_tokens - 1,
        rendered_input_tokens=second.rendered_input_tokens - 1,
    )
    forged = replace(allocation, allocations=(shifted_first, shifted_second, third))
    observations = tuple(
        RenderedInputObservation(item.public_input_digest, item.rendered_input_tokens)
        for item in forged.allocations
    )

    with pytest.raises(ValueError, match="frozen weighted"):
        preflight_rendered_batch(forged, requests, observations, _envelope())


def test_complete_chat_counter_includes_frozen_roles_and_generation_wrapper() -> None:
    seen: list[tuple[tuple[str, str], ...]] = []

    def render(messages: tuple[tuple[str, str], ...]) -> str:
        seen.append(messages)
        return "<bos>" + "".join(f"<{role}>{text}" for role, text in messages) + "<assistant>"

    count = count_rendered_chat_input(
        system_prompt="frozen system",
        user_prompt="question and evidence",
        render_chat=render,
        token_counter=len,
    )

    assert seen == [(("system", "frozen system"), ("user", "question and evidence"))]
    assert count == len("<bos><system>frozen system<user>question and evidence<assistant>")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"token_axis_sha256": "not-a-digest"},
        {"max_rendered_input_tokens": 21},
        {"mean_rendered_input_tokens": 21},
        {"items_per_split": 0},
    ],
)
def test_envelope_rejects_invalid_or_endpoint_infeasible_limits(
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "token_axis_sha256": "a" * 64,
        "max_rendered_input_tokens": 20,
        "mean_rendered_input_tokens": 10,
        "items_per_split": 3,
        "output_reserve_tokens": 5,
        "endpoint_model_limit": 25,
    }
    values.update(kwargs)

    with pytest.raises((TypeError, ValueError)):
        ElasticContextEnvelope(**values)  # type: ignore[arg-type]
