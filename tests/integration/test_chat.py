"""Integration tests for synchronous chat completions against mocked LLM Gateway."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from llm_gateway_sdk import (
    GatewayAuthenticationError,
    GatewayBadRequestError,
    GatewayInternalServerError,
    GatewayPermissionDeniedError,
    GatewayRateLimitError,
    GatewaySettings,
    MissingGatewayConfigError,
)


@pytest.mark.parametrize(
    "alias", ["general-fast", "general-reasoning", "structured-output", "agent-tools"]
)
def test_chat_completion_with_gateway_model_aliases(
    alias: str,
    default_settings: GatewaySettings,
    mock_sync_client_factory: Any,
) -> None:
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        body = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": f"req-{alias}"},
            json={
                "id": f"chatcmpl-{alias}",
                "object": "chat.completion",
                "created": 1700000000,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": f"Reply from {alias}"},
                    }
                ],
                "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
            },
        )

    with mock_sync_client_factory(handler) as client:
        response = client.complete(
            model=alias,
            messages=[{"role": "user", "content": "Hello gateway"}],
        )

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert str(req.url) == "https://gateway.example.com/v1/chat/completions"
    assert req.headers["Authorization"] == f"Bearer {default_settings.api_key}"
    assert req.headers["X-Gateway-App-Name"] == "test-consumer"
    assert response.content == f"Reply from {alias}"
    assert response.choices[0].message.content == f"Reply from {alias}"
    assert response.request_id == f"req-{alias}"
    assert response._request_id == f"req-{alias}"


def test_complete_uses_default_model_and_raises_if_missing(
    mock_sync_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-default",
                "object": "chat.completion",
                "created": 1700000000,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Default model used"},
                    }
                ],
            },
        )

    with mock_sync_client_factory(handler) as client:
        resp = client.complete(messages=[{"role": "user", "content": "Hi"}])
        assert resp.model == "general-fast"
        assert resp.content == "Default model used"

    no_model_settings = GatewaySettings(
        base_url="https://gateway.example.com/v1",
        api_key="sk-test",
    )
    with (
        mock_sync_client_factory(handler, no_model_settings) as client2,
        pytest.raises(MissingGatewayConfigError),
    ):
        client2.complete(messages=[{"role": "user", "content": "Hi"}])


@pytest.mark.parametrize(
    ("status_code", "expected_exc"),
    [
        (400, GatewayBadRequestError),
        (401, GatewayAuthenticationError),
        (403, GatewayPermissionDeniedError),
        (429, GatewayRateLimitError),
        (500, GatewayInternalServerError),
        (502, GatewayInternalServerError),
        (503, GatewayInternalServerError),
    ],
)
def test_chat_errors_propagate_without_automatic_retry_by_default(
    status_code: int,
    expected_exc: type[Exception],
    mock_sync_client_factory: Any,
) -> None:
    attempt_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempt_count
        attempt_count += 1
        return httpx.Response(
            status_code,
            headers={"x-request-id": f"err-{status_code}"},
            json={"error": {"message": f"Gateway error {status_code}", "type": "gateway_error"}},
        )

    with mock_sync_client_factory(handler) as client, pytest.raises(expected_exc) as exc_info:
        client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Trigger error"}],
        )

    # Default max_retries=0 means exactly 1 request is sent to the gateway
    assert attempt_count == 1
    assert getattr(exc_info.value, "request_id", None) == f"err-{status_code}"
