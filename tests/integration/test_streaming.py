"""Integration tests for SSE streaming chat completions (sync and async)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest

from llm_gateway_sdk import GatewayBadRequestError, GatewayConnectionError

SSE_PAYLOAD = (
    b": keep-alive comment\n\n"
    b'data: {"id":"chatcmpl-stream-1","object":"chat.completion.chunk","created":1700000000,'
    b'"model":"general-fast","choices":[{"index":0,'
    b'"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}\n\n'
    b'data: {"id":"chatcmpl-stream-1","object":"chat.completion.chunk","created":1700000000,'
    b'"model":"general-fast","choices":[{"index":0,'
    b'"delta":{"content":" world"},"finish_reason":null}]}\n\n'
    b'data: {"id":"chatcmpl-stream-1","object":"chat.completion.chunk","created":1700000000,'
    b'"model":"general-fast","choices":[{"index":0,'
    b'"delta":{"content":"!"},"finish_reason":"stop"}]}\n\n'
    b"data: [DONE]\n\n"
)


def test_sync_streaming_chat_completion_and_iter_text(mock_sync_client_factory: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream", "x-request-id": "stream-sync-1"},
            content=SSE_PAYLOAD,
        )

    with mock_sync_client_factory(handler) as client:
        with client.stream(
            model="general-fast",
            messages=[{"role": "user", "content": "Greet me"}],
        ) as stream:
            assert stream.request_id == "stream-sync-1"
            assert "".join(stream.iter_text()) == "Hello world!"

        stream2 = client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Greet me"}],
            stream=True,
        )
        chunks = [chunk.choices[0].delta.content or "" for chunk in stream2]
        assert "".join(chunks) == "Hello world!"


def test_sync_streaming_http_error_raises_status_error(mock_sync_client_factory: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            headers={"x-request-id": "stream-err-400"},
            json={"error": {"message": "Invalid stream parameters"}},
        )

    with (
        mock_sync_client_factory(handler) as client,
        pytest.raises(GatewayBadRequestError) as exc_info,
    ):
        client.stream(messages=[{"role": "user", "content": "Fail"}])
    assert exc_info.value.request_id == "stream-err-400"


@pytest.mark.asyncio
async def test_async_streaming_chat_completion_and_early_cancellation(
    mock_async_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream", "x-request-id": "stream-async-1"},
            content=SSE_PAYLOAD,
        )

    async with mock_async_client_factory(handler) as async_client:
        async with await async_client.stream(
            model="general-fast",
            messages=[{"role": "user", "content": "Greet me"}],
        ) as stream:
            assert stream.request_id == "stream-async-1"
            collected = [piece async for piece in stream.iter_text()]
            assert "".join(collected) == "Hello world!"

        # Early cancellation after first chunk cleans up resources safely
        stream2 = await async_client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Cancel early"}],
            stream=True,
        )
        first_chunk = await stream2.__anext__()
        assert first_chunk.choices[0].delta.content == "Hello"
        assert first_chunk.content == "Hello"
        await stream2.close()


def test_partial_stream_failure_is_not_retried(mock_sync_client_factory: Any) -> None:
    attempts = 0

    class FailingByteStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            yield (
                b'data: {"id":"chatcmpl-stream-err","object":"chat.completion.chunk","created":1,'
                b'"model":"general-fast","choices":[{"index":0,"delta":{"content":"Partial"},"finish_reason":null}]}\n\n'
            )
            raise httpx.ReadError("Mid-stream connection drop")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=FailingByteStream(),
        )

    with mock_sync_client_factory(handler) as client:
        stream = client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Partial stream"}],
            stream=True,
        )
        iterator = iter(stream)
        first = next(iterator)
        assert first.choices[0].delta.content == "Partial"
        with pytest.raises(GatewayConnectionError):
            next(iterator)
    assert attempts == 1


@pytest.mark.asyncio
async def test_async_partial_stream_failure(mock_async_client_factory: Any) -> None:
    class FailingAsyncByteStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            yield (
                b'data: {"id":"chatcmpl-stream-err","object":"chat.completion.chunk","created":1,'
                b'"model":"general-fast","choices":[{"index":0,"delta":{"content":"Part1"},"finish_reason":null}]}\n\n'
            )
            raise httpx.ReadError("Async mid-stream disconnect")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=FailingAsyncByteStream(),
        )

    async with mock_async_client_factory(handler) as async_client:
        stream = await async_client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Partial async stream"}],
            stream=True,
        )
        first = await stream.__anext__()
        assert first.choices[0].delta.content == "Part1"
        with pytest.raises(GatewayConnectionError):
            await stream.__anext__()
