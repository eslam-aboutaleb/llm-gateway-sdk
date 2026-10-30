"""Integration tests for structured outputs (native Pydantic parse and JSON mode)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ValidationError


class MarketVerdict(BaseModel):
    market_id: str
    recommendation: str
    confidence: float


def test_structured_output_json_mode_and_pydantic_validation(
    mock_sync_client_factory: Any,
) -> None:
    captured_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_requests.append(body)
        return httpx.Response(
            200,
            headers={"x-request-id": "struct-1"},
            json={
                "id": "chatcmpl-struct-1",
                "object": "chat.completion",
                "created": 1700000000,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": (
                                '{"market_id":"0x123","recommendation":"buy_yes","confidence":0.82}'
                            ),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35},
            },
        )

    with mock_sync_client_factory(handler) as client:
        response = client.chat.completions.create(
            model="structured-output",
            messages=[{"role": "user", "content": "Evaluate market 0x123"}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        assert content is not None
        verdict = MarketVerdict.model_validate_json(content)
        assert verdict.market_id == "0x123"
        assert verdict.recommendation == "buy_yes"
        assert verdict.confidence == pytest.approx(0.82)

    assert captured_requests[0]["model"] == "structured-output"
    assert captured_requests[0]["response_format"] == {"type": "json_object"}


def test_structured_output_invalid_json_raises_validation_error(
    mock_sync_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-struct-bad",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "structured-output",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"market_id":"0x123","confidence":"not-a-float"}',
                        },
                    }
                ],
            },
        )

    with mock_sync_client_factory(handler) as client:
        response = client.chat.completions.create(
            model="structured-output",
            messages=[{"role": "user", "content": "Evaluate market 0x123"}],
            response_format={"type": "json_object"},
        )
        with pytest.raises(ValidationError):
            MarketVerdict.model_validate_json(response.choices[0].message.content or "")
