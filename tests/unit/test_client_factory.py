"""Unit tests for ``create_client`` and ``create_async_client`` factories."""

from __future__ import annotations

import httpx
import pytest

from llm_gateway_sdk import (
    AsyncGatewayClient,
    GatewayClient,
    GatewaySettings,
    InvalidGatewaySettingsError,
    create_async_client,
    create_client,
)


def test_create_sync_and_async_clients_return_gateway_instances(
    default_settings: GatewaySettings,
) -> None:
    sync_client = default_settings.create_client()
    async_client = default_settings.create_async_client()
    try:
        assert isinstance(sync_client, GatewayClient)
        assert isinstance(async_client, AsyncGatewayClient)
        assert str(sync_client.base_url).rstrip("/") == "https://gateway.example.com/v1"
        assert str(async_client.base_url).rstrip("/") == "https://gateway.example.com/v1"
        assert sync_client.api_key == default_settings.api_key
        assert async_client.api_key == default_settings.api_key
        assert sync_client.max_retries == 0
        assert async_client.max_retries == 0
        assert sync_client.timeout == 15.0
        assert async_client.timeout == 15.0
        assert sync_client.default_headers["X-Gateway-App-Name"] == "test-consumer"
        assert sync_client.default_headers["X-Gateway-Environment"] == "test"
        assert default_settings.api_key not in repr(sync_client)
        assert default_settings.api_key not in repr(async_client)
        assert "[REDACTED]" in repr(sync_client)
        assert "[REDACTED]" in repr(async_client)
    finally:
        sync_client.close()


def test_per_client_overrides_do_not_mutate_settings(
    default_settings: GatewaySettings,
) -> None:
    client = create_client(
        default_settings,
        timeout=60.0,
        max_retries=2,
        default_headers={"X-Request-Source": "batch-worker"},
    )
    try:
        assert client.timeout == 60.0
        assert client.max_retries == 2
        assert client.default_headers["X-Request-Source"] == "batch-worker"
        assert client.default_headers["X-Gateway-App-Name"] == "test-consumer"
        assert default_settings.timeout == 15.0
        assert default_settings.max_retries == 0
    finally:
        client.close()


def test_verify_ssl_false_creates_unverified_transport() -> None:
    settings = GatewaySettings(
        base_url="https://localhost:8443/v1",
        api_key="sk-test-local",
        verify_ssl=False,
    )
    sync_client = settings.create_client()
    async_client = settings.create_async_client()
    try:
        assert isinstance(sync_client, GatewayClient)
        assert isinstance(async_client, AsyncGatewayClient)
    finally:
        sync_client.close()


def test_custom_http_client_origin_mismatch_is_rejected(
    default_settings: GatewaySettings,
) -> None:
    evil_sync = httpx.Client(base_url="https://evil.example.com/v1")
    evil_async = httpx.AsyncClient(base_url="https://evil.example.com/v1")
    try:
        with pytest.raises(InvalidGatewaySettingsError, match="origin does not match"):
            default_settings.create_client(http_client=evil_sync)
        with pytest.raises(InvalidGatewaySettingsError, match="origin does not match"):
            default_settings.create_async_client(http_client=evil_async)
    finally:
        evil_sync.close()


def test_custom_http_client_with_follow_redirects_is_rejected(
    default_settings: GatewaySettings,
) -> None:
    redirect_client = httpx.Client(
        base_url="https://gateway.example.com/v1",
        follow_redirects=True,
    )
    try:
        with pytest.raises(InvalidGatewaySettingsError, match="follow_redirects=True"):
            default_settings.create_client(http_client=redirect_client)
    finally:
        redirect_client.close()


def test_invalid_settings_or_http_client_type_rejected(
    default_settings: GatewaySettings,
) -> None:
    with pytest.raises(InvalidGatewaySettingsError):
        create_client("not-settings")  # type: ignore[arg-type]
    with pytest.raises(InvalidGatewaySettingsError):
        create_async_client("not-settings")  # type: ignore[arg-type]
    with pytest.raises(InvalidGatewaySettingsError):
        default_settings.create_client(http_client="not-an-httpx-client")  # type: ignore[arg-type]
    with pytest.raises(InvalidGatewaySettingsError):
        default_settings.create_async_client(http_client="not-an-httpx-client")  # type: ignore[arg-type]
