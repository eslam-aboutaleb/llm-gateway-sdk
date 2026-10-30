"""Unit tests for synchronous and asynchronous client lifecycle management."""

from __future__ import annotations

import pytest

from llm_gateway_sdk import GatewaySettings


def test_sync_client_context_manager_and_close(default_settings: GatewaySettings) -> None:
    with default_settings.create_client() as client:
        assert not client.is_closed()
    assert client.is_closed()


@pytest.mark.asyncio
async def test_async_client_context_manager_and_aclose(
    default_settings: GatewaySettings,
) -> None:
    async with default_settings.create_async_client() as async_client:
        assert not async_client.is_closed()
    assert async_client.is_closed()


def test_multiple_clients_are_independent_not_singletons(
    default_settings: GatewaySettings,
) -> None:
    first = default_settings.create_client()
    second = default_settings.create_client(timeout=45.0)
    try:
        assert first is not second
        assert first.timeout == 15.0
        assert second.timeout == 45.0
    finally:
        first.close()
        second.close()
