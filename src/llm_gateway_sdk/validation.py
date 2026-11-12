"""Layer 1: Pure validation and security boundary functions.

Depends only on Layer 0 (``constants``, ``exceptions``), standard library, and ``httpx``.
Every function has a single responsibility, is stateless, and enforces strict security
invariants (never echoing secrets in exception messages).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any
from urllib.parse import SplitResult, urlsplit

import httpx

from llm_gateway_sdk.constants import (
    ALLOWED_URL_SCHEMES,
    FORBIDDEN_HEADER_NAMES,
)
from llm_gateway_sdk.exceptions import (
    InvalidGatewaySettingsError,
    InvalidGatewayURLError,
    MissingGatewayConfigError,
)

__all__ = [
    "parse_bool_env",
    "validate_api_key",
    "validate_base_url",
    "validate_default_headers",
    "validate_embedding_dimensions",
    "validate_http_client_origin",
    "validate_max_retries",
    "validate_optional_str",
    "validate_timeout",
    "validate_verify_ssl",
]


def _has_control_chars(value: str) -> bool:
    """Return True if ``value`` contains ASCII control characters (0..31 or 127)."""
    return any(ord(char) < 32 or ord(char) == 127 for char in value)


def _has_whitespace_or_control_chars(value: str) -> bool:
    """Return True if ``value`` contains whitespace or ASCII control characters."""
    return any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)


def _is_finite_positive_number(value: float) -> bool:
    """Return True if ``value`` is finite and strictly greater than zero."""
    return math.isfinite(value) and value > 0.0


def _is_valid_parsed_gateway_url(parsed: SplitResult, raw: str) -> bool:
    """Verify parsed URL components satisfy the gateway security contract."""
    if "\\" in raw or "?" in raw or "#" in raw:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False

    return (
        parsed.scheme in ALLOWED_URL_SCHEMES
        and bool(parsed.hostname)
        and port != 0
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and "@" not in parsed.netloc
    )


def validate_base_url(base_url: Any, *, field_name: str = "base_url") -> str:
    """Validate a gateway endpoint URL without mutating its path.

    Rules:
    - Must be a non-empty string.
    - Must use ``http`` or ``https`` scheme.
    - Must have a non-empty hostname and valid port (1..65535 if specified).
    - Must not include username/password credentials, query parameters, or fragments.
    - Must not include ASCII control characters, whitespace, ``\\``, or ``@``.
    """
    if base_url is None:
        raise MissingGatewayConfigError(
            f"Missing required gateway '{field_name}' "
            "(set LLM_GATEWAY_BASE_URL or LITELLM_API_BASE)"
        )
    if not isinstance(base_url, str):
        raise InvalidGatewayURLError(f"Gateway '{field_name}' must be a string")

    if not base_url or not base_url.strip():
        raise MissingGatewayConfigError(
            f"Missing required gateway '{field_name}' "
            "(set LLM_GATEWAY_BASE_URL or LITELLM_API_BASE)"
        )

    if _has_whitespace_or_control_chars(base_url):
        raise InvalidGatewayURLError(
            f"Gateway '{field_name}' must not contain whitespace or control characters"
        )

    try:
        parsed = urlsplit(base_url)
    except ValueError as exc:
        raise InvalidGatewayURLError(
            f"Gateway '{field_name}' must be an HTTP(S) URL without credentials, query or fragment"
        ) from exc

    if not _is_valid_parsed_gateway_url(parsed, base_url):
        raise InvalidGatewayURLError(
            f"Gateway '{field_name}' must be an HTTP(S) URL without credentials, query or fragment"
        )

    return base_url


def validate_api_key(
    api_key: Any,
    *,
    disallow_master_key: str | None = None,
) -> str:
    """Validate a consumer virtual API key without ever echoing the secret in errors."""
    if api_key is None:
        raise MissingGatewayConfigError(
            "Missing required gateway 'api_key' (set LLM_GATEWAY_API_KEY or LITELLM_API_KEY)"
        )
    if not isinstance(api_key, str):
        raise InvalidGatewaySettingsError("Gateway 'api_key' must be a string")

    stripped = api_key.strip()
    if not stripped:
        raise MissingGatewayConfigError(
            "Missing required gateway 'api_key' (set LLM_GATEWAY_API_KEY or LITELLM_API_KEY)"
        )

    if _has_whitespace_or_control_chars(stripped):
        raise InvalidGatewaySettingsError(
            "Gateway 'api_key' must not contain whitespace or control characters"
        )

    if disallow_master_key and stripped == disallow_master_key.strip():
        raise InvalidGatewaySettingsError(
            "Gateway 'api_key' must be a consumer virtual key, not LITELLM_MASTER_KEY"
        )

    return stripped


def _validate_httpx_timeout(timeout: httpx.Timeout) -> httpx.Timeout:
    """Validate all components of an ``httpx.Timeout`` object."""
    for component_name, component_val in (
        ("connect", timeout.connect),
        ("read", timeout.read),
        ("write", timeout.write),
        ("pool", timeout.pool),
    ):
        if component_val is not None and not _is_finite_positive_number(float(component_val)):
            raise InvalidGatewaySettingsError(
                f"Gateway 'timeout.{component_name}' must be a finite positive number"
            )
    return timeout


def validate_timeout(timeout: Any) -> float | httpx.Timeout:
    """Validate request timeout (positive float/int seconds or ``httpx.Timeout``)."""
    if isinstance(timeout, bool) or timeout is None:
        raise InvalidGatewaySettingsError(
            "Gateway 'timeout' must be a positive number of seconds or an httpx.Timeout instance"
        )

    if isinstance(timeout, httpx.Timeout):
        return _validate_httpx_timeout(timeout)

    if isinstance(timeout, (int, float)):
        val = float(timeout)
        if not _is_finite_positive_number(val):
            raise InvalidGatewaySettingsError(
                "Gateway 'timeout' must be a finite positive number of seconds"
            )
        return val

    if isinstance(timeout, str):
        try:
            val = float(timeout.strip())
        except ValueError as exc:
            raise InvalidGatewaySettingsError(
                "Gateway 'timeout' must be a finite positive number of seconds"
            ) from exc
        if not _is_finite_positive_number(val):
            raise InvalidGatewaySettingsError(
                "Gateway 'timeout' must be a finite positive number of seconds"
            )
        return val

    raise InvalidGatewaySettingsError(
        "Gateway 'timeout' must be a positive number of seconds or an httpx.Timeout instance"
    )


def _parse_int_setting(value: Any, *, error_message: str) -> int:
    """Parse an integer setting from an ``int`` or digits-only ``str``."""
    if isinstance(value, bool) or value is None:
        raise InvalidGatewaySettingsError(error_message)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw or not raw.lstrip("-").isdigit():
            raise InvalidGatewaySettingsError(error_message)
        return int(raw)
    raise InvalidGatewaySettingsError(error_message)


def validate_max_retries(max_retries: Any) -> int:
    """Validate client retry count (non-negative integer)."""
    error_msg = "Gateway 'max_retries' must be a non-negative integer"
    val = _parse_int_setting(
        max_retries,
        error_message=error_msg,
    )
    if val < 0:
        raise InvalidGatewaySettingsError(error_msg)
    return val


def validate_embedding_dimensions(dimensions: Any) -> int | None:
    """Validate optional embedding dimensions (positive integer or None)."""
    if dimensions is None or (isinstance(dimensions, str) and not dimensions.strip()):
        return None

    error_msg = "Gateway 'embedding_dimensions' must be a positive integer (> 0)"
    val = _parse_int_setting(
        dimensions,
        error_message=error_msg,
    )
    if val <= 0:
        raise InvalidGatewaySettingsError(error_msg)
    return val


def validate_optional_str(value: Any, *, field_name: str) -> str | None:
    """Validate an optional string setting (such as model alias, app_name, environment)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidGatewaySettingsError(f"Gateway '{field_name}' must be a string or None")

    stripped = value.strip()
    if not stripped:
        return None

    if _has_control_chars(stripped):
        raise InvalidGatewaySettingsError(
            f"Gateway '{field_name}' must not contain control characters"
        )
    return stripped


def _validate_single_header(raw_key: Any, raw_val: Any) -> tuple[str, str]:
    """Validate a single HTTP header key-value pair."""
    if not isinstance(raw_key, str) or not isinstance(raw_val, str):
        raise InvalidGatewaySettingsError(
            "Gateway 'default_headers' keys and values must be strings"
        )
    key = raw_key.strip()
    if not key:
        raise InvalidGatewaySettingsError(
            "Gateway 'default_headers' must not contain empty header names"
        )
    if key.lower() in FORBIDDEN_HEADER_NAMES:
        raise InvalidGatewaySettingsError(
            f"Gateway 'default_headers' must not override reserved header '{key}'"
        )
    if _has_whitespace_or_control_chars(key) or ":" in key:
        raise InvalidGatewaySettingsError(
            "Gateway 'default_headers' contains an invalid header name"
        )
    if _has_control_chars(raw_val):
        raise InvalidGatewaySettingsError(
            f"Gateway 'default_headers' value for '{key}' must not contain control characters"
        )
    return key, raw_val


def validate_default_headers(headers: Any) -> dict[str, str]:
    """Validate optional custom HTTP headers."""
    if headers is None:
        return {}
    if not isinstance(headers, Mapping):
        raise InvalidGatewaySettingsError(
            "Gateway 'default_headers' must be a mapping of string header names to string values"
        )

    return dict(_validate_single_header(k, v) for k, v in headers.items())


def validate_verify_ssl(verify_ssl: Any) -> bool:
    """Validate ``verify_ssl`` boolean flag."""
    if isinstance(verify_ssl, bool):
        return verify_ssl
    raise InvalidGatewaySettingsError("Gateway 'verify_ssl' must be a boolean")


def parse_bool_env(value: str, *, var_name: str) -> bool:
    """Parse a boolean environment variable strictly."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise InvalidGatewaySettingsError(
        f"Environment variable '{var_name}' must be a boolean (true/false/1/0)"
    )


def _effective_port(parsed: SplitResult) -> int | None:
    """Return explicit port or standard scheme default port (80 for http, 443 for https)."""
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == "http":
        return 80
    if parsed.scheme == "https":
        return 443
    return None


def validate_http_client_origin(
    http_client: httpx.Client | httpx.AsyncClient,
    expected_base_url: str,
) -> None:
    """Verify a custom ``httpx`` client cannot route gateway credentials to an unrelated origin."""
    if getattr(http_client, "follow_redirects", False):
        raise InvalidGatewaySettingsError(
            "Custom http_client must not enable follow_redirects=True "
            "to prevent credential leakage across origins"
        )
    if getattr(http_client, "auth", None) is not None:
        raise InvalidGatewaySettingsError(
            "Custom http_client must not configure custom auth that overrides gateway credentials"
        )

    client_base = str(http_client.base_url)
    if not client_base:
        return
    parsed_client = urlsplit(client_base)
    if not parsed_client.scheme and not parsed_client.hostname:
        return
    parsed_expected = urlsplit(expected_base_url)
    if (
        parsed_client.scheme != parsed_expected.scheme
        or parsed_client.hostname != parsed_expected.hostname
        or _effective_port(parsed_client) != _effective_port(parsed_expected)
    ):
        raise InvalidGatewaySettingsError(
            "Custom http_client base_url origin does not match configured gateway base_url"
        )
