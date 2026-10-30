"""FastAPI lifespan client management example using ``llm_gateway_sdk``.

Demonstrates creating a single shared ``AsyncOpenAI`` client at application startup
and closing it cleanly on shutdown rather than instantiating a client per request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from llm_gateway_sdk import GatewaySettings


@asynccontextmanager
async def gateway_lifespan(app: Any) -> AsyncIterator[None]:
    """Attach a shared ``AsyncOpenAI`` gateway client to ``app.state``."""
    settings = GatewaySettings.from_env()
    async with settings.create_async_client() as async_client:
        app.state.gateway_settings = settings
        app.state.llm_client = async_client
        yield
