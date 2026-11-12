"""Contract tests verifying Gateway SDK error mapping, status codes, retries, and raw headers."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from llm_gateway_sdk import (
    GatewayAPIStatusError,
    GatewayAuthenticationError,
    GatewayBadRequestError,
    GatewayConnectionError,
    GatewayInternalServerError,
    GatewayNotFoundError,
    GatewayPermissionDeniedError,
    GatewayRateLimitError,
    GatewaySettings,
    GatewayTimeoutError,
    GatewayUnprocessableEntityError,
)


@pytest.mark.parametrize(
    ("status_code", "expected_cls"),
    [
        (400, GatewayBadRequestError),
        (401, GatewayAuthenticationError),
        (403, GatewayPermissionDeniedError),
        (404, GatewayNotFoundError),
        (408, GatewayAPIStatusError),
        (422, GatewayUnprocessableEntityError),
        (429, GatewayRateLimitError),
        (500, GatewayInternalServerError),
        (502, GatewayInternalServerError),
        (503, GatewayInternalServerError),
    ],
)
def test_http_status_codes_map_to_gateway_exceptions(
    status_code: int,
    expected_cls: type[GatewayAPIStatusError],
    mock_sync_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            headers={"x-request-id": f"trace-{status_code}"},
            json={
                "error": {
                    "message": f"Simulated HTTP {status_code}",
                    "type": "api_error",
                    "code": str(status_code),
                }
            },
        )

    with mock_sync_client_factory(handler) as client, pytest.raises(expected_cls) as exc_info:
        client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Test status code"}],
        )

    err = exc_info.value
    assert err.status_code == status_code
    assert err.request_id == f"trace-{status_code}"


def test_with_raw_response_exposes_gateway_headers_for_all_resources(
    mock_sync_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {
            "x-request-id": "req-raw-001",
            "x-litellm-call-id": "call-litellm-99",
            "x-litellm-model-id": "general-fast-deployment",
        }
        if request.url.path == "/v1/embeddings":
            return httpx.Response(
                200,
                headers=headers,
                json={
                    "object": "list",
                    "model": "rag-embedding",
                    "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2]}],
                },
            )
        if request.url.path == "/v1/models":
            return httpx.Response(
                200,
                headers=headers,
                json={"object": "list", "data": [{"id": "general-fast", "object": "model"}]},
            )
        return httpx.Response(
            200,
            headers=headers,
            json={
                "id": "chatcmpl-raw-1",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "general-fast",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Raw OK"},
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        )

    with mock_sync_client_factory(handler) as client:
        raw_chat = client.chat.completions.with_raw_response.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert raw_chat.headers["x-request-id"] == "req-raw-001"
        assert raw_chat.headers["x-litellm-call-id"] == "call-litellm-99"
        assert raw_chat.status_code == 200
        assert raw_chat.parse().choices[0].message.content == "Raw OK"

        raw_emb = client.embeddings.with_raw_response.create(
            model="rag-embedding",
            input="Hello",
        )
        assert raw_emb.request_id == "req-raw-001"
        assert raw_emb.parse().embeddings == [[0.1, 0.2]]

        raw_models = client.models.with_raw_response.list()
        assert raw_models.request_id == "req-raw-001"
        assert raw_models.parse().data[0].id == "general-fast"


def test_network_timeout_connection_and_configured_retries(
    default_settings: GatewaySettings,
    mock_sync_client_factory: Any,
) -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connect timed out", request=request)

    with mock_sync_client_factory(timeout_handler) as client, pytest.raises(GatewayTimeoutError):
        client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Timeout"}],
        )

    def connect_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("DNS lookup failed", request=request)

    with mock_sync_client_factory(connect_handler) as client, pytest.raises(GatewayConnectionError):
        client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Connect fail"}],
        )

    # Verify opt-in retry behavior when max_retries > 0 on transient 503
    attempts = 0

    def transient_503_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, text="Upstream temporarily unavailable")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-retry-ok",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "general-fast",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Recovered"},
                    }
                ],
            },
        )

    transport = httpx.MockTransport(transient_503_handler)
    with (
        httpx.Client(transport=transport) as http_client,
        default_settings.create_client(http_client=http_client, max_retries=1) as retry_client,
    ):
        resp = retry_client.complete(messages=[{"role": "user", "content": "Retry test"}])
        assert resp.content == "Recovered"
        assert attempts == 2
