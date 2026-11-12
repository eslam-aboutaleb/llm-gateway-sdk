"""Integration tests for function and parallel tool calling (`agent-tools` alias)."""

from __future__ import annotations

import json
from typing import Any

import httpx


def test_single_and_parallel_tool_calls(mock_sync_client_factory: Any) -> None:
    captured_requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_requests.append(body)
        return httpx.Response(
            200,
            headers={"x-request-id": "tool-req-1"},
            json={
                "id": "chatcmpl-tools-1",
                "object": "chat.completion",
                "created": 1700000000,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "get_market_price",
                                        "arguments": '{"condition_id":"0xabc","side":"YES"}',
                                    },
                                },
                                {
                                    "id": "call_2",
                                    "type": "function",
                                    "function": {
                                        "name": "get_market_price",
                                        "arguments": '{"condition_id":"0xdef","side":"NO"}',
                                    },
                                },
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 25, "completion_tokens": 18, "total_tokens": 43},
            },
        )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_market_price",
                "description": "Retrieve current Polymarket price for a condition ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "condition_id": {"type": "string"},
                        "side": {"type": "string", "enum": ["YES", "NO"]},
                    },
                    "required": ["condition_id", "side"],
                },
            },
        }
    ]

    with mock_sync_client_factory(handler) as client:
        response = client.chat.completions.create(
            model="agent-tools",
            messages=[{"role": "user", "content": "Check YES on 0xabc and NO on 0xdef"}],
            tools=tools,
            tool_choice="required",
        )

    assert captured_requests[0]["model"] == "agent-tools"
    assert captured_requests[0]["tool_choice"] == "required"
    assert captured_requests[0]["tools"][0]["function"]["name"] == "get_market_price"

    tool_calls = response.choices[0].message.tool_calls
    assert tool_calls is not None
    assert response.tool_calls == tool_calls
    assert len(tool_calls) == 2
    assert json.loads(tool_calls[0].function.arguments) == {
        "condition_id": "0xabc",
        "side": "YES",
    }
    assert json.loads(tool_calls[1].function.arguments) == {
        "condition_id": "0xdef",
        "side": "NO",
    }
