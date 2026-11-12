"""Unit tests for ``GatewaySettings`` initialization, immutability, secret masking, and env."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import httpx
import pytest

from llm_gateway_sdk import (
    REDACTED_SECRET,
    GatewaySettings,
    InvalidGatewaySettingsError,
    MissingGatewayConfigError,
)


def test_settings_initialization_and_defaults() -> None:
    settings = GatewaySettings(
        base_url="https://gateway.example.com/v1",
        api_key="sk-consumer-virtual-key",
    )
    assert settings.base_url == "https://gateway.example.com/v1"
    assert settings.api_key == "sk-consumer-virtual-key"
    assert settings.default_model is None
    assert settings.default_embedding_model is None
    assert settings.embedding_dimensions is None
    assert settings.timeout == 30.0
    assert settings.max_retries == 0
    assert settings.app_name is None
    assert settings.environment is None
    assert settings.default_headers is None
    assert settings.verify_ssl is True


def test_settings_is_immutable(default_settings: GatewaySettings) -> None:
    with pytest.raises(FrozenInstanceError):
        default_settings.api_key = "mutated"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        default_settings.base_url = "https://other.example.com/v1"  # type: ignore[misc]


def test_secret_redaction_in_repr_str_and_dict(default_settings: GatewaySettings) -> None:
    secret = "sk-test-virtual-key-do-not-leak"
    assert secret not in repr(default_settings)
    assert secret not in str(default_settings)
    assert REDACTED_SECRET in repr(default_settings)

    redacted_dict = default_settings.to_dict()
    assert redacted_dict["api_key"] == REDACTED_SECRET
    assert secret not in str(redacted_dict)

    unredacted_dict = default_settings.to_dict(redact_secrets=False)
    assert unredacted_dict["api_key"] == secret


def test_default_headers_immutability() -> None:
    settings = GatewaySettings(
        base_url="https://gateway.example.com/v1",
        api_key="sk-consumer-key",
        default_headers={"X-Custom": "val"},
    )
    assert settings.default_headers is not None
    assert settings.default_headers["X-Custom"] == "val"
    with pytest.raises(TypeError):
        settings.default_headers["X-Other"] = "blocked"  # type: ignore[index]


def test_build_default_headers_attribution_and_merging() -> None:
    settings = GatewaySettings(
        base_url="https://gateway.example.com/v1",
        api_key="sk-consumer-key",
        app_name="my-service",
        environment="production",
        default_headers={"X-Correlation-ID": "req-123"},
    )
    headers = settings.build_default_headers(
        extra_headers={"X-Extra": "true", "x-correlation-id": "req-456"}
    )
    assert headers == {
        "X-Gateway-App-Name": "my-service",
        "X-Title": "my-service",
        "X-Gateway-Environment": "production",
        "x-correlation-id": "req-456",
        "X-Extra": "true",
    }


def test_connection_options_strips_trailing_slash_only_when_requested() -> None:
    settings = GatewaySettings(
        base_url="https://gateway.example.com/v1/",
        api_key="sk-consumer-key",
    )
    assert settings.base_url == "https://gateway.example.com/v1/"
    assert settings.connection_options() == {
        "api_base": "https://gateway.example.com/v1",
        "api_key": "sk-consumer-key",
    }
    assert settings.connection_options(strip_trailing_slash=False) == {
        "api_base": "https://gateway.example.com/v1/",
        "api_key": "sk-consumer-key",
    }


def test_from_env_loads_all_llm_gateway_variables() -> None:
    env = {
        "LLM_GATEWAY_BASE_URL": "https://gateway.example.com/v1",
        "LLM_GATEWAY_API_KEY": "sk-env-virtual-key",
        "LLM_GATEWAY_DEFAULT_MODEL": "general-fast",
        "LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL": "rag-embedding",
        "LLM_GATEWAY_EMBEDDING_DIMENSIONS": "1536",
        "LLM_GATEWAY_TIMEOUT": "45.5",
        "LLM_GATEWAY_MAX_RETRIES": "1",
        "LLM_GATEWAY_APP_NAME": "my-service",
        "LLM_GATEWAY_ENVIRONMENT": "production",
        "LLM_GATEWAY_VERIFY_SSL": "true",
    }
    settings = GatewaySettings.from_env(environ=env)
    assert settings.base_url == "https://gateway.example.com/v1"
    assert settings.api_key == "sk-env-virtual-key"
    assert settings.default_model == "general-fast"
    assert settings.default_embedding_model == "rag-embedding"
    assert settings.embedding_dimensions == 1536
    assert settings.timeout == 45.5
    assert settings.max_retries == 1
    assert settings.app_name == "my-service"
    assert settings.environment == "production"
    assert settings.verify_ssl is True


def test_from_env_never_falls_back_to_openai_or_master_key() -> None:
    env = {
        "LLM_GATEWAY_BASE_URL": "https://gateway.example.com/v1",
        "OPENAI_API_KEY": "sk-native-openai-key",
        "LITELLM_MASTER_KEY": "sk-master-admin-key",
        "LITELLM_API_KEY": "sk-legacy-key",
    }
    with pytest.raises(MissingGatewayConfigError):
        GatewaySettings.from_env(environ=env)


def test_from_env_rejects_master_key_used_as_consumer_key() -> None:
    env = {
        "LLM_GATEWAY_BASE_URL": "https://gateway.example.com/v1",
        "LLM_GATEWAY_API_KEY": "sk-master-secret-999",
        "LITELLM_MASTER_KEY": "sk-master-secret-999",
    }
    with pytest.raises(InvalidGatewaySettingsError) as exc_info:
        GatewaySettings.from_env(environ=env)
    assert "sk-master-secret-999" not in str(exc_info.value)


def test_from_env_opt_in_legacy_litellm_variables() -> None:
    env = {
        "LITELLM_API_BASE": "https://gateway.example.com/v1",
        "LITELLM_API_KEY": "sk-legacy-consumer-key",
        "LITELLM_MODEL": "general-reasoning",
        "LITELLM_EMBEDDING_MODEL": "rag-embedding",
        "RAG_EMBEDDING_DIMENSIONS": "1536",
    }
    settings = GatewaySettings.from_env(environ=env, allow_legacy_litellm_env=True)
    assert settings.base_url == "https://gateway.example.com/v1"
    assert settings.api_key == "sk-legacy-consumer-key"
    assert settings.default_model == "general-reasoning"
    assert settings.default_embedding_model == "rag-embedding"
    assert settings.embedding_dimensions == 1536


def test_from_env_overrides_and_unknown_kwargs() -> None:
    env = {
        "LLM_GATEWAY_BASE_URL": "https://gateway.example.com/v1",
        "LLM_GATEWAY_API_KEY": "sk-env-key",
    }
    custom_timeout = httpx.Timeout(20.0, connect=5.0)
    settings = GatewaySettings.from_env(
        environ=env,
        timeout=custom_timeout,
        max_retries=2,
        verify_ssl=False,
        default_headers={"X-Service": "test"},
    )
    assert settings.timeout == custom_timeout
    assert settings.max_retries == 2
    assert settings.verify_ssl is False
    assert settings.default_headers == {"X-Service": "test"}

    with pytest.raises(InvalidGatewaySettingsError):
        GatewaySettings.from_env(
            environ={"LLM_GATEWAY_BASE_URL": "https://gateway.example.com/v1"},
            api_key=12345,
        )

    with pytest.raises(TypeError, match="Unexpected keyword arguments"):
        GatewaySettings.from_env(environ=env, unknown_option=True)


def test_from_env_whitespace_only_optional_vars_use_defaults() -> None:
    env = {
        "LLM_GATEWAY_BASE_URL": "https://gateway.example.com/v1",
        "LLM_GATEWAY_API_KEY": "sk-env-key",
        "LLM_GATEWAY_TIMEOUT": "   ",
        "LLM_GATEWAY_MAX_RETRIES": "   ",
        "LLM_GATEWAY_VERIFY_SSL": "   ",
    }
    settings = GatewaySettings.from_env(environ=env)
    assert settings.timeout == 30.0
    assert settings.max_retries == 0
    assert settings.verify_ssl is True


def test_from_env_supports_llm_gateway_url_and_key_aliases() -> None:
    env = {
        "LLM_GATEWAY_URL": "https://gateway.example.com/v1",
        "LLM_GATEWAY_KEY": "sk-short-env-key",
        "LLM_GATEWAY_MODEL": "general-fast",
        "LLM_GATEWAY_EMBEDDING_MODEL": "rag-embedding",
    }
    settings = GatewaySettings.from_env(environ=env)
    assert settings.base_url == "https://gateway.example.com/v1"
    assert settings.api_key == "sk-short-env-key"
    assert settings.default_model == "general-fast"
    assert settings.default_embedding_model == "rag-embedding"
