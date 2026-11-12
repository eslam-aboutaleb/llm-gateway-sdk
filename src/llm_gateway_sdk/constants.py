"""Layer 0: Domain constants and immutable defaults for ``llm_gateway_sdk``.

Centralizes all default values, environment variable names, attribution headers,
and security blocklists to eliminate magic strings and magic numbers across layers.
"""

from __future__ import annotations

__all__ = [
    "ALLOWED_URL_SCHEMES",
    "ATTRIBUTION_APP_HEADER",
    "ATTRIBUTION_ENV_HEADER",
    "ATTRIBUTION_TITLE_HEADER",
    "DEFAULT_ENV_PREFIX",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_VERIFY_SSL",
    "FORBIDDEN_HEADER_NAMES",
    "LEGACY_LITELLM_MASTER_KEY_ENV",
    "REDACTED_SECRET",
]

#: Placeholder string used whenever a secret value is redacted in repr/str/logs/dicts.
REDACTED_SECRET: str = "[REDACTED]"  # noqa: S105

#: Default request timeout in seconds when not explicitly specified.
DEFAULT_TIMEOUT_SECONDS: float = 30.0

#: Default client retry count (0 because the LiteLLM Gateway handles upstream retries).
DEFAULT_MAX_RETRIES: int = 0

#: Default TLS certificate verification setting.
DEFAULT_VERIFY_SSL: bool = True

#: Default environment variable prefix for ``GatewaySettings.from_env()``.
DEFAULT_ENV_PREFIX: str = "LLM_GATEWAY_"

#: Environment variable name for the LiteLLM administrative master key (never allowed in consumers).
LEGACY_LITELLM_MASTER_KEY_ENV: str = "LITELLM_MASTER_KEY"

#: Allowed URL schemes for gateway endpoints.
ALLOWED_URL_SCHEMES: frozenset[str] = frozenset({"http", "https"})

#: HTTP header names used for safe consumer request attribution.
ATTRIBUTION_APP_HEADER: str = "X-Gateway-App-Name"
ATTRIBUTION_TITLE_HEADER: str = "X-Title"
ATTRIBUTION_ENV_HEADER: str = "X-Gateway-Environment"

#: Security-sensitive HTTP headers that custom ``default_headers`` must never override.
FORBIDDEN_HEADER_NAMES: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "host",
        "content-length",
    }
)
