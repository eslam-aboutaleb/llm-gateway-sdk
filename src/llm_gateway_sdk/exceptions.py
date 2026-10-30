"""Exceptions raised by ``llm_gateway_sdk`` for configuration and validation errors.

Runtime HTTP, network, timeout, and API status errors are intentionally NOT wrapped;
the official ``openai`` Python SDK exceptions (``APIConnectionError``, ``APITimeoutError``,
``APIStatusError``, ``AuthenticationError``, ``PermissionDeniedError``, ``RateLimitError``,
etc.) propagate directly to callers.
"""

from __future__ import annotations

__all__ = [
    "GatewayConfigError",
    "GatewaySDKError",
    "InvalidGatewaySettingsError",
    "InvalidGatewayURLError",
    "MissingGatewayConfigError",
]


class GatewaySDKError(ValueError):
    """Base exception for all ``llm-gateway-sdk`` configuration and usage errors.

    Inherits from :class:`ValueError` so callers expecting standard Python value
    validation errors can catch either ``GatewaySDKError`` or ``ValueError``.
    Never include raw API keys, headers, or credentials in exception messages.
    """


class GatewayConfigError(GatewaySDKError):
    """Raised when gateway configuration is missing, malformed, or unsafe."""


class MissingGatewayConfigError(GatewayConfigError):
    """Raised when a required gateway setting (such as ``base_url`` or ``api_key``) is missing."""


class InvalidGatewayURLError(GatewayConfigError):
    """Raised when a gateway ``base_url`` is malformed or violates security constraints."""


class InvalidGatewaySettingsError(GatewayConfigError):
    """Raised when a non-URL gateway setting (timeout, retries, dimensions, headers) is invalid."""
