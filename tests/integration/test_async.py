"""Integration tests for asynchronous client behavior, timeouts, embeddings, and exceptions."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from llm_gateway_sdk import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewaySettings,
    GatewayTimeoutError,
)


@pytest.mark.asyncio
async def test_async_chat_embeddings_models_and_health(
    default_settings: GatewaySettings,
    mock_async_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(200, text='"I\'m alive!"')
        assert request.headers["Authorization"] == f"Bearer {default_settings.api_key}"
        if request.url.path == "/v1/models":
            return httpx.Response(
                200,
                headers={"x-request-id": "async-models-01"},
                json={"object": "list", "data": [{"id": "general-fast", "object": "model"}]},
            )
        if request.url.path == "/v1/embeddings":
            return httpx.Response(
                200,
                headers={"x-request-id": "async-emb-01"},
                json={
                    "object": "list",
                    "model": "rag-embedding",
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                    "usage": {"prompt_tokens": 3, "total_tokens": 3},
                },
            )
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
        health_status = await async_client.health()
        assert health_status is True

        models_resp = await async_client.list_models()
        assert models_resp.model_ids == ["general-fast"]

        emb_resp = await async_client.embed(input="Async embed")
        assert emb_resp.embeddings == [[0.1, 0.2]]
        assert emb_resp.vectors == [[0.1, 0.2]]
        assert emb_resp.embedding == [0.1, 0.2]

        raw_chat = await async_client.chat.completions.with_raw_response.create(
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert raw_chat.request_id == "async-req-01"
        assert raw_chat.parse().content == "Async hello"

        raw_emb = await async_client.embeddings.with_raw_response.create(
            input="Async embed",
        )
        assert raw_emb.request_id == "async-emb-01"

        raw_models = await async_client.models.with_raw_response.list()
        assert raw_models.request_id == "async-models-01"

        response = await async_client.complete(
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert response.content == "Async hello"
        assert response.request_id == "async-req-01"


@pytest.mark.asyncio
async def test_async_timeout_raises_gateway_timeout_error_without_retry(
    mock_async_client_factory: Any,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("Gateway read timed out", request=request)

    async with mock_async_client_factory(handler) as async_client:
        with pytest.raises(GatewayTimeoutError):
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
        with pytest.raises(GatewayConnectionError):
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
        with pytest.raises(GatewayAuthenticationError) as exc_info:
            await async_client.chat.completions.create(
                model="general-fast",
                messages=[{"role": "user", "content": "Ping"}],
            )
        assert exc_info.value.request_id == "req-401"
