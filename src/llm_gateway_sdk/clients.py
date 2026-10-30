"""Layer 3: Client factory layer returning native OpenAI and AsyncOpenAI clients.

Depends inward on Layer 0 (``exceptions``), Layer 1 (``validation``), and Layer 2 (``settings``).
Eliminates duplication between sync and async factories through shared parameter resolution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI, DefaultAsyncHttpxClient, DefaultHttpxClient, OpenAI

from llm_gateway_sdk.exceptions import InvalidGatewaySettingsError
from llm_gateway_sdk.settings import GatewaySettings
from llm_gateway_sdk.validation import (
    validate_http_client_origin,
    validate_max_retries,
    validate_timeout,
)

__all__ = [
    "create_async_client",
    "create_client",
]


@dataclass(frozen=True)
class _ResolvedClientOptions:
    """Internal validated options shared by sync and async OpenAI client construction."""

    api_key: str
    base_url: str
    timeout: float | httpx.Timeout
    max_retries: int
    default_headers: dict[str, str] | None


def _resolve_client_options(
    settings: GatewaySettings,
    *,
    caller_name: str,
    timeout: float | httpx.Timeout | None,
    max_retries: int | None,
    default_headers: Mapping[str, str] | None,
) -> _ResolvedClientOptions:
    """Validate and merge per-client overrides with ``GatewaySettings``."""
    if not isinstance(settings, GatewaySettings):
        raise InvalidGatewaySettingsError(
            f"{caller_name} requires a valid GatewaySettings instance"
        )

    effective_timeout = settings.timeout if timeout is None else validate_timeout(timeout)
    effective_retries = (
        settings.max_retries if max_retries is None else validate_max_retries(max_retries)
    )
    headers = settings.build_default_headers(extra_headers=default_headers)

    return _ResolvedClientOptions(
        api_key=settings.api_key,
        base_url=settings.base_url,
        timeout=effective_timeout,
        max_retries=effective_retries,
        default_headers=headers or None,
    )


def create_client(
    settings: GatewaySettings,
    *,
    timeout: float | httpx.Timeout | None = None,
    max_retries: int | None = None,
    default_headers: Mapping[str, str] | None = None,
    http_client: httpx.Client | None = None,
) -> OpenAI:
    """Create a configured synchronous :class:`openai.OpenAI` client for the LiteLLM Gateway."""
    options = _resolve_client_options(
        settings,
        caller_name="create_client",
        timeout=timeout,
        max_retries=max_retries,
        default_headers=default_headers,
    )

    effective_http_client: httpx.Client | None = http_client
    if effective_http_client is not None:
        if not isinstance(effective_http_client, httpx.Client):
            raise InvalidGatewaySettingsError(
                "create_client 'http_client' must be an httpx.Client instance"
            )
        validate_http_client_origin(effective_http_client, settings.base_url)
    elif not settings.verify_ssl:
        effective_http_client = DefaultHttpxClient(verify=False)

    return OpenAI(
        api_key=options.api_key,
        base_url=options.base_url,
        timeout=options.timeout,
        max_retries=options.max_retries,
        default_headers=options.default_headers,
        http_client=effective_http_client,
    )


def create_async_client(
    settings: GatewaySettings,
    *,
    timeout: float | httpx.Timeout | None = None,
    max_retries: int | None = None,
    default_headers: Mapping[str, str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> AsyncOpenAI:
    """Create a configured asynchronous :class:`openai.AsyncOpenAI` client for the Gateway."""
    options = _resolve_client_options(
        settings,
        caller_name="create_async_client",
        timeout=timeout,
        max_retries=max_retries,
        default_headers=default_headers,
    )

    effective_http_client: httpx.AsyncClient | None = http_client
    if effective_http_client is not None:
        if not isinstance(effective_http_client, httpx.AsyncClient):
            raise InvalidGatewaySettingsError(
                "create_async_client 'http_client' must be an httpx.AsyncClient instance"
            )
        validate_http_client_origin(effective_http_client, settings.base_url)
    elif not settings.verify_ssl:
        effective_http_client = DefaultAsyncHttpxClient(verify=False)

    return AsyncOpenAI(
        api_key=options.api_key,
        base_url=options.base_url,
        timeout=options.timeout,
        max_retries=options.max_retries,
        default_headers=options.default_headers,
        http_client=effective_http_client,
    )
