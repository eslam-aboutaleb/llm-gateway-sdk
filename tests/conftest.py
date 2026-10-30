"""Shared pytest fixtures for keyless unit, integration, and compatibility tests."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from llm_gateway_sdk import GatewaySettings


@pytest.fixture(autouse=True)
def isolate_gateway_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear gateway and provider environment variables unless running live tests."""
    if os.getenv("LLM_GATEWAY_LIVE_TESTS", "").lower() in {"1", "true", "yes"}:
        return
    for key in list(os.environ):
        if key.startswith(("LLM_GATEWAY_", "LITELLM_", "OPENAI_", "RAG_EMBEDDING_", "TRACELOOP_")):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def default_settings() -> GatewaySettings:
    """Return a clean, deterministic ``GatewaySettings`` instance for keyless tests."""
    return GatewaySettings(
        base_url="https://gateway.example.com/v1",
        api_key="sk-test-virtual-key-do-not-leak",
        default_model="general-fast",
        default_embedding_model="rag-embedding",
        embedding_dimensions=1536,
        timeout=15.0,
        max_retries=0,
        app_name="test-consumer",
        environment="test",
    )


@pytest.fixture
def mock_sync_client_factory(
    default_settings: GatewaySettings,
) -> Callable[[Callable[[httpx.Request], httpx.Response], GatewaySettings | None], Any]:
    """Create a synchronous ``OpenAI`` client wired to an ``httpx.MockTransport`` handler."""

    def _build(
        handler: Callable[[httpx.Request], httpx.Response],
        settings: GatewaySettings | None = None,
    ) -> Any:
        cfg = settings or default_settings
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return cfg.create_client(http_client=http_client)

    return _build


@pytest.fixture
def mock_async_client_factory(
    default_settings: GatewaySettings,
) -> Callable[[Callable[[httpx.Request], Any], GatewaySettings | None], Any]:
    """Create an asynchronous ``AsyncOpenAI`` client wired to an ``httpx.MockTransport`` handler."""

    def _build(
        handler: Callable[[httpx.Request], Any],
        settings: GatewaySettings | None = None,
    ) -> Any:
        cfg = settings or default_settings
        transport = httpx.MockTransport(handler)
        http_client = httpx.AsyncClient(transport=transport)
        return cfg.create_async_client(http_client=http_client)

    return _build
