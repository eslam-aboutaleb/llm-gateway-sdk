"""Layer 2: Immutable ``GatewaySettings`` domain configuration model and environment loader.

Depends inward on Layer 0 (``constants``, ``exceptions``) and Layer 1 (``validation``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import httpx

from llm_gateway_sdk.constants import (
    ATTRIBUTION_APP_HEADER,
    ATTRIBUTION_ENV_HEADER,
    ATTRIBUTION_TITLE_HEADER,
    DEFAULT_ENV_PREFIX,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VERIFY_SSL,
    LEGACY_LITELLM_MASTER_KEY_ENV,
    REDACTED_SECRET,
)
from llm_gateway_sdk.exceptions import MissingGatewayConfigError
from llm_gateway_sdk.validation import (
    parse_bool_env,
    validate_api_key,
    validate_base_url,
    validate_default_headers,
    validate_embedding_dimensions,
    validate_max_retries,
    validate_optional_str,
    validate_timeout,
    validate_verify_ssl,
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI, OpenAI

__all__ = ["REDACTED_SECRET", "GatewaySettings"]


class _EnvironmentLookup:
    """Single-responsibility helper for reading gateway variables from an environment mapping."""

    def __init__(
        self,
        environ: Mapping[str, str],
        *,
        prefix: str,
        allow_legacy_litellm_env: bool,
    ) -> None:
        self._env = environ
        self._prefix = prefix
        self._allow_legacy = allow_legacy_litellm_env

    def get(self, suffix: str, *legacy_names: str) -> str | None:
        """Read ``{prefix}{suffix}``, falling back to ``legacy_names`` only if opted in."""
        primary_val = self._env.get(f"{self._prefix}{suffix}")
        if primary_val is not None and primary_val.strip() != "":
            return primary_val
        if self._allow_legacy:
            for legacy_name in legacy_names:
                legacy_val = self._env.get(legacy_name)
                if legacy_val is not None and legacy_val.strip() != "":
                    return legacy_val
        return None

    def require(self, suffix: str, legacy_name: str, override_val: Any) -> str:
        """Resolve a required setting from override or environment, raising if absent."""
        if override_val is not None:
            return str(override_val) if not isinstance(override_val, str) else override_val
        resolved = self.get(suffix, legacy_name)
        if resolved is None:
            legacy_hint = f" or '{legacy_name}'" if self._allow_legacy else ""
            raise MissingGatewayConfigError(
                f"Missing required environment variable '{self._prefix}{suffix}'{legacy_hint}"
            )
        return resolved


@dataclass(frozen=True)
class GatewaySettings:
    """Standardized, immutable configuration for connecting to a LiteLLM Gateway.

    Attributes:
        base_url: Gateway OpenAI-compatible HTTP(S) base URL (e.g. ``https://gateway.example.com/v1``).
        api_key: Consumer virtual API key issued by the gateway administrator.
            Never logged, printed in ``repr()``, or included in validation errors.
        default_model: Optional default chat completion model alias (e.g. ``general-fast``).
        default_embedding_model: Optional default embedding model alias (e.g. ``rag-embedding``).
        embedding_dimensions: Optional positive integer embedding dimensions (e.g. ``1536``).
        timeout: Request timeout in seconds (default ``30.0``) or ``httpx.Timeout``.
        max_retries: Automatic client retry count (default ``0`` to avoid multiplying
            gateway-level retries).
        app_name: Optional application identifier included in safe attribution headers.
        environment: Optional deployment environment identifier (e.g. ``production``).
        default_headers: Optional mapping of explicit HTTP headers to attach to requests.
        verify_ssl: Whether TLS certificate verification is enabled (default ``True``).
    """

    base_url: str
    api_key: str = field(repr=False)
    default_model: str | None = None
    default_embedding_model: str | None = None
    embedding_dimensions: int | None = None
    timeout: float | httpx.Timeout = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    app_name: str | None = None
    environment: str | None = None
    default_headers: Mapping[str, str] | None = None
    verify_ssl: bool = DEFAULT_VERIFY_SSL

    def __post_init__(self) -> None:
        validated_headers = validate_default_headers(self.default_headers)
        object.__setattr__(
            self, "base_url", validate_base_url(self.base_url, field_name="base_url")
        )
        object.__setattr__(self, "api_key", validate_api_key(self.api_key))
        object.__setattr__(
            self,
            "default_model",
            validate_optional_str(self.default_model, field_name="default_model"),
        )
        object.__setattr__(
            self,
            "default_embedding_model",
            validate_optional_str(
                self.default_embedding_model, field_name="default_embedding_model"
            ),
        )
        object.__setattr__(
            self,
            "embedding_dimensions",
            validate_embedding_dimensions(self.embedding_dimensions),
        )
        object.__setattr__(self, "timeout", validate_timeout(self.timeout))
        object.__setattr__(self, "max_retries", validate_max_retries(self.max_retries))
        object.__setattr__(
            self, "app_name", validate_optional_str(self.app_name, field_name="app_name")
        )
        object.__setattr__(
            self,
            "environment",
            validate_optional_str(self.environment, field_name="environment"),
        )
        object.__setattr__(
            self,
            "default_headers",
            MappingProxyType(validated_headers) if validated_headers else None,
        )
        object.__setattr__(self, "verify_ssl", validate_verify_ssl(self.verify_ssl))

    def __repr__(self) -> str:
        headers_repr = dict(self.default_headers) if self.default_headers else None
        return (
            f"GatewaySettings("
            f"base_url={self.base_url!r}, "
            f"api_key={REDACTED_SECRET!r}, "
            f"default_model={self.default_model!r}, "
            f"default_embedding_model={self.default_embedding_model!r}, "
            f"embedding_dimensions={self.embedding_dimensions!r}, "
            f"timeout={self.timeout!r}, "
            f"max_retries={self.max_retries!r}, "
            f"app_name={self.app_name!r}, "
            f"environment={self.environment!r}, "
            f"default_headers={headers_repr!r}, "
            f"verify_ssl={self.verify_ssl!r}"
            f")"
        )

    def __str__(self) -> str:
        return self.__repr__()

    def to_dict(self, *, redact_secrets: bool = True) -> dict[str, Any]:
        """Serialize settings to a dictionary, redacting ``api_key`` by default."""
        return {
            "base_url": self.base_url,
            "api_key": REDACTED_SECRET if redact_secrets else self.api_key,
            "default_model": self.default_model,
            "default_embedding_model": self.default_embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "app_name": self.app_name,
            "environment": self.environment,
            "default_headers": dict(self.default_headers) if self.default_headers else None,
            "verify_ssl": self.verify_ssl,
        }

    def connection_options(self, *, strip_trailing_slash: bool = True) -> dict[str, str]:
        """Return ``{"api_base": ..., "api_key": ...}`` for compatibility adapters."""
        base = self.base_url.rstrip("/") if strip_trailing_slash else self.base_url
        return {"api_base": base, "api_key": self.api_key}

    def build_default_headers(
        self,
        extra_headers: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        """Construct the merged HTTP headers dictionary for client requests."""
        merged: dict[str, str] = {}
        if self.app_name:
            merged[ATTRIBUTION_APP_HEADER] = self.app_name
            merged[ATTRIBUTION_TITLE_HEADER] = self.app_name
        if self.environment:
            merged[ATTRIBUTION_ENV_HEADER] = self.environment
        if self.default_headers:
            merged.update(self.default_headers)
        if extra_headers is not None:
            merged.update(validate_default_headers(extra_headers))
        return merged

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        prefix: str = DEFAULT_ENV_PREFIX,
        allow_legacy_litellm_env: bool = False,
        **overrides: Any,
    ) -> GatewaySettings:
        """Load :class:`GatewaySettings` from an environment mapping."""
        env: Mapping[str, str] = os.environ if environ is None else environ
        lookup = _EnvironmentLookup(
            env, prefix=prefix, allow_legacy_litellm_env=allow_legacy_litellm_env
        )

        base_url = lookup.require("BASE_URL", "LITELLM_API_BASE", overrides.pop("base_url", None))
        raw_api_key = lookup.require("API_KEY", "LITELLM_API_KEY", overrides.pop("api_key", None))
        validated_key = validate_api_key(
            raw_api_key,
            disallow_master_key=env.get(LEGACY_LITELLM_MASTER_KEY_ENV),
        )

        default_model = overrides.pop("default_model", lookup.get("DEFAULT_MODEL", "LITELLM_MODEL"))
        default_embedding_model = overrides.pop(
            "default_embedding_model",
            lookup.get("DEFAULT_EMBEDDING_MODEL", "LITELLM_EMBEDDING_MODEL"),
        )
        embedding_dimensions = overrides.pop(
            "embedding_dimensions",
            lookup.get(
                "EMBEDDING_DIMENSIONS",
                "LITELLM_EMBEDDING_DIMENSIONS",
                "RAG_EMBEDDING_DIMENSIONS",
            ),
        )

        raw_timeout = overrides.pop("timeout", env.get(f"{prefix}TIMEOUT"))
        timeout: float | httpx.Timeout = (
            DEFAULT_TIMEOUT_SECONDS
            if raw_timeout is None or raw_timeout == ""
            else validate_timeout(raw_timeout)
        )

        raw_retries = overrides.pop("max_retries", env.get(f"{prefix}MAX_RETRIES"))
        max_retries: int = (
            DEFAULT_MAX_RETRIES
            if raw_retries is None or raw_retries == ""
            else validate_max_retries(raw_retries)
        )

        app_name = overrides.pop("app_name", lookup.get("APP_NAME"))
        environment = overrides.pop("environment", lookup.get("ENVIRONMENT"))
        default_headers = overrides.pop("default_headers", None)

        raw_verify_ssl = overrides.pop("verify_ssl", env.get(f"{prefix}VERIFY_SSL"))
        verify_ssl = _resolve_verify_ssl(raw_verify_ssl, var_name=f"{prefix}VERIFY_SSL")

        if overrides:
            unknown = ", ".join(sorted(overrides))
            raise TypeError(f"Unexpected keyword arguments for GatewaySettings.from_env: {unknown}")

        return cls(
            base_url=base_url,
            api_key=validated_key,
            default_model=default_model,
            default_embedding_model=default_embedding_model,
            embedding_dimensions=embedding_dimensions,
            timeout=timeout,
            max_retries=max_retries,
            app_name=app_name,
            environment=environment,
            default_headers=default_headers,
            verify_ssl=verify_ssl,
        )

    def create_client(
        self,
        *,
        timeout: float | httpx.Timeout | None = None,
        max_retries: int | None = None,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> OpenAI:
        """Create a synchronous native :class:`openai.OpenAI` client configured for the gateway."""
        from llm_gateway_sdk.clients import create_client

        return create_client(
            self,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            http_client=http_client,
        )

    def create_async_client(
        self,
        *,
        timeout: float | httpx.Timeout | None = None,
        max_retries: int | None = None,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> AsyncOpenAI:
        """Create an asynchronous native :class:`openai.AsyncOpenAI` client for the gateway."""
        from llm_gateway_sdk.clients import create_async_client

        return create_async_client(
            self,
            timeout=timeout,
            max_retries=max_retries,
            default_headers=default_headers,
            http_client=http_client,
        )


def _resolve_verify_ssl(raw_value: Any, *, var_name: str) -> bool:
    """Resolve optional ``verify_ssl`` from environment or boolean override."""
    if raw_value is None or raw_value == "":
        return DEFAULT_VERIFY_SSL
    if isinstance(raw_value, str):
        return parse_bool_env(raw_value, var_name=var_name)
    return validate_verify_ssl(raw_value)
