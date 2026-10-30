"""Optional ``pydantic-settings`` integration (`llm-gateway-sdk[settings]`)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

try:
    from pydantic import (
        AliasChoices,
        Field,
        SecretStr,
        ValidationError,
        field_validator,
        model_validator,
    )
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pydantic-settings is required for llm_gateway_sdk.integrations.pydantic_settings. "
        "Install it with: pip install 'llm-gateway-sdk[settings]'"
    ) from exc

from llm_gateway_sdk.exceptions import MissingGatewayConfigError
from llm_gateway_sdk.settings import GatewaySettings
from llm_gateway_sdk.validation import validate_base_url

if TYPE_CHECKING:
    import httpx
    from openai import AsyncOpenAI, OpenAI

__all__ = [
    "GatewayBaseSettings",
    "connection_options",
]


def _secret_value(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    val = secret.get_secret_value()
    return val if val != "" else None


class GatewayBaseSettings(BaseSettings):
    """Reusable Pydantic ``BaseSettings`` class for LiteLLM Gateway configuration.

    Supports both the standard ``LLM_GATEWAY_*`` environment variables and legacy
    ``LITELLM_*`` environment variables for drop-in compatibility across services.
    All validation errors redact raw input values so credentials never leak through
    ``ValidationError.errors()`` or ``ValidationError.json()``.
    """

    gateway_base: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_GATEWAY_BASE_URL", "LITELLM_API_BASE"),
    )
    gateway_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_GATEWAY_API_KEY", "LITELLM_API_KEY"),
    )
    gateway_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_GATEWAY_DEFAULT_MODEL", "LITELLM_MODEL"),
    )
    embedding_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL",
            "LITELLM_EMBEDDING_MODEL",
        ),
    )
    embedding_key: SecretStr | None = Field(
        default=None,
        validation_alias="LITELLM_EMBEDDING_API_KEY",
    )
    embedding_base: SecretStr | None = Field(
        default=None,
        validation_alias="LITELLM_EMBEDDING_API_BASE",
    )
    embedding_dimensions: int | None = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices(
            "LLM_GATEWAY_EMBEDDING_DIMENSIONS",
            "LITELLM_EMBEDDING_DIMENSIONS",
            "RAG_EMBEDDING_DIMENSIONS",
        ),
    )
    gateway_timeout: float = Field(
        default=30.0,
        gt=0,
        validation_alias="LLM_GATEWAY_TIMEOUT",
    )
    gateway_max_retries: int = Field(
        default=0,
        ge=0,
        validation_alias="LLM_GATEWAY_MAX_RETRIES",
    )
    gateway_app_name: str | None = Field(
        default=None,
        validation_alias="LLM_GATEWAY_APP_NAME",
    )
    gateway_environment: str | None = Field(
        default=None,
        validation_alias="LLM_GATEWAY_ENVIRONMENT",
    )

    model_config = SettingsConfigDict(
        populate_by_name=True,
        hide_input_in_errors=True,
        extra="ignore",
    )

    @field_validator("embedding_dimensions", mode="before")
    @classmethod
    def empty_dimensions_are_unset(cls, value: Any) -> Any:
        return None if value == "" else value

    @model_validator(mode="wrap")
    @classmethod
    def redact_validation_errors(cls, values: Any, handler: Any) -> Any:
        """Ensure Pydantic's errors()/json() never retain credential-bearing inputs."""
        try:
            return handler(values)
        except ValidationError as exc:
            raise ValidationError.from_exception_data(
                cls.__name__,
                [
                    {
                        "type": "value_error",
                        "loc": error["loc"],
                        "input": "[redacted]",
                        "ctx": {"error": ValueError("Invalid configuration value")},
                    }
                    for error in exc.errors()
                ],
                hide_input=True,
            ) from None

    @field_validator("gateway_base", "embedding_base")
    @classmethod
    def validate_endpoint(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or value.get_secret_value() == "":
            return value
        raw = value.get_secret_value()
        try:
            validate_base_url(raw, field_name="gateway_base")
        except ValueError as exc:
            raise ValueError(
                "Endpoint must be an HTTP(S) URL without credentials, query or fragment"
            ) from exc
        return value

    def to_gateway_settings(
        self,
        *,
        default_model_fallback: str | None = None,
        default_embedding_model_fallback: str | None = None,
        default_headers: Mapping[str, str] | None = None,
        verify_ssl: bool = True,
    ) -> GatewaySettings:
        """Convert this Pydantic settings instance into an immutable :class:`GatewaySettings`."""
        base = _secret_value(self.gateway_base)
        key = _secret_value(self.gateway_key)
        if not base or not key:
            raise MissingGatewayConfigError(
                "LLM_GATEWAY_BASE_URL/LITELLM_API_BASE and "
                "LLM_GATEWAY_API_KEY/LITELLM_API_KEY are required"
            )
        return GatewaySettings(
            base_url=base.rstrip("/"),
            api_key=key,
            default_model=self.gateway_model or default_model_fallback,
            default_embedding_model=self.embedding_model or default_embedding_model_fallback,
            embedding_dimensions=self.embedding_dimensions,
            timeout=self.gateway_timeout,
            max_retries=self.gateway_max_retries,
            app_name=self.gateway_app_name,
            environment=self.gateway_environment,
            default_headers=default_headers,
            verify_ssl=verify_ssl,
        )

    def create_gateway_client(
        self,
        *,
        timeout: float | httpx.Timeout | None = None,
        max_retries: int | None = None,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> OpenAI:
        """Create a synchronous :class:`openai.OpenAI` client from these settings."""
        return self.to_gateway_settings().create_client(
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            http_client=http_client,
        )

    def create_async_gateway_client(
        self,
        *,
        timeout: float | httpx.Timeout | None = None,
        max_retries: int | None = None,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> AsyncOpenAI:
        """Create an asynchronous :class:`openai.AsyncOpenAI` client from these settings."""
        return self.to_gateway_settings().create_async_client(
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            http_client=http_client,
        )


def connection_options(
    settings: GatewayBaseSettings,
    *,
    embedding: bool = False,  # noqa: ARG001 - preserved for consumer compatibility
) -> dict[str, str]:
    """Extract normalized ``{"api_base": ..., "api_key": ...}`` from ``GatewayBaseSettings``.

    Embeddings always use ``gateway_base`` and ``gateway_key``; legacy embedding
    endpoint overrides cannot bypass the primary gateway.
    """
    base = _secret_value(settings.gateway_base)
    key = _secret_value(settings.gateway_key)
    if not base or not key:
        raise MissingGatewayConfigError("LITELLM_API_BASE and LITELLM_API_KEY are required")
    return {"api_base": base.rstrip("/"), "api_key": key}
