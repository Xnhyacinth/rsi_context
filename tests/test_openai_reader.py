from __future__ import annotations

import json
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from rsicontext.eval import openai_compatible
from rsicontext.eval.openai_compatible import OpenAICompatibleReader, ReaderProtocolError
from rsicontext.experiment import APIProfile, BudgetSpec, ModelSpec, RunSpec, Split, Track
from rsicontext.policy import ContextPack, DocumentChunk
from rsicontext.registry import (
    RegistryEntry,
    ServingProfile,
    load_registry,
    load_serving_profiles,
)

ROOT = Path(__file__).parents[1]


def _context() -> ContextPack:
    chunk = DocumentChunk("c1", "doc", 0, 20, "ANSWER: amber", 2)
    return ContextPack(spans=(chunk,), ordering=("c1",), token_count=2)


def _runtime() -> tuple[RunSpec, ServingProfile, RegistryEntry, APIProfile]:
    registry = load_registry(ROOT / "configs" / "registry.json")
    profile = load_serving_profiles(ROOT / "configs" / "serving_profiles.json", registry).get(
        "qwen3.6-27b-128k-bf16-h200x8"
    )
    model = registry.select([profile.model_id])[0]
    run_spec = RunSpec(
        experiment="reader-test",
        dataset_revision="dataset-sha",
        evaluator_revision="evaluator-sha",
        policy_hash="policy-sha",
        serving_profile_hash=profile.profile_hash,
        reader_profile_hash="placeholder",
        chat_template_enable_thinking=False,
        model=ModelSpec(
            "Qwen/Qwen3.6-27B",
            cast(str, model.revision),
            cast(str, model.revision),
            profile.max_model_len,
        ),
        budget=BudgetSpec(context_tokens=4_096, output_tokens=64, target_calls=1),
        split=Split.VISIBLE,
        track=Track.SINGLE_READER,
        seed=profile.seed,
    )
    reader_profile = APIProfile(
        id="local-reader-test",
        provider="vllm-test",
        endpoint_env="TEST_ENDPOINT",
        api_key_env="TEST_API_KEY",
        allowed_host="127.0.0.1",
        model="Qwen/Qwen3.6-27B",
        protocol="chat-completions-sse",
        evaluation_max_model_len=profile.max_model_len,
        max_output_tokens=64,
        seed=profile.seed,
        temperature=0.0,
        provider_revision=model.revision,
        chat_template_enable_thinking=False,
    )
    return (
        replace(run_spec, reader_profile_hash=reader_profile.profile_hash),
        profile,
        model,
        reader_profile,
    )


def test_reader_sends_frozen_greedy_request_and_parses_answer() -> None:
    requests: list[urllib.request.Request] = []

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        requests.append(request)
        assert timeout == 30.0
        return json.dumps(
            {
                "choices": [{"message": {"content": "amber"}}],
                "usage": {"completion_tokens": 1, "prompt_tokens": 23},
            }
        ).encode()

    reader = OpenAICompatibleReader(
        endpoint="http://127.0.0.1:8000/v1/chat/completions",
        model="Qwen/Qwen3.6-27B",
        max_tokens=64,
        chat_template_enable_thinking=False,
        transport=transport,
    )

    output = reader.read("What is the color?", _context())

    assert output.answer == "amber"
    assert output.input_tokens == 23
    assert output.output_tokens == 1
    assert requests[0].data is not None
    payload = json.loads(cast(bytes, requests[0].data))
    assert payload["temperature"] == 0.0
    assert payload["seed"] == 42
    assert payload["max_tokens"] == 64
    assert payload["model"] == "Qwen/Qwen3.6-27B"
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert "[c1]" in payload["messages"][1]["content"]


def test_streaming_reader_requires_model_usage_and_done_marker() -> None:
    requests: list[urllib.request.Request] = []

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        requests.append(request)
        chunks = (
            {
                "choices": [{"delta": {"content": "am"}, "finish_reason": ""}],
                "id": "response-1",
                "model": "hy3-ioa",
                "usage": None,
            },
            {
                "choices": [{"delta": {"content": "ber"}, "finish_reason": "stop"}],
                "id": "response-1",
                "model": "hy3-ioa",
                "usage": {"completion_tokens": 2, "prompt_tokens": 20},
            },
        )
        events = [f"data: {json.dumps(chunk)}" for chunk in chunks]
        return ("\n\n".join((*events, "data: [DONE]")) + "\n\n").encode()

    reader = OpenAICompatibleReader(
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        model="hy3-ioa",
        max_tokens=8,
        max_model_len=4_096,
        stream=True,
        require_response_model=True,
        allowed_hosts=("copilot.tencent.com",),
        transport=transport,
    )

    output = reader.read("What is the color?", _context())

    assert output.answer == "amber"
    assert output.input_tokens == 20
    assert output.output_tokens == 2
    assert output.response_id == "response-1"
    assert output.response_model == "hy3-ioa"
    assert requests[0].data is not None
    payload = json.loads(cast(bytes, requests[0].data))
    assert payload["stream"] is True
    assert payload["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            'data: {"id":"r","model":"hy3-ioa","choices":[],"usage":'
            '{"prompt_tokens":1,"completion_tokens":1}}\n\n',
            "DONE",
        ),
        (
            'data: {"id":"r","model":"other","choices":[],"usage":'
            '{"prompt_tokens":1,"completion_tokens":1}}\n\ndata: [DONE]\n\n',
            "model",
        ),
        (
            'data: {"id":"r","model":"hy3-ioa","choices":[],"usage":null}\n\ndata: [DONE]\n\n',
            "usage",
        ),
    ],
)
def test_streaming_reader_fails_closed_on_incomplete_protocol(body: str, message: str) -> None:
    reader = OpenAICompatibleReader(
        endpoint="https://copilot.tencent.com/v2/chat/completions",
        model="hy3-ioa",
        max_tokens=8,
        stream=True,
        require_response_model=True,
        allowed_hosts=("copilot.tencent.com",),
        transport=lambda request, timeout: body.encode(),
    )

    with pytest.raises(ReaderProtocolError, match=message):
        reader.read("query", _context())


def test_reader_rejects_remote_endpoint_by_default() -> None:
    with pytest.raises(ValueError, match="host"):
        OpenAICompatibleReader(
            endpoint="https://example.com/v1/chat/completions", model="model", max_tokens=1
        )


@pytest.mark.parametrize(
    ("endpoint", "message"),
    [
        ("http://copilot.tencent.com/v2/chat/completions", "HTTPS"),
        ("https://user:secret@copilot.tencent.com/v2/chat/completions", "credentials"),
        ("https://copilot.tencent.com/v2/chat/completions?key=secret", "query"),
    ],
)
def test_reader_rejects_unsafe_remote_endpoint_forms(endpoint: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        OpenAICompatibleReader(
            endpoint=endpoint,
            model="hy3-ioa",
            max_tokens=1,
            allowed_hosts=("copilot.tencent.com",),
        )


def test_reader_factory_binds_model_decoding_and_budget_to_run_spec() -> None:
    run_spec, profile, registry_model, reader_profile = _runtime()
    reader = OpenAICompatibleReader.from_run_spec(
        endpoint=profile.chat_completions_endpoint,
        run_spec=run_spec,
        serving_profile=profile,
        registry_model=registry_model,
        reader_profile=reader_profile,
        transport=lambda request, timeout: b"{}",
    )

    assert reader.model == "Qwen/Qwen3.6-27B"
    assert reader.max_tokens == 64
    assert reader.seed == 42
    assert reader.max_model_len == 131_072
    assert reader.chat_template_enable_thinking is False

    with pytest.raises(ValueError, match="wall-time"):
        OpenAICompatibleReader.from_run_spec(
            endpoint=profile.chat_completions_endpoint,
            run_spec=run_spec,
            serving_profile=profile,
            registry_model=registry_model,
            reader_profile=reader_profile,
            timeout_seconds=run_spec.budget.wall_time_seconds + 1,
            transport=lambda request, timeout: b"{}",
        )

    mismatched = replace(
        run_spec,
        model=ModelSpec(
            "meta-llama/Llama-3.3-70B-Instruct",
            run_spec.model.revision,
            run_spec.model.tokenizer_revision,
            run_spec.model.max_model_len,
        ),
    )
    with pytest.raises(ValueError, match="model id"):
        OpenAICompatibleReader.from_run_spec(
            endpoint=profile.chat_completions_endpoint,
            run_spec=mismatched,
            serving_profile=profile,
            registry_model=registry_model,
            reader_profile=reader_profile,
            transport=lambda request, timeout: b"{}",
        )


def test_reader_factory_rejects_unbound_reader_profile_identity() -> None:
    run_spec, profile, registry_model, reader_profile = _runtime()

    with pytest.raises(ValueError, match="reader profile hash"):
        OpenAICompatibleReader.from_run_spec(
            endpoint=profile.chat_completions_endpoint,
            run_spec=replace(run_spec, reader_profile_hash="unbound-reader-hash"),
            serving_profile=profile,
            registry_model=registry_model,
            reader_profile=reader_profile,
            transport=lambda request, timeout: b"{}",
        )

    with pytest.raises(ValueError, match="thinking"):
        OpenAICompatibleReader.from_run_spec(
            endpoint=profile.chat_completions_endpoint,
            run_spec=replace(run_spec, chat_template_enable_thinking=True),
            serving_profile=profile,
            registry_model=registry_model,
            reader_profile=reader_profile,
            transport=lambda request, timeout: b"{}",
        )


def test_reader_fails_closed_on_malformed_response() -> None:
    reader = OpenAICompatibleReader(
        endpoint="http://localhost:8000/v1/chat/completions",
        model="model",
        max_tokens=1,
        transport=lambda request, timeout: b'{"choices":[]}',
    )

    with pytest.raises(ReaderProtocolError, match="choice"):
        reader.read("query", _context())

    missing_usage = OpenAICompatibleReader(
        endpoint="http://localhost:8000/v1/chat/completions",
        model="model",
        max_tokens=1,
        transport=lambda request, timeout: b'{"choices":[{"message":{"content":"x"}}]}',
    )
    with pytest.raises(ReaderProtocolError, match="usage"):
        missing_usage.read("query", _context())


def test_reader_enforces_reported_output_and_model_length_limits() -> None:
    output_overrun = OpenAICompatibleReader(
        endpoint="http://localhost:8000/v1/chat/completions",
        model="model",
        max_tokens=1,
        max_model_len=10,
        transport=lambda request, timeout: (
            b'{"choices":[{"message":{"content":"x"}}],'
            b'"usage":{"prompt_tokens":2,"completion_tokens":2}}'
        ),
    )
    with pytest.raises(ReaderProtocolError, match="output token limit"):
        output_overrun.read("query", _context())

    context_overrun = OpenAICompatibleReader(
        endpoint="http://localhost:8000/v1/chat/completions",
        model="model",
        max_tokens=2,
        max_model_len=3,
        transport=lambda request, timeout: (
            b'{"choices":[{"message":{"content":"x"}}],'
            b'"usage":{"prompt_tokens":3,"completion_tokens":1}}'
        ),
    )
    with pytest.raises(ReaderProtocolError, match="model length"):
        context_overrun.read("query", _context())


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_tokens": True},
        {"seed": False},
        {"timeout_seconds": float("nan")},
        {"allowed_hosts": ["localhost"]},
        {"stream": 1},
        {"require_response_model": "yes"},
        {"api_key": ""},
        {"transport": None},
    ],
)
def test_reader_constructor_rejects_weakly_typed_runtime_fields(
    overrides: dict[str, object],
) -> None:
    values = {
        "endpoint": "http://localhost:8000/v1/chat/completions",
        "model": "model",
        "max_tokens": 1,
        **overrides,
    }

    with pytest.raises((TypeError, ValueError)):
        OpenAICompatibleReader(**values)  # type: ignore[arg-type]


def test_default_transport_disables_proxies_and_rejects_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_handlers: list[object] = []

    class FakeOpener:
        def open(self, request: urllib.request.Request, timeout: float) -> object:
            raise AssertionError("network should not be reached")

    def fake_build_opener(*handlers: object) -> FakeOpener:
        captured_handlers.extend(handlers)
        return FakeOpener()

    monkeypatch.setattr(urllib.request, "build_opener", fake_build_opener)
    request = urllib.request.Request("http://localhost/v1/chat/completions")
    with pytest.raises(AssertionError, match="network"):
        openai_compatible._urlopen_transport(request, 1.0)

    proxy_handlers = [
        handler for handler in captured_handlers if isinstance(handler, urllib.request.ProxyHandler)
    ]
    assert len(proxy_handlers) == 1
    assert vars(proxy_handlers[0])["proxies"] == {}
    redirect_handler = next(
        handler
        for handler in captured_handlers
        if isinstance(handler, openai_compatible._RejectRedirects)
    )
    with pytest.raises(ReaderProtocolError, match="redirect"):
        redirect_handler.redirect_request(request, None, 302, "Found", {}, "https://example.com")


def test_default_transport_rejects_oversized_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, limit: int) -> bytes:
            assert limit == openai_compatible._MAX_RESPONSE_BYTES + 1
            return b"x" * limit

    class FakeOpener:
        def open(self, request: urllib.request.Request, timeout: float) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(urllib.request, "build_opener", lambda *handlers: FakeOpener())
    request = urllib.request.Request("http://localhost/v1/chat/completions")

    with pytest.raises(ReaderProtocolError, match="size limit"):
        openai_compatible._urlopen_transport(request, 1.0)
