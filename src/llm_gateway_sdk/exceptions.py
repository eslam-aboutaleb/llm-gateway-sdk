"""Layer 0: Provider-agnostic exception hierarchy for ``llm_gateway_sdk``.

All configuration and runtime exceptions inherit from :class:`GatewaySDKError`.
Configuration errors also inherit from :class:`ValueError` for standard Python
validation compatibility. Never include raw API keys, headers, or credentials
in exception messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

__all__ = [
    "GatewayAPIStatusError",
    "GatewayAuthenticationError",
    "GatewayBadRequestError",
    "GatewayConfigError",
    "GatewayConnectionError",
    "GatewayInternalServerError",
    "GatewayNotFoundError",
    "GatewayPermissionDeniedError",
    "GatewayRateLimitError",
    "GatewayRuntimeError",
    "GatewaySDKError",
    "GatewayTimeoutError",
    "GatewayUnprocessableEntityError",
    "InvalidGatewaySettingsError",
    "InvalidGatewayURLError",
    "MissingGatewayConfigError",
]


class GatewaySDKError(Exception):
    """Base exception for all ``llm-gateway-sdk`` configuration and runtime errors."""


class GatewayConfigError(GatewaySDKError, ValueError):
    """Raised when gateway configuration is missing, malformed, or unsafe.

    Inherits from :class:`ValueError` so callers expecting standard Python value
    validation errors can catch either ``GatewayConfigError`` or ``ValueError``.
    """


class MissingGatewayConfigError(GatewayConfigError):
    """Raised when a required gateway setting (such as ``base_url`` or ``api_key``) is missing."""


class InvalidGatewayURLError(GatewayConfigError):
    """Raised when a gateway ``base_url`` is malformed or violates security constraints."""


class InvalidGatewaySettingsError(GatewayConfigError):
    """Raised when a non-URL gateway setting (timeout, retries, dimensions, headers) is invalid."""


class GatewayRuntimeError(GatewaySDKError):
    """Base exception for runtime HTTP, transport, timeout, and gateway status errors."""


class GatewayConnectionError(GatewayRuntimeError):
    """Raised when a network, DNS, TCP, TLS, or mid-stream transport failure occurs."""


class GatewayTimeoutError(GatewayConnectionError):
    """Raised when a gateway request exceeds the configured connect, read, or write timeout."""


class GatewayAPIStatusError(GatewayRuntimeError):
    """Raised when the gateway returns a non-2xx HTTP status response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None = None,
        headers: httpx.Headers | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id
        self.headers = headers
        self.body = body


class GatewayBadRequestError(GatewayAPIStatusError):
    """Raised on HTTP 400 Bad Request from the gateway."""


class GatewayAuthenticationError(GatewayAPIStatusError):
    """Raised on HTTP 401 Unauthorized (missing, invalid, expired, or revoked virtual key)."""


class GatewayPermissionDeniedError(GatewayAPIStatusError):
    """Raised on HTTP 403 Forbidden (virtual key not permitted for requested model or route)."""


class GatewayNotFoundError(GatewayAPIStatusError):
    """Raised on HTTP 404 Not Found (blocked management route or unknown endpoint)."""


class GatewayUnprocessableEntityError(GatewayAPIStatusError):
    """Raised on HTTP 422 Unprocessable Entity."""


class GatewayRateLimitError(GatewayAPIStatusError):
    """Raised on HTTP 429 Too Many Requests (RPM, TPM, concurrency, or budget limit reached)."""


class GatewayInternalServerError(GatewayAPIStatusError):
    """Raised on HTTP 5xx server or upstream provider errors."""
