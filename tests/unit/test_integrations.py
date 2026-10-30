"""Unit tests for optional integrations (pydantic-settings, instructor, langchain, openllmetry)."""

from __future__ import annotations

import builtins
import json
import os
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from llm_gateway_sdk import (
    GatewaySettings,
    InvalidGatewaySettingsError,
    MissingGatewayConfigError,
)
from llm_gateway_sdk.integrations.instructor import (
    create_async_instructor_client,
    create_instructor_client,
)
from llm_gateway_sdk.integrations.langchain import (
    create_chat_model,
    create_embeddings_model,
)
from llm_gateway_sdk.integrations.openllmetry import configure_observability
from llm_gateway_sdk.integrations.pydantic_settings import (
    GatewayBaseSettings,
    connection_options,
)

# ── Pydantic Settings Integration ──────────────────────────────────────────


def test_pydantic_settings_loads_llm_gateway_and_legacy_litellm_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_API_BASE", "https://gateway.example.com/v1/")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-secret-key-123")
    monkeypatch.setenv("LITELLM_MODEL", "general-fast")
    monkeypatch.setenv("LITELLM_EMBEDDING_MODEL", "rag-embedding")
    monkeypatch.setenv("LITELLM_EMBEDDING_DIMENSIONS", "1536")

    cfg = GatewayBaseSettings(_env_file=None)
    assert connection_options(cfg) == {
        "api_base": "https://gateway.example.com/v1",
        "api_key": "sk-secret-key-123",
    }
    assert "sk-secret-key-123" not in repr(cfg)
    assert "sk-secret-key-123" not in cfg.model_dump_json()

    gw_settings = cfg.to_gateway_settings()
    assert gw_settings.base_url == "https://gateway.example.com/v1"
    assert gw_settings.api_key == "sk-secret-key-123"
    assert gw_settings.default_model == "general-fast"
    assert gw_settings.default_embedding_model == "rag-embedding"
    assert gw_settings.embedding_dimensions == 1536

    sync_client = cfg.create_gateway_client()
    async_client = cfg.create_async_gateway_client()
    try:
        assert str(sync_client.base_url).rstrip("/") == "https://gateway.example.com/v1"
        assert str(async_client.base_url).rstrip("/") == "https://gateway.example.com/v1"
    finally:
        sync_client.close()


def test_pydantic_settings_redacts_validation_errors() -> None:
    with pytest.raises(ValidationError) as exc_info:
        GatewayBaseSettings(
            _env_file=None,
            gateway_base="https://user:super-secret@localhost/v1",  # type: ignore[arg-type]
            gateway_key="super-secret",  # type: ignore[arg-type]
        )
    assert "super-secret" not in str(exc_info.value)
    assert "super-secret" not in exc_info.value.json()
    assert "super-secret" not in str(exc_info.value.errors())


def test_pydantic_settings_empty_dimensions_and_missing_credentials() -> None:
    cfg = GatewayBaseSettings(
        _env_file=None,
        gateway_base=SecretStr("https://gateway.example.com/v1"),
        gateway_key=SecretStr(""),
        embedding_dimensions="",  # type: ignore[arg-type]
    )
    assert cfg.embedding_dimensions is None
    with pytest.raises(MissingGatewayConfigError):
        connection_options(cfg)
    with pytest.raises(MissingGatewayConfigError):
        cfg.to_gateway_settings()


# ── LangChain Integration ──────────────────────────────────────────────────


def test_langchain_create_chat_and_embeddings_models(
    default_settings: GatewaySettings,
) -> None:
    chat = create_chat_model(
        default_settings,
        temperature=0.2,
        max_tokens=512,
        streaming=True,
    )
    assert chat.model_name == "general-fast"
    assert chat.openai_api_base == "https://gateway.example.com/v1"
    assert chat.max_retries == 0
    assert chat.streaming is True
    assert default_settings.api_key not in repr(chat)

    embeddings = create_embeddings_model(default_settings)
    assert embeddings.model == "rag-embedding"
    assert embeddings.dimensions == 1536
    assert embeddings.openai_api_base == "https://gateway.example.com/v1"
    assert embeddings.max_retries == 0
    assert embeddings.check_embedding_ctx_length is False
    assert default_settings.api_key not in repr(embeddings)


def test_langchain_mock_transport_execution(
    default_settings: GatewaySettings,
) -> None:
    captured_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_requests.append({"url": str(request.url), "body": body})
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "model": "rag-embedding",
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
                    "usage": {"prompt_tokens": 3, "total_tokens": 3},
                },
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-lc-1",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "general-fast",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "LangChain OK"},
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        chat = create_chat_model(
            default_settings,
            max_tokens=24,
            temperature=0.0,
            http_client=http_client,
        )
        reply = chat.invoke("Hello gateway")
        assert reply.content == "LangChain OK"

        embed = create_embeddings_model(default_settings, dimensions=3, http_client=http_client)
        vec = embed.embed_query(" Embed me ")
        assert vec == [0.1, 0.2, 0.3]

    assert len(captured_requests) == 2
    assert captured_requests[0]["body"]["model"] == "general-fast"
    assert captured_requests[0]["body"]["max_tokens"] == 24
    assert "max_completion_tokens" not in captured_requests[0]["body"]
    assert captured_requests[1]["body"]["model"] == "rag-embedding"
    assert captured_requests[1]["body"]["dimensions"] == 3


def test_langchain_validation_errors() -> None:
    settings_without_models = GatewaySettings(
        base_url="https://gateway.example.com/v1",
        api_key="sk-test",
    )
    with pytest.raises(MissingGatewayConfigError):
        create_chat_model(settings_without_models)
    with pytest.raises(MissingGatewayConfigError):
        create_embeddings_model(settings_without_models)
    with pytest.raises(InvalidGatewaySettingsError):
        create_chat_model("not-settings")  # type: ignore[arg-type]
    with pytest.raises(InvalidGatewaySettingsError):
        create_embeddings_model("not-settings")  # type: ignore[arg-type]


# ── Instructor Integration ─────────────────────────────────────────────────


def test_instructor_integration_with_stub_module(
    default_settings: GatewaySettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Any, Any, dict[str, Any]]] = []

    fake_instructor = ModuleType("instructor")
    fake_instructor.Mode = SimpleNamespace(TOOLS="TOOLS", JSON="JSON")  # type: ignore[attr-defined]

    def fake_from_openai(client: Any, mode: Any = None, **kwargs: Any) -> dict[str, Any]:
        calls.append((client, mode, kwargs))
        return {"wrapped": client, "mode": mode, "kwargs": kwargs}

    fake_instructor.from_openai = fake_from_openai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "instructor", fake_instructor)

    wrapped_sync = create_instructor_client(default_settings, max_retries=1)
    assert wrapped_sync["mode"] == "TOOLS"
    assert wrapped_sync["kwargs"] == {"max_retries": 1}
    wrapped_sync["wrapped"].close()

    async_client = default_settings.create_async_client()
    wrapped_async = create_async_instructor_client(async_client, mode="JSON")
    assert wrapped_async["wrapped"] is async_client
    assert wrapped_async["mode"] == "JSON"

    with pytest.raises(InvalidGatewaySettingsError):
        create_instructor_client("invalid")  # type: ignore[arg-type]
    with pytest.raises(InvalidGatewaySettingsError):
        create_async_instructor_client("invalid")  # type: ignore[arg-type]


def test_instructor_missing_dependency_raises_helpful_import_error(
    default_settings: GatewaySettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "instructor", raising=False)
    real_import = builtins.__import__

    def block_instructor(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "instructor":
            raise ImportError("No module named 'instructor'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_instructor)
    with pytest.raises(ImportError, match="llm-gateway-sdk\\[structured\\]"):
        create_instructor_client(default_settings)


# ── OpenLLMetry Integration ────────────────────────────────────────────────


def test_openllmetry_privacy_by_default_and_secret_protection(
    default_settings: GatewaySettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_calls: list[dict[str, Any]] = []

    traceloop_pkg = ModuleType("traceloop")
    traceloop_sdk = ModuleType("traceloop.sdk")

    class FakeTraceloop:
        @staticmethod
        def init(**kwargs: Any) -> None:
            init_calls.append(kwargs)

    traceloop_sdk.Traceloop = FakeTraceloop  # type: ignore[attr-defined]
    traceloop_pkg.sdk = traceloop_sdk  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "traceloop", traceloop_pkg)
    monkeypatch.setitem(sys.modules, "traceloop.sdk", traceloop_sdk)

    obs_cfg = configure_observability(
        default_settings,
        disable_batch=True,
        resource_attributes={"team": "quant"},
    )
    assert obs_cfg.app_name == "test-consumer"
    assert obs_cfg.environment == "test"
    assert obs_cfg.record_content is False
    assert os.environ["TRACELOOP_TRACE_CONTENT"] == "false"
    assert len(init_calls) == 1
    assert init_calls[0]["app_name"] == "test-consumer"
    assert init_calls[0]["resource_attributes"]["team"] == "quant"
    assert default_settings.api_key not in str(init_calls[0])

    # Reject secret attribute keys or leaking the gateway API key in attributes
    with pytest.raises(InvalidGatewaySettingsError, match="secret attribute"):
        configure_observability(
            default_settings,
            resource_attributes={"api_key": "should-fail"},
        )
    with pytest.raises(InvalidGatewaySettingsError, match="contains the gateway API key"):
        configure_observability(
            default_settings,
            resource_attributes={"custom": default_settings.api_key},
        )
    with pytest.raises(InvalidGatewaySettingsError):
        configure_observability("not-settings")  # type: ignore[arg-type]
    with pytest.raises(InvalidGatewaySettingsError):
        configure_observability(default_settings, record_content="yes")  # type: ignore[arg-type]
