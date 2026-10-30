"""Contract tests verifying native OpenAI SDK error mapping, status codes, and response headers."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)


@pytest.mark.parametrize(
    ("status_code", "expected_cls"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, PermissionDeniedError),
        (404, NotFoundError),
        (408, APIStatusError),
        (422, UnprocessableEntityError),
        (429, RateLimitError),
        (500, InternalServerError),
        (502, InternalServerError),
        (503, InternalServerError),
    ],
)
def test_http_status_codes_map_to_native_openai_exceptions(
    status_code: int,
    expected_cls: type[APIStatusError],
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


def test_with_raw_response_exposes_gateway_headers(
    mock_sync_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "x-request-id": "req-raw-001",
                "x-litellm-call-id": "call-litellm-99",
                "x-litellm-model-id": "general-fast-deployment",
            },
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
        raw_response = client.chat.completions.with_raw_response.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert raw_response.headers["x-request-id"] == "req-raw-001"
        assert raw_response.headers["x-litellm-call-id"] == "call-litellm-99"
        parsed = raw_response.parse()
        assert parsed.choices[0].message.content == "Raw OK"


def test_network_timeout_and_connection_errors(mock_sync_client_factory: Any) -> None:
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connect timed out", request=request)

    with mock_sync_client_factory(timeout_handler) as client, pytest.raises(APITimeoutError):
        client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Timeout"}],
        )

    def connect_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("DNS lookup failed", request=request)

    with mock_sync_client_factory(connect_handler) as client, pytest.raises(APIConnectionError):
        client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Connect fail"}],
        )
