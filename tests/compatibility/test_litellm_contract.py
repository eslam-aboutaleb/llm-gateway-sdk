"""Compatibility tests against the deployed LiteLLM Gateway contract and opt-in live tests."""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest
from openai import NotFoundError

from llm_gateway_sdk import GatewaySettings


def test_models_endpoint_and_caddy_blocked_management_routes(
    mock_sync_client_factory: Any,
) -> None:
    """Verify `/v1/models` works while administrative routes return 404 NotFoundError."""
    allowed_paths = {"/v1/chat/completions", "/v1/embeddings", "/v1/models"}

    def caddy_gateway_simulator(request: httpx.Request) -> httpx.Response:
        if request.url.path not in allowed_paths:
            return httpx.Response(404, text="Not Found")
        if request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {
                            "id": "general-fast",
                            "object": "model",
                            "created": 1700000000,
                            "owned_by": "litellm",
                        },
                        {
                            "id": "general-reasoning",
                            "object": "model",
                            "created": 1700000000,
                            "owned_by": "litellm",
                        },
                        {
                            "id": "structured-output",
                            "object": "model",
                            "created": 1700000000,
                            "owned_by": "litellm",
                        },
                        {
                            "id": "agent-tools",
                            "object": "model",
                            "created": 1700000000,
                            "owned_by": "litellm",
                        },
                        {
                            "id": "rag-embedding",
                            "object": "model",
                            "created": 1700000000,
                            "owned_by": "litellm",
                        },
                    ],
                },
            )
        return httpx.Response(200, json={})

    with mock_sync_client_factory(caddy_gateway_simulator) as client:
        models_page = client.models.list()
        model_ids = [m.id for m in models_page.data]
        assert model_ids == [
            "general-fast",
            "general-reasoning",
            "structured-output",
            "agent-tools",
            "rag-embedding",
        ]

        # Management routes are blocked at Caddy ingress with 404
        for blocked_route in ["/key/generate", "/user/info", "/team/info", "/spend/logs"]:
            with pytest.raises(NotFoundError):
                client.post(blocked_route, cast_to=dict)


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("LLM_GATEWAY_LIVE_TESTS", "").lower() not in {"1", "true", "yes"},
    reason="Opt-in live gateway test; set LLM_GATEWAY_LIVE_TESTS=true to run",
)
def test_live_gateway_integration() -> None:
    """Opt-in live integration test against a deployed LiteLLM Gateway."""
    import asyncio
    import json

    from llm_gateway_sdk.integrations.langchain import create_chat_model, create_embeddings_model

    settings = GatewaySettings.from_env(allow_legacy_litellm_env=True)
    chat_model = settings.default_model or "general-fast"
    embed_model = settings.default_embedding_model or "rag-embedding"

    with settings.create_client() as client:
        models_page = client.models.list()
        model_ids = {m.id for m in models_page.data}
        assert "general-fast" in model_ids
        assert "rag-embedding" in model_ids

        completion = client.chat.completions.create(
            model=chat_model,
            messages=[{"role": "user", "content": "Reply with OK."}],
            max_tokens=16,
        )
        assert completion.choices[0].message.content

        stream = client.chat.completions.create(
            model=chat_model,
            messages=[{"role": "user", "content": "Reply with OK."}],
            max_tokens=16,
            stream=True,
        )
        chunks = [c.choices[0].delta.content or "" for c in stream if c.choices]
        assert "".join(chunks).strip()

        tool_resp = client.chat.completions.create(
            model="agent-tools",
            messages=[{"role": "user", "content": "Call echo_tool with text OK."}],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "echo_tool",
                        "description": "Echo text",
                        "parameters": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}},
                            "required": ["text"],
                        },
                    },
                }
            ],
            tool_choice="required",
            max_tokens=64,
        )
        tool_calls = tool_resp.choices[0].message.tool_calls
        assert tool_calls and tool_calls[0].function.name == "echo_tool"
        assert json.loads(tool_calls[0].function.arguments)["text"]

        embedding = client.embeddings.create(
            model=embed_model,
            input=["Synthetic live embedding test"],
        )
        assert len(embedding.data) == 1
        assert len(embedding.data[0].embedding) > 0

    async def verify_async() -> None:
        async with settings.create_async_client() as aclient:
            aresp = await aclient.chat.completions.create(
                model=chat_model,
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_tokens=16,
            )
            assert aresp.choices[0].message.content

    asyncio.run(verify_async())

    lc_chat = create_chat_model(settings, model=chat_model, max_tokens=24, temperature=0.0)
    assert lc_chat.invoke("Reply with OK.").content

    lc_emb = create_embeddings_model(settings, model=embed_model)
    assert len(lc_emb.embed_query("Synthetic check.")) > 0
