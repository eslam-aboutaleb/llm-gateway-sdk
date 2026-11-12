"""Integration tests for single and batch vector embeddings (`/v1/embeddings`)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from llm_gateway_sdk import (
    GatewayBadRequestError,
    GatewaySettings,
    MissingGatewayConfigError,
)


def test_single_and_batch_embeddings_with_dimensions(
    default_settings: GatewaySettings,
    mock_sync_client_factory: Any,
) -> None:
    captured_payloads: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://gateway.example.com/v1/embeddings"
        payload = json.loads(request.content)
        captured_payloads.append(payload)
        inputs = payload["input"] if isinstance(payload["input"], list) else [payload["input"]]
        dim = payload.get("dimensions", 1536)
        return httpx.Response(
            200,
            headers={"x-request-id": "emb-req-1"},
            json={
                "object": "list",
                "model": payload["model"],
                "data": [
                    {
                        "object": "embedding",
                        "index": idx,
                        "embedding": [0.01 * (idx + 1)] * dim,
                    }
                    for idx in range(len(inputs))
                ],
                "usage": {"prompt_tokens": 6 * len(inputs), "total_tokens": 6 * len(inputs)},
            },
        )

    with mock_sync_client_factory(handler) as client:
        # High-level client.embed() uses default_embedding_model and embedding_dimensions
        single = client.embed(input="Polymarket rate decision market")
        assert len(single.data) == 1
        assert len(single.data[0].embedding) == 1536
        assert len(single.embeddings) == 1
        assert single.request_id == "emb-req-1"

        batch = client.embeddings.create(
            model="rag-embedding",
            input=["First market", "Second market"],
            dimensions=256,
        )
        assert len(batch.data) == 2
        assert len(batch.data[0].embedding) == 256
        assert len(batch.data[1].embedding) == 256

    assert captured_payloads[0]["model"] == "rag-embedding"
    assert captured_payloads[0]["dimensions"] == 1536
    assert captured_payloads[1]["dimensions"] == 256


def test_embed_missing_model_and_bad_request_error(
    mock_sync_client_factory: Any,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            headers={"x-request-id": "emb-400"},
            json={"error": {"message": "Model 'unknown-embed' not allowed for key"}},
        )

    with (
        mock_sync_client_factory(handler) as client,
        pytest.raises(GatewayBadRequestError) as exc_info,
    ):
        client.embeddings.create(model="unknown-embed", input="test")
    assert exc_info.value.request_id == "emb-400"

    no_model_settings = GatewaySettings(
        base_url="https://gateway.example.com/v1",
        api_key="sk-test",
    )
    with (
        mock_sync_client_factory(handler, no_model_settings) as client2,
        pytest.raises(MissingGatewayConfigError),
    ):
        client2.embed(input="test")
