"""Layer 3: Provider-agnostic synchronous and asynchronous HTTP/SSE gateway clients.

Built directly on ``httpx`` with zero dependency on ``openai``, ``langchain``, or any
other vendor/framework SDK. Supports chat completions, real-time SSE streaming,
tool calling, vector embeddings, and model discovery against LiteLLM Gateways.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, overload

import httpx

from llm_gateway_sdk.constants import REDACTED_SECRET
from llm_gateway_sdk.exceptions import (
    GatewayAPIStatusError,
    GatewayAuthenticationError,
    GatewayBadRequestError,
    GatewayConnectionError,
    GatewayInternalServerError,
    GatewayNotFoundError,
    GatewayPermissionDeniedError,
    GatewayRateLimitError,
    GatewayTimeoutError,
    GatewayUnprocessableEntityError,
    InvalidGatewaySettingsError,
    MissingGatewayConfigError,
)
from llm_gateway_sdk.models import (
    AsyncGatewayStream,
    ChatResponse,
    EmbeddingResponse,
    GatewayStream,
    ModelListResponse,
    RawGatewayResponse,
)
from llm_gateway_sdk.settings import GatewaySettings
from llm_gateway_sdk.validation import (
    validate_default_headers,
    validate_embedding_dimensions,
    validate_http_client_origin,
    validate_max_retries,
    validate_optional_str,
    validate_timeout,
)

__all__ = [
    "AsyncGatewayClient",
    "GatewayClient",
    "create_async_client",
    "create_client",
]

_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class _ResolvedClientOptions:
    """Internal validated options shared by sync and async gateway client construction."""

    api_key: str
    base_url: str
    timeout: float | httpx.Timeout
    max_retries: int
    default_headers: dict[str, str]
    verify_ssl: bool


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
        default_headers=headers,
        verify_ssl=settings.verify_ssl,
    )


def _resolve_endpoint_url(base_url: str, route: str) -> str:
    """Resolve an inference or health route against ``base_url`` without duplicating ``/v1``."""
    clean_base = base_url.rstrip("/")
    clean_route = "/" + route.lstrip("/")

    if clean_route in {"/health", "/ready", "/status"}:
        root_base = clean_base[:-3] if clean_base.endswith("/v1") else clean_base
        return f"{root_base}{clean_route}"

    if clean_route.startswith("/v1/"):
        if clean_base.endswith("/v1"):
            return f"{clean_base}{clean_route[3:]}"
        return f"{clean_base}{clean_route}"

    return f"{clean_base}{clean_route}"


def _extract_error_message(response: httpx.Response, secret_to_redact: str) -> tuple[str, Any]:
    """Extract a sanitized error message and parsed body from a non-2xx gateway response."""
    body: Any = None
    message = f"Gateway returned HTTP {response.status_code}"
    try:
        body = response.json()
        if isinstance(body, dict):
            err_obj = body.get("error")
            if isinstance(err_obj, dict) and isinstance(err_obj.get("message"), str):
                message = err_obj["message"]
            elif isinstance(err_obj, str):
                message = err_obj
            elif isinstance(body.get("detail"), str):
                message = body["detail"]
    except ValueError:
        text = response.text.strip()
        if text:
            body = text
            message = text[:200]

    if secret_to_redact and secret_to_redact in message:
        message = message.replace(secret_to_redact, REDACTED_SECRET)
    return message, body


def _map_status_error(response: httpx.Response, *, secret_to_redact: str) -> GatewayAPIStatusError:
    """Map an HTTP status code to the corresponding :class:`GatewayAPIStatusError` subclass."""
    status = response.status_code
    request_id = response.headers.get("x-request-id")
    message, body = _extract_error_message(response, secret_to_redact)

    status_map: dict[int, type[GatewayAPIStatusError]] = {
        400: GatewayBadRequestError,
        401: GatewayAuthenticationError,
        403: GatewayPermissionDeniedError,
        404: GatewayNotFoundError,
        422: GatewayUnprocessableEntityError,
        429: GatewayRateLimitError,
    }
    exc_cls = status_map.get(status)
    if exc_cls is None:
        exc_cls = GatewayInternalServerError if status >= 500 else GatewayAPIStatusError

    return exc_cls(
        message,
        status_code=status,
        request_id=request_id,
        headers=response.headers,
        body=body,
    )


def _build_chat_payload(
    *,
    resolved_model: str,
    messages: Sequence[Mapping[str, Any]],
    stream: bool,
    temperature: float | None,
    max_tokens: int | None,
    tools: Sequence[Mapping[str, Any]] | None,
    tool_choice: str | Mapping[str, Any] | None,
    response_format: Mapping[str, Any] | None,
    extra_body: Mapping[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Construct the JSON payload for ``POST /v1/chat/completions``."""
    payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": [dict(m) for m in messages],
    }
    if stream:
        payload["stream"] = True
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if tools is not None:
        payload["tools"] = [dict(t) for t in tools]
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if response_format is not None:
        payload["response_format"] = dict(response_format)
    if extra_body is not None:
        payload.update(extra_body)
    payload.update(kwargs)
    return payload


def _build_embeddings_payload(
    *,
    resolved_model: str,
    input_data: str | Sequence[str],
    dimensions: int | None,
    extra_body: Mapping[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Construct the JSON payload for ``POST /v1/embeddings``."""
    payload: dict[str, Any] = {
        "model": resolved_model,
        "input": list(input_data) if not isinstance(input_data, str) else input_data,
    }
    if dimensions is not None:
        payload["dimensions"] = dimensions
    if extra_body is not None:
        payload.update(extra_body)
    payload.update(kwargs)
    return payload


def _prepare_chat_payload(
    settings: GatewaySettings,
    *,
    model: str | None,
    messages: Sequence[Mapping[str, Any]],
    stream: bool,
    temperature: float | None,
    max_tokens: int | None,
    tools: Sequence[Mapping[str, Any]] | None,
    tool_choice: str | Mapping[str, Any] | None,
    response_format: Mapping[str, Any] | None,
    extra_body: Mapping[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Validate chat model and construct the JSON payload for ``POST /v1/chat/completions``."""
    resolved_model = validate_optional_str(model, field_name="model") or settings.default_model
    if not resolved_model:
        raise MissingGatewayConfigError(
            "Model alias is required: pass 'model=...' or set 'default_model' on GatewaySettings"
        )
    return _build_chat_payload(
        resolved_model=resolved_model,
        messages=messages,
        stream=stream,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        tool_choice=tool_choice,
        response_format=response_format,
        extra_body=extra_body,
        kwargs=kwargs,
    )


def _prepare_embeddings_payload(
    settings: GatewaySettings,
    *,
    model: str | None,
    input_data: str | Sequence[str],
    dimensions: int | None,
    extra_body: Mapping[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    """Validate embedding model/dimensions and construct payload for ``POST /v1/embeddings``."""
    resolved_model = (
        validate_optional_str(model, field_name="model") or settings.default_embedding_model
    )
    if not resolved_model:
        raise MissingGatewayConfigError(
            "Embedding model alias is required: pass 'model=...' "
            "or set 'default_embedding_model' on GatewaySettings"
        )
    resolved_dims = (
        settings.embedding_dimensions
        if dimensions is None
        else validate_embedding_dimensions(dimensions)
    )
    return _build_embeddings_payload(
        resolved_model=resolved_model,
        input_data=input_data,
        dimensions=resolved_dims,
        extra_body=extra_body,
        kwargs=kwargs,
    )


def _wrap_raw_response(response: httpx.Response, model_cls: Any) -> RawGatewayResponse[Any]:
    """Parse an HTTP JSON response into ``model_cls`` wrapped in :class:`RawGatewayResponse`."""
    req_id = response.headers.get("x-request-id")
    data = response.json()
    if isinstance(data, dict) and req_id is not None:
        data = {**data, "request_id": req_id}
    parsed = model_cls.model_validate(data)
    return RawGatewayResponse(
        status_code=response.status_code,
        headers=response.headers,
        request_id=req_id,
        parsed=parsed,
    )


class _RawChatCompletionsResource:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client

    def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[ChatResponse]:
        return self._client._complete_raw(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _ChatCompletionsResource:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client
        self.with_raw_response = _RawChatCompletionsResource(client)

    @overload
    def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        stream: Literal[False] = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> ChatResponse: ...

    @overload
    def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        stream: Literal[True],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> GatewayStream: ...

    def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> ChatResponse | GatewayStream:
        if stream:
            return self._client.stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                response_format=response_format,
                extra_headers=extra_headers,
                extra_body=extra_body,
                timeout=timeout,
                **kwargs,
            )
        return self._client.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _ChatNamespace:
    def __init__(self, client: GatewayClient) -> None:
        self.completions = _ChatCompletionsResource(client)


class _RawEmbeddingsResource:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client

    def create(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[EmbeddingResponse]:
        return self._client._embed_raw(
            input=input,
            model=model,
            dimensions=dimensions,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _EmbeddingsResource:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client
        self.with_raw_response = _RawEmbeddingsResource(client)

    def create(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        return self._client.embed(
            input=input,
            model=model,
            dimensions=dimensions,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _RawModelsResource:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client

    def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> RawGatewayResponse[ModelListResponse]:
        return self._client._list_models_raw(extra_headers=extra_headers, timeout=timeout)


class _ModelsResource:
    def __init__(self, client: GatewayClient) -> None:
        self._client = client
        self.with_raw_response = _RawModelsResource(client)

    def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> ModelListResponse:
        return self._client.list_models(extra_headers=extra_headers, timeout=timeout)


# ── Asynchronous Resource Helpers ──────────────────────────────────────────


class _AsyncRawChatCompletionsResource:
    def __init__(self, client: AsyncGatewayClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[ChatResponse]:
        return await self._client._complete_raw(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _AsyncChatCompletionsResource:
    def __init__(self, client: AsyncGatewayClient) -> None:
        self._client = client
        self.with_raw_response = _AsyncRawChatCompletionsResource(client)

    @overload
    async def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        stream: Literal[False] = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> ChatResponse: ...

    @overload
    async def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        stream: Literal[True],
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> AsyncGatewayStream: ...

    async def create(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        stream: bool = False,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGatewayStream:
        if stream:
            return await self._client.stream(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                response_format=response_format,
                extra_headers=extra_headers,
                extra_body=extra_body,
                timeout=timeout,
                **kwargs,
            )
        return await self._client.complete(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _AsyncChatNamespace:
    def __init__(self, client: AsyncGatewayClient) -> None:
        self.completions = _AsyncChatCompletionsResource(client)


class _AsyncRawEmbeddingsResource:
    def __init__(self, client: AsyncGatewayClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[EmbeddingResponse]:
        return await self._client._embed_raw(
            input=input,
            model=model,
            dimensions=dimensions,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _AsyncEmbeddingsResource:
    def __init__(self, client: AsyncGatewayClient) -> None:
        self._client = client
        self.with_raw_response = _AsyncRawEmbeddingsResource(client)

    async def create(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        return await self._client.embed(
            input=input,
            model=model,
            dimensions=dimensions,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )


class _AsyncRawModelsResource:
    def __init__(self, client: AsyncGatewayClient) -> None:
        self._client = client

    async def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> RawGatewayResponse[ModelListResponse]:
        return await self._client._list_models_raw(extra_headers=extra_headers, timeout=timeout)


class _AsyncModelsResource:
    def __init__(self, client: AsyncGatewayClient) -> None:
        self._client = client
        self.with_raw_response = _AsyncRawModelsResource(client)

    async def list(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> ModelListResponse:
        return await self._client.list_models(extra_headers=extra_headers, timeout=timeout)


# ── Synchronous & Asynchronous Gateway Clients ─────────────────────────────


class GatewayClient:
    """Provider-agnostic synchronous HTTP/SSE client for LiteLLM Gateways."""

    def __init__(
        self,
        settings: GatewaySettings,
        *,
        options: _ResolvedClientOptions,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._api_key = options.api_key
        self._base_url_str = options.base_url
        self.base_url = httpx.URL(options.base_url)
        self.timeout = options.timeout
        self.max_retries = options.max_retries
        self.default_headers: Mapping[str, str] = MappingProxyType(dict(options.default_headers))

        self._owns_http_client = http_client is None
        self._http_client: httpx.Client = (
            http_client
            if http_client is not None
            else httpx.Client(timeout=options.timeout, verify=options.verify_ssl)
        )

        self.chat = _ChatNamespace(self)
        self.embeddings = _EmbeddingsResource(self)
        self.models = _ModelsResource(self)

    @property
    def api_key(self) -> str:
        return self._api_key

    def __repr__(self) -> str:
        return (
            f"GatewayClient(base_url={self._base_url_str!r}, "
            f"api_key={REDACTED_SECRET!r}, "
            f"timeout={self.timeout!r}, "
            f"max_retries={self.max_retries!r})"
        )

    def _build_request_headers(
        self,
        extra_headers: Mapping[str, str] | None = None,
        *,
        include_auth: bool = True,
    ) -> dict[str, str]:
        headers = dict(self.default_headers)
        if extra_headers is not None:
            headers.update(validate_default_headers(extra_headers))
        if include_auth:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _send_json_request(
        self,
        method: str,
        route: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
        include_auth: bool = True,
    ) -> httpx.Response:
        url = _resolve_endpoint_url(self._base_url_str, route)
        headers = self._build_request_headers(extra_headers, include_auth=include_auth)
        effective_timeout = self.timeout if timeout is None else validate_timeout(timeout)

        attempts = 0
        max_attempts = 1 + self.max_retries
        while True:
            attempts += 1
            try:
                response = self._http_client.request(
                    method,
                    url,
                    json=json_body,
                    headers=headers,
                    timeout=effective_timeout,
                )
            except httpx.TimeoutException as exc:
                if attempts < max_attempts:
                    continue
                raise GatewayTimeoutError("Gateway request timed out") from exc
            except httpx.HTTPError as exc:
                if attempts < max_attempts:
                    continue
                raise GatewayConnectionError("Gateway connection failed") from exc

            if response.status_code >= 400:
                if response.status_code in _RETRYABLE_STATUS_CODES and attempts < max_attempts:
                    response.close()
                    continue
                raise _map_status_error(response, secret_to_redact=self._api_key)

            return response

    def _complete_raw(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[ChatResponse]:
        payload = _prepare_chat_payload(
            self._settings,
            model=model,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_body=extra_body,
            kwargs=kwargs,
        )
        response = self._send_json_request(
            "POST",
            "/v1/chat/completions",
            json_body=payload,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return _wrap_raw_response(response, ChatResponse)

    def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute a synchronous chat completion against ``POST /v1/chat/completions``."""
        return self._complete_raw(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        ).parse()

    def stream(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> GatewayStream:
        """Start a synchronous SSE chat completion stream against ``POST /v1/chat/completions``."""
        payload = _prepare_chat_payload(
            self._settings,
            model=model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_body=extra_body,
            kwargs=kwargs,
        )
        url = _resolve_endpoint_url(self._base_url_str, "/v1/chat/completions")
        headers = self._build_request_headers(extra_headers)
        effective_timeout = self.timeout if timeout is None else validate_timeout(timeout)

        request = self._http_client.build_request(
            "POST",
            url,
            json=payload,
            headers=headers,
            timeout=effective_timeout,
        )
        try:
            response = self._http_client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError("Gateway streaming request timed out") from exc
        except httpx.HTTPError as exc:
            raise GatewayConnectionError("Gateway streaming connection failed") from exc

        if response.status_code >= 400:
            try:
                response.read()
                raise _map_status_error(response, secret_to_redact=self._api_key)
            finally:
                response.close()

        return GatewayStream(response)

    def _embed_raw(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[EmbeddingResponse]:
        payload = _prepare_embeddings_payload(
            self._settings,
            model=model,
            input_data=input,
            dimensions=dimensions,
            extra_body=extra_body,
            kwargs=kwargs,
        )
        response = self._send_json_request(
            "POST",
            "/v1/embeddings",
            json_body=payload,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return _wrap_raw_response(response, EmbeddingResponse)

    def embed(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate single or batch vector embeddings via ``POST /v1/embeddings``."""
        return self._embed_raw(
            input=input,
            model=model,
            dimensions=dimensions,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        ).parse()

    def _list_models_raw(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> RawGatewayResponse[ModelListResponse]:
        response = self._send_json_request(
            "GET",
            "/v1/models",
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return _wrap_raw_response(response, ModelListResponse)

    def list_models(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> ModelListResponse:
        """List model aliases permitted for this virtual key via ``GET /v1/models``."""
        return self._list_models_raw(extra_headers=extra_headers, timeout=timeout).parse()

    def health(self, *, timeout: float | httpx.Timeout | None = None) -> bool:
        """Perform an unauthenticated liveness check against ``GET /health``."""
        response = self._send_json_request(
            "GET",
            "/health",
            timeout=timeout,
            include_auth=False,
        )
        return response.status_code == 200

    def post(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        cast_to: Any = dict,  # noqa: ARG002
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Any:
        """Send an authenticated POST request to a gateway path."""
        response = self._send_json_request(
            "POST",
            path,
            json_body=body or {},
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return response.json()

    def close(self) -> None:
        """Close the underlying synchronous HTTP transport."""
        self._http_client.close()

    def is_closed(self) -> bool:
        """Return True if the underlying HTTP client is closed."""
        return self._http_client.is_closed

    def __enter__(self) -> GatewayClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class AsyncGatewayClient:
    """Provider-agnostic asynchronous HTTP/SSE client for LiteLLM Gateways."""

    def __init__(
        self,
        settings: GatewaySettings,
        *,
        options: _ResolvedClientOptions,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._api_key = options.api_key
        self._base_url_str = options.base_url
        self.base_url = httpx.URL(options.base_url)
        self.timeout = options.timeout
        self.max_retries = options.max_retries
        self.default_headers: Mapping[str, str] = MappingProxyType(dict(options.default_headers))

        self._owns_http_client = http_client is None
        self._http_client: httpx.AsyncClient = (
            http_client
            if http_client is not None
            else httpx.AsyncClient(timeout=options.timeout, verify=options.verify_ssl)
        )

        self.chat = _AsyncChatNamespace(self)
        self.embeddings = _AsyncEmbeddingsResource(self)
        self.models = _AsyncModelsResource(self)

    @property
    def api_key(self) -> str:
        return self._api_key

    def __repr__(self) -> str:
        return (
            f"AsyncGatewayClient(base_url={self._base_url_str!r}, "
            f"api_key={REDACTED_SECRET!r}, "
            f"timeout={self.timeout!r}, "
            f"max_retries={self.max_retries!r})"
        )

    def _build_request_headers(
        self,
        extra_headers: Mapping[str, str] | None = None,
        *,
        include_auth: bool = True,
    ) -> dict[str, str]:
        headers = dict(self.default_headers)
        if extra_headers is not None:
            headers.update(validate_default_headers(extra_headers))
        if include_auth:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _send_json_request(
        self,
        method: str,
        route: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
        include_auth: bool = True,
    ) -> httpx.Response:
        url = _resolve_endpoint_url(self._base_url_str, route)
        headers = self._build_request_headers(extra_headers, include_auth=include_auth)
        effective_timeout = self.timeout if timeout is None else validate_timeout(timeout)

        attempts = 0
        max_attempts = 1 + self.max_retries
        while True:
            attempts += 1
            try:
                response = await self._http_client.request(
                    method,
                    url,
                    json=json_body,
                    headers=headers,
                    timeout=effective_timeout,
                )
            except httpx.TimeoutException as exc:
                if attempts < max_attempts:
                    continue
                raise GatewayTimeoutError("Gateway async request timed out") from exc
            except httpx.HTTPError as exc:
                if attempts < max_attempts:
                    continue
                raise GatewayConnectionError("Gateway async connection failed") from exc

            if response.status_code >= 400:
                if response.status_code in _RETRYABLE_STATUS_CODES and attempts < max_attempts:
                    await response.aclose()
                    continue
                raise _map_status_error(response, secret_to_redact=self._api_key)

            return response

    async def _complete_raw(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[ChatResponse]:
        payload = _prepare_chat_payload(
            self._settings,
            model=model,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_body=extra_body,
            kwargs=kwargs,
        )
        response = await self._send_json_request(
            "POST",
            "/v1/chat/completions",
            json_body=payload,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return _wrap_raw_response(response, ChatResponse)

    async def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Execute an asynchronous chat completion against ``POST /v1/chat/completions``."""
        raw = await self._complete_raw(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )
        return raw.parse()

    async def stream(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] | None = None,
        response_format: Mapping[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> AsyncGatewayStream:
        """Start an async SSE chat completion stream against ``POST /v1/chat/completions``."""
        payload = _prepare_chat_payload(
            self._settings,
            model=model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
            extra_body=extra_body,
            kwargs=kwargs,
        )
        url = _resolve_endpoint_url(self._base_url_str, "/v1/chat/completions")
        headers = self._build_request_headers(extra_headers)
        effective_timeout = self.timeout if timeout is None else validate_timeout(timeout)

        request = self._http_client.build_request(
            "POST",
            url,
            json=payload,
            headers=headers,
            timeout=effective_timeout,
        )
        try:
            response = await self._http_client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            raise GatewayTimeoutError("Gateway async streaming request timed out") from exc
        except httpx.HTTPError as exc:
            raise GatewayConnectionError("Gateway async streaming connection failed") from exc

        if response.status_code >= 400:
            try:
                await response.aread()
                raise _map_status_error(response, secret_to_redact=self._api_key)
            finally:
                await response.aclose()

        return AsyncGatewayStream(response)

    async def _embed_raw(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> RawGatewayResponse[EmbeddingResponse]:
        payload = _prepare_embeddings_payload(
            self._settings,
            model=model,
            input_data=input,
            dimensions=dimensions,
            extra_body=extra_body,
            kwargs=kwargs,
        )
        response = await self._send_json_request(
            "POST",
            "/v1/embeddings",
            json_body=payload,
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return _wrap_raw_response(response, EmbeddingResponse)

    async def embed(
        self,
        *,
        input: str | Sequence[str],
        model: str | None = None,
        dimensions: int | None = None,
        extra_headers: Mapping[str, str] | None = None,
        extra_body: Mapping[str, Any] | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate single or batch vector embeddings asynchronously via ``POST /v1/embeddings``."""
        raw = await self._embed_raw(
            input=input,
            model=model,
            dimensions=dimensions,
            extra_headers=extra_headers,
            extra_body=extra_body,
            timeout=timeout,
            **kwargs,
        )
        return raw.parse()

    async def _list_models_raw(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> RawGatewayResponse[ModelListResponse]:
        response = await self._send_json_request(
            "GET",
            "/v1/models",
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return _wrap_raw_response(response, ModelListResponse)

    async def list_models(
        self,
        *,
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> ModelListResponse:
        """List model aliases permitted for this virtual key via ``GET /v1/models``."""
        raw = await self._list_models_raw(extra_headers=extra_headers, timeout=timeout)
        return raw.parse()

    async def health(self, *, timeout: float | httpx.Timeout | None = None) -> bool:
        """Perform an unauthenticated liveness check against ``GET /health``."""
        response = await self._send_json_request(
            "GET",
            "/health",
            timeout=timeout,
            include_auth=False,
        )
        return response.status_code == 200

    async def post(
        self,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        cast_to: Any = dict,  # noqa: ARG002
        extra_headers: Mapping[str, str] | None = None,
        timeout: float | httpx.Timeout | None = None,
    ) -> Any:
        """Send an authenticated async POST request to a gateway path."""
        response = await self._send_json_request(
            "POST",
            path,
            json_body=body or {},
            extra_headers=extra_headers,
            timeout=timeout,
        )
        return response.json()

    async def close(self) -> None:
        """Close the underlying asynchronous HTTP transport."""
        await self._http_client.aclose()

    async def aclose(self) -> None:
        """Alias for :meth:`close`."""
        await self.close()

    def is_closed(self) -> bool:
        """Return True if the underlying async HTTP client is closed."""
        return self._http_client.is_closed

    async def __aenter__(self) -> AsyncGatewayClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


def create_client(
    settings: GatewaySettings,
    *,
    timeout: float | httpx.Timeout | None = None,
    max_retries: int | None = None,
    default_headers: Mapping[str, str] | None = None,
    http_client: httpx.Client | None = None,
) -> GatewayClient:
    """Create a configured synchronous :class:`GatewayClient` for the LiteLLM Gateway."""
    options = _resolve_client_options(
        settings,
        caller_name="create_client",
        timeout=timeout,
        max_retries=max_retries,
        default_headers=default_headers,
    )

    if http_client is not None:
        if not isinstance(http_client, httpx.Client):
            raise InvalidGatewaySettingsError(
                "create_client 'http_client' must be an httpx.Client instance"
            )
        validate_http_client_origin(http_client, settings.base_url)

    return GatewayClient(settings, options=options, http_client=http_client)


def create_async_client(
    settings: GatewaySettings,
    *,
    timeout: float | httpx.Timeout | None = None,
    max_retries: int | None = None,
    default_headers: Mapping[str, str] | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> AsyncGatewayClient:
    """Create a configured asynchronous :class:`AsyncGatewayClient` for the LiteLLM Gateway."""
    options = _resolve_client_options(
        settings,
        caller_name="create_async_client",
        timeout=timeout,
        max_retries=max_retries,
        default_headers=default_headers,
    )

    if http_client is not None:
        if not isinstance(http_client, httpx.AsyncClient):
            raise InvalidGatewaySettingsError(
                "create_async_client 'http_client' must be an httpx.AsyncClient instance"
            )
        validate_http_client_origin(http_client, settings.base_url)

    return AsyncGatewayClient(settings, options=options, http_client=http_client)
