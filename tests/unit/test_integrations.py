"""Unit tests for optional ``pydantic-settings`` integration (`llm-gateway-sdk[settings]`)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from llm_gateway_sdk import (
    AsyncGatewayClient,
    GatewayClient,
    MissingGatewayConfigError,
)
from llm_gateway_sdk.integrations.pydantic_settings import (
    GatewayBaseSettings,
    connection_options,
)


def test_pydantic_settings_loads_llm_gateway_and_legacy_litellm_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_API_BASE", "https://gateway.example.com/v1/")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-secret-key-123")
    monkeypatch.setenv("LITELLM_MODEL", "general-fast")
    monkeypatch.setenv("LITELLM_EMBEDDING_MODEL", "rag-embedding")
    monkeypatch.setenv("LITELLM_EMBEDDING_DIMENSIONS", "1536")

    cfg = GatewayBaseSettings()
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
        assert isinstance(sync_client, GatewayClient)
        assert isinstance(async_client, AsyncGatewayClient)
        assert str(sync_client.base_url).rstrip("/") == "https://gateway.example.com/v1"
        assert str(async_client.base_url).rstrip("/") == "https://gateway.example.com/v1"
    finally:
        sync_client.close()


def test_pydantic_settings_loads_short_llm_gateway_url_and_key_vars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_GATEWAY_URL", "https://gateway.example.com/v1")
    monkeypatch.setenv("LLM_GATEWAY_KEY", "sk-short-alias-key")
    monkeypatch.setenv("LLM_GATEWAY_MODEL", "general-fast")
    monkeypatch.setenv("LLM_GATEWAY_EMBEDDING_MODEL", "rag-embedding")

    cfg = GatewayBaseSettings()
    gw_settings = cfg.to_gateway_settings()
    assert gw_settings.base_url == "https://gateway.example.com/v1"
    assert gw_settings.api_key == "sk-short-alias-key"
    assert gw_settings.default_model == "general-fast"
    assert gw_settings.default_embedding_model == "rag-embedding"


def test_pydantic_settings_redacts_validation_errors() -> None:
    with pytest.raises(ValidationError) as exc_info:
        GatewayBaseSettings(
            gateway_base="https://user:super-secret@localhost/v1",  # type: ignore[arg-type]
            gateway_key="super-secret",  # type: ignore[arg-type]
        )
    assert "super-secret" not in str(exc_info.value)
    assert "super-secret" not in exc_info.value.json()
    assert "super-secret" not in str(exc_info.value.errors())


def test_pydantic_settings_empty_dimensions_and_missing_credentials() -> None:
    cfg = GatewayBaseSettings(
        gateway_base=SecretStr("https://gateway.example.com/v1"),
        gateway_key=SecretStr(""),
        embedding_dimensions="",  # type: ignore[arg-type]
    )
    assert cfg.embedding_dimensions is None
    with pytest.raises(MissingGatewayConfigError):
        connection_options(cfg)
    with pytest.raises(MissingGatewayConfigError):
        cfg.to_gateway_settings()

    cfg_none = GatewayBaseSettings()
    with pytest.raises(MissingGatewayConfigError):
        connection_options(cfg_none)
