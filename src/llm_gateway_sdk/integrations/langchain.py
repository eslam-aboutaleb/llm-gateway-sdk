"""Layer 4: Optional ``langchain-openai`` integration (`llm-gateway-sdk[langchain]`).

Depends inward on Layers 0-2 (``exceptions``, ``validation``, ``settings``) and
eliminates duplication between chat and embedding model factories.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from llm_gateway_sdk.exceptions import (
    InvalidGatewaySettingsError,
    MissingGatewayConfigError,
)
from llm_gateway_sdk.settings import GatewaySettings
from llm_gateway_sdk.validation import (
    validate_embedding_dimensions,
    validate_http_client_origin,
    validate_max_retries,
    validate_optional_str,
    validate_timeout,
)

if TYPE_CHECKING:
    import httpx
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

__all__ = [
    "create_chat_model",
    "create_embeddings_model",
]


def _import_langchain_openai() -> tuple[type[ChatOpenAI], type[OpenAIEmbeddings]]:
    try:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "langchain-openai is required for llm_gateway_sdk.integrations.langchain. "
            "Install it with: pip install 'llm-gateway-sdk[langchain]'"
        ) from exc
    return ChatOpenAI, OpenAIEmbeddings


def _build_common_langchain_kwargs(
    settings: GatewaySettings,
    *,
    resolved_model: str,
    timeout: float | httpx.Timeout | None,
    max_retries: int | None,
    default_headers: Mapping[str, str] | None,
    http_client: httpx.Client | None,
    http_async_client: httpx.AsyncClient | None,
    extra_kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Validate and construct common keyword arguments for ``ChatOpenAI`` & ``OpenAIEmbeddings``."""
    effective_timeout = settings.timeout if timeout is None else validate_timeout(timeout)
    effective_retries = (
        settings.max_retries if max_retries is None else validate_max_retries(max_retries)
    )
    headers = settings.build_default_headers(extra_headers=default_headers)

    if http_client is not None:
        validate_http_client_origin(http_client, settings.base_url)
    if http_async_client is not None:
        validate_http_client_origin(http_async_client, settings.base_url)

    init_kwargs: dict[str, Any] = {
        "model": resolved_model,
        "api_key": settings.api_key,
        "base_url": settings.base_url,
        "timeout": effective_timeout,
        "max_retries": effective_retries,
        **extra_kwargs,
    }
    if headers:
        init_kwargs["default_headers"] = headers
    if http_client is not None:
        init_kwargs["http_client"] = http_client
    if http_async_client is not None:
        init_kwargs["http_async_client"] = http_async_client
    return init_kwargs


def create_chat_model(
    settings: GatewaySettings,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    streaming: bool = False,
    timeout: float | httpx.Timeout | None = None,
    max_retries: int | None = None,
    default_headers: Mapping[str, str] | None = None,
    http_client: httpx.Client | None = None,
    http_async_client: httpx.AsyncClient | None = None,
    **kwargs: Any,
) -> ChatOpenAI:
    """Create a configured ``langchain_openai.ChatOpenAI`` model pointing at the LiteLLM Gateway."""
    if not isinstance(settings, GatewaySettings):
        raise InvalidGatewaySettingsError(
            "create_chat_model requires a valid GatewaySettings instance"
        )

    ChatOpenAI, _ = _import_langchain_openai()

    resolved_model = validate_optional_str(model, field_name="model") or settings.default_model
    if not resolved_model:
        raise MissingGatewayConfigError(
            "Model alias is required: pass 'model=...' or set 'default_model' on GatewaySettings"
        )

    init_kwargs = _build_common_langchain_kwargs(
        settings,
        resolved_model=resolved_model,
        timeout=timeout,
        max_retries=max_retries,
        default_headers=default_headers,
        http_client=http_client,
        http_async_client=http_async_client,
        extra_kwargs={"streaming": streaming, **kwargs},
    )
    if temperature is not None:
        init_kwargs["temperature"] = temperature
    if max_tokens is not None:
        existing_extra_body = dict(init_kwargs.get("extra_body") or {})
        existing_extra_body.setdefault("max_tokens", max_tokens)
        init_kwargs["extra_body"] = existing_extra_body

    return ChatOpenAI(**init_kwargs)


def create_embeddings_model(
    settings: GatewaySettings,
    *,
    model: str | None = None,
    dimensions: int | None = None,
    timeout: float | httpx.Timeout | None = None,
    max_retries: int | None = None,
    default_headers: Mapping[str, str] | None = None,
    http_client: httpx.Client | None = None,
    http_async_client: httpx.AsyncClient | None = None,
    check_embedding_ctx_length: bool = False,
    **kwargs: Any,
) -> OpenAIEmbeddings:
    """Create a configured ``langchain_openai.OpenAIEmbeddings`` model for the LiteLLM Gateway."""
    if not isinstance(settings, GatewaySettings):
        raise InvalidGatewaySettingsError(
            "create_embeddings_model requires a valid GatewaySettings instance"
        )

    _, OpenAIEmbeddings = _import_langchain_openai()

    resolved_model = (
        validate_optional_str(model, field_name="model") or settings.default_embedding_model
    )
    if not resolved_model:
        raise MissingGatewayConfigError(
            "Embedding model alias is required: pass 'model=...' "
            "or set 'default_embedding_model' on GatewaySettings"
        )

    resolved_dimensions = (
        settings.embedding_dimensions
        if dimensions is None
        else validate_embedding_dimensions(dimensions)
    )
    init_kwargs = _build_common_langchain_kwargs(
        settings,
        resolved_model=resolved_model,
        timeout=timeout,
        max_retries=max_retries,
        default_headers=default_headers,
        http_client=http_client,
        http_async_client=http_async_client,
        extra_kwargs={"check_embedding_ctx_length": check_embedding_ctx_length, **kwargs},
    )
    if resolved_dimensions is not None:
        init_kwargs["dimensions"] = resolved_dimensions

    return OpenAIEmbeddings(**init_kwargs)
