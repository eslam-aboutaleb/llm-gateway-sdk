"""Integration tests for asynchronous client behavior, timeouts, and exceptions."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, AuthenticationError

from llm_gateway_sdk import GatewaySettings


@pytest.mark.asyncio
async def test_async_chat_completion_success(
    default_settings: GatewaySettings,
    mock_async_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {default_settings.api_key}"
        return httpx.Response(
            200,
            headers={"x-request-id": "async-req-01"},
            json={
                "id": "chatcmpl-async-01",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "general-fast",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Async hello"},
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    async with mock_async_client_factory(handler) as async_client:
        response = await async_client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert response.choices[0].message.content == "Async hello"
        assert response._request_id == "async-req-01"


@pytest.mark.asyncio
async def test_async_timeout_raises_api_timeout_error_without_retry(
    mock_async_client_factory: Any,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("Gateway read timed out", request=request)

    async with mock_async_client_factory(handler) as async_client:
        with pytest.raises(APITimeoutError):
            await async_client.chat.completions.create(
                model="general-fast",
                messages=[{"role": "user", "content": "Slow query"}],
            )
    assert calls == 1


@pytest.mark.asyncio
async def test_async_connection_and_auth_failures(
    mock_async_client_factory: Any,
) -> None:
    def conn_fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    async with mock_async_client_factory(conn_fail) as async_client:
        with pytest.raises(APIConnectionError):
            await async_client.chat.completions.create(
                model="general-fast",
                messages=[{"role": "user", "content": "Ping"}],
            )

    def auth_fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            headers={"x-request-id": "req-401"},
            json={"error": {"message": "Invalid virtual key"}},
        )

    async with mock_async_client_factory(auth_fail) as async_client:
        with pytest.raises(AuthenticationError) as exc_info:
            await async_client.chat.completions.create(
                model="general-fast",
                messages=[{"role": "user", "content": "Ping"}],
            )
        assert exc_info.value.request_id == "req-401"
