"""Deterministic elastic rendered-input allocation and batch preflight."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ALLOCATOR_ID = "weighted-water-filling-v1"


def _positive_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field} must be an integer")
    if value <= 0:
        raise ValueError(f"{field} must be positive")
    return value


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


@dataclass(frozen=True, slots=True)
class ElasticContextEnvelope:
    """Evaluator-owned per-item maximum and per-candidate batch input cap."""

    token_axis_sha256: str
    max_rendered_input_tokens: int
    mean_rendered_input_tokens: int
    items_per_split: int
    output_reserve_tokens: int
    endpoint_model_limit: int
    allocator_id: str = _ALLOCATOR_ID

    def __post_init__(self) -> None:
        _digest(self.token_axis_sha256, "token_axis_sha256")
        for field in (
            "max_rendered_input_tokens",
            "mean_rendered_input_tokens",
            "items_per_split",
            "output_reserve_tokens",
            "endpoint_model_limit",
        ):
            _positive_integer(getattr(self, field), field)
        if self.mean_rendered_input_tokens > self.max_rendered_input_tokens:
            raise ValueError("mean rendered input cannot exceed the per-item maximum")
        if self.max_rendered_input_tokens + self.output_reserve_tokens > self.endpoint_model_limit:
            raise ValueError("rendered input maximum and output reserve exceed the endpoint limit")
        if self.allocator_id != _ALLOCATOR_ID:
            raise ValueError(f"allocator_id must be {_ALLOCATOR_ID}")

    @property
    def batch_input_token_cap(self) -> int:
        return self.mean_rendered_input_tokens * self.items_per_split

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "batch_input_token_cap": self.batch_input_token_cap,
            "schema_version": 1,
        }

    @property
    def envelope_sha256(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ElasticLengthPreference:
    """The only length-allocation fields authored by a candidate policy."""

    desired_rendered_input_tokens: int
    priority: int

    def __post_init__(self) -> None:
        for field in ("desired_rendered_input_tokens", "priority"):
            _positive_integer(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class ElasticItemRequest:
    """Evaluator-owned item identity/overhead joined to a policy preference."""

    public_input_digest: str
    fixed_overhead_tokens: int
    preference: ElasticLengthPreference

    def __post_init__(self) -> None:
        _digest(self.public_input_digest, "public_input_digest")
        _positive_integer(self.fixed_overhead_tokens, "fixed_overhead_tokens")
        if not isinstance(self.preference, ElasticLengthPreference):
            raise TypeError("preference must be an ElasticLengthPreference")
        if self.desired_rendered_input_tokens < self.fixed_overhead_tokens:
            raise ValueError("desired rendered input cannot be below its fixed overhead")

    @property
    def desired_rendered_input_tokens(self) -> int:
        return self.preference.desired_rendered_input_tokens

    @property
    def priority(self) -> int:
        return self.preference.priority


@dataclass(frozen=True, slots=True)
class ElasticItemAllocation:
    public_input_digest: str
    fixed_overhead_tokens: int
    desired_rendered_input_tokens: int
    priority: int
    payload_tokens: int
    rendered_input_tokens: int


@dataclass(frozen=True, slots=True)
class ElasticBatchAllocation:
    envelope_sha256: str
    allocations: tuple[ElasticItemAllocation, ...]
    total_fixed_overhead_tokens: int
    total_payload_tokens: int
    total_rendered_input_tokens: int
    unallocated_input_tokens: int


@dataclass(frozen=True, slots=True)
class RenderedInputObservation:
    """Frozen-tokenizer count of one complete rendered reader request."""

    public_input_digest: str
    rendered_input_tokens: int

    def __post_init__(self) -> None:
        _digest(self.public_input_digest, "public_input_digest")
        _positive_integer(self.rendered_input_tokens, "rendered_input_tokens")


@dataclass(frozen=True, slots=True)
class RenderedBatchPreflight:
    envelope_sha256: str
    item_count: int
    total_rendered_input_tokens: int
    batch_input_token_cap: int


def allocate_elastic_batch(
    requests: tuple[ElasticItemRequest, ...],
    envelope: ElasticContextEnvelope,
) -> ElasticBatchAllocation:
    """Allocate integer payload quotas with order-invariant weighted water filling."""

    if not isinstance(envelope, ElasticContextEnvelope):
        raise TypeError("envelope must be an ElasticContextEnvelope")
    if not isinstance(requests, tuple) or any(
        not isinstance(request, ElasticItemRequest) for request in requests
    ):
        raise TypeError("requests must be a tuple of ElasticItemRequest values")
    if len(requests) != envelope.items_per_split:
        raise ValueError("requests must contain the complete split item set")
    by_digest = {request.public_input_digest: request for request in requests}
    if len(by_digest) != len(requests):
        raise ValueError("public input digests must be unique")
    ordered = tuple(by_digest[digest] for digest in sorted(by_digest))
    if any(
        request.fixed_overhead_tokens > envelope.max_rendered_input_tokens for request in ordered
    ):
        raise ValueError("fixed request overhead exceeds the per-item maximum")
    overhead = sum(request.fixed_overhead_tokens for request in ordered)
    if overhead > envelope.batch_input_token_cap:
        raise ValueError("fixed request overhead exceeds the batch input-token cap")

    demands = {
        request.public_input_digest: max(
            min(request.desired_rendered_input_tokens, envelope.max_rendered_input_tokens)
            - request.fixed_overhead_tokens,
            0,
        )
        for request in ordered
    }
    available = envelope.batch_input_token_cap - overhead
    payload_budget = min(available, sum(demands.values()))
    payloads = _weighted_water_fill(ordered, demands, payload_budget)
    allocations = tuple(
        ElasticItemAllocation(
            public_input_digest=request.public_input_digest,
            fixed_overhead_tokens=request.fixed_overhead_tokens,
            desired_rendered_input_tokens=request.desired_rendered_input_tokens,
            priority=request.priority,
            payload_tokens=payloads[request.public_input_digest],
            rendered_input_tokens=(
                request.fixed_overhead_tokens + payloads[request.public_input_digest]
            ),
        )
        for request in ordered
    )
    total_payload = sum(item.payload_tokens for item in allocations)
    total_rendered = overhead + total_payload
    return ElasticBatchAllocation(
        envelope_sha256=envelope.envelope_sha256,
        allocations=allocations,
        total_fixed_overhead_tokens=overhead,
        total_payload_tokens=total_payload,
        total_rendered_input_tokens=total_rendered,
        unallocated_input_tokens=envelope.batch_input_token_cap - total_rendered,
    )


def _weighted_water_fill(
    requests: tuple[ElasticItemRequest, ...],
    demands: dict[str, int],
    payload_budget: int,
) -> dict[str, int]:
    assigned = {request.public_input_digest: 0 for request in requests}
    active = {request.public_input_digest: request for request in requests}
    remaining = payload_budget
    while active and remaining:
        total_weight = sum(request.priority for request in active.values())
        saturated = tuple(
            digest
            for digest, request in active.items()
            if demands[digest] * total_weight <= remaining * request.priority
        )
        if saturated:
            for digest in saturated:
                amount = demands[digest]
                assigned[digest] += amount
                remaining -= amount
                del active[digest]
            continue

        distributed = 0
        remainders: list[tuple[int, str]] = []
        for digest, request in active.items():
            numerator = remaining * request.priority
            amount, remainder = divmod(numerator, total_weight)
            assigned[digest] += amount
            distributed += amount
            remainders.append((remainder, digest))
        leftovers = remaining - distributed
        for _, digest in sorted(remainders, key=lambda value: (-value[0], value[1]))[:leftovers]:
            assigned[digest] += 1
        remaining = 0
    return assigned


def preflight_rendered_batch(
    allocation: ElasticBatchAllocation,
    requests: tuple[ElasticItemRequest, ...],
    observations: tuple[RenderedInputObservation, ...],
    envelope: ElasticContextEnvelope,
) -> RenderedBatchPreflight:
    """Validate all final rendered counts before the first target-model call."""

    if not isinstance(allocation, ElasticBatchAllocation):
        raise TypeError("allocation must be an ElasticBatchAllocation")
    if not isinstance(envelope, ElasticContextEnvelope):
        raise TypeError("envelope must be an ElasticContextEnvelope")
    if allocation.envelope_sha256 != envelope.envelope_sha256:
        raise ValueError("allocation does not match the frozen envelope")
    _validate_allocation(allocation, envelope)
    if allocation != allocate_elastic_batch(requests, envelope):
        raise ValueError("allocation does not match the frozen weighted allocation rule")
    if not isinstance(observations, tuple) or any(
        not isinstance(item, RenderedInputObservation) for item in observations
    ):
        raise TypeError("observations must be a tuple of RenderedInputObservation values")
    observed = {item.public_input_digest: item for item in observations}
    if len(observed) != len(observations):
        raise ValueError("rendered observations must have unique public input digests")
    allocated = {item.public_input_digest: item for item in allocation.allocations}
    if set(observed) != set(allocated):
        raise ValueError("rendered observations must contain the complete item set")
    for digest, item in observed.items():
        quota = allocated[digest]
        if item.rendered_input_tokens < quota.fixed_overhead_tokens:
            raise ValueError("complete rendered input is below its frozen overhead")
        if item.rendered_input_tokens > quota.rendered_input_tokens:
            raise ValueError("complete rendered input exceeds its item allocation")
        if item.rendered_input_tokens > envelope.max_rendered_input_tokens:
            raise ValueError("complete rendered input exceeds the per-item maximum")
        if item.rendered_input_tokens + envelope.output_reserve_tokens > (
            envelope.endpoint_model_limit
        ):
            raise ValueError("complete rendered input and output reserve exceed the endpoint limit")
    total = sum(item.rendered_input_tokens for item in observations)
    if total > envelope.batch_input_token_cap:
        raise ValueError("complete rendered batch exceeds the input-token cap")
    return RenderedBatchPreflight(
        envelope_sha256=envelope.envelope_sha256,
        item_count=len(observations),
        total_rendered_input_tokens=total,
        batch_input_token_cap=envelope.batch_input_token_cap,
    )


def _validate_allocation(
    allocation: ElasticBatchAllocation,
    envelope: ElasticContextEnvelope,
) -> None:
    items = allocation.allocations
    if len(items) != envelope.items_per_split:
        raise ValueError("allocation is internally inconsistent with the split size")
    digests = tuple(item.public_input_digest for item in items)
    if len(digests) != len(set(digests)) or digests != tuple(sorted(digests)):
        raise ValueError("allocation is internally inconsistent with item identities")
    for item in items:
        _digest(item.public_input_digest, "allocation.public_input_digest")
        for field in (
            "fixed_overhead_tokens",
            "desired_rendered_input_tokens",
            "priority",
            "rendered_input_tokens",
        ):
            _positive_integer(getattr(item, field), f"allocation.{field}")
        if not isinstance(item.payload_tokens, int) or isinstance(item.payload_tokens, bool):
            raise TypeError("allocation.payload_tokens must be an integer")
        if item.payload_tokens < 0:
            raise ValueError("allocation.payload_tokens must be non-negative")
        if item.rendered_input_tokens != item.fixed_overhead_tokens + item.payload_tokens:
            raise ValueError("allocation is internally inconsistent with its payload total")
        if item.rendered_input_tokens > min(
            item.desired_rendered_input_tokens,
            envelope.max_rendered_input_tokens,
        ):
            raise ValueError("allocation is internally inconsistent with its item maximum")
    overhead = sum(item.fixed_overhead_tokens for item in items)
    payload = sum(item.payload_tokens for item in items)
    rendered = sum(item.rendered_input_tokens for item in items)
    if (
        allocation.total_fixed_overhead_tokens != overhead
        or allocation.total_payload_tokens != payload
        or allocation.total_rendered_input_tokens != rendered
        or allocation.unallocated_input_tokens != envelope.batch_input_token_cap - rendered
        or rendered > envelope.batch_input_token_cap
    ):
        raise ValueError("allocation is internally inconsistent with its batch totals")


def count_rendered_chat_input(
    *,
    system_prompt: str,
    user_prompt: str,
    render_chat: Callable[[tuple[tuple[str, str], ...]], str],
    token_counter: Callable[[str], int],
) -> int:
    """Count a complete frozen chat rendering, including generation wrappers."""

    if not isinstance(system_prompt, str) or not system_prompt:
        raise ValueError("system_prompt must be a non-empty string")
    if not isinstance(user_prompt, str) or not user_prompt:
        raise ValueError("user_prompt must be a non-empty string")
    if not callable(render_chat) or not callable(token_counter):
        raise TypeError("render_chat and token_counter must be callable")
    rendered = render_chat((("system", system_prompt), ("user", user_prompt)))
    if not isinstance(rendered, str) or not rendered:
        raise TypeError("render_chat must return a non-empty string")
    count = token_counter(rendered)
    return _positive_integer(count, "rendered_input_tokens")
