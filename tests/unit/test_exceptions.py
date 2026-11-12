"""Unit tests for SDK configuration and runtime exception hierarchies."""

from __future__ import annotations

import pytest

from llm_gateway_sdk import (
    GatewayAPIStatusError,
    GatewayAuthenticationError,
    GatewayBadRequestError,
    GatewayConfigError,
    GatewayConnectionError,
    GatewayInternalServerError,
    GatewayNotFoundError,
    GatewayPermissionDeniedError,
    GatewayRateLimitError,
    GatewayRuntimeError,
    GatewaySDKError,
    GatewayTimeoutError,
    GatewayUnprocessableEntityError,
    InvalidGatewaySettingsError,
    InvalidGatewayURLError,
    MissingGatewayConfigError,
)


def test_exception_inheritance_hierarchy() -> None:
    assert issubclass(GatewayConfigError, GatewaySDKError)
    assert issubclass(GatewayConfigError, ValueError)
    assert issubclass(MissingGatewayConfigError, GatewayConfigError)
    assert issubclass(InvalidGatewayURLError, GatewayConfigError)
    assert issubclass(InvalidGatewaySettingsError, GatewayConfigError)

    assert issubclass(GatewayRuntimeError, GatewaySDKError)
    assert issubclass(GatewayConnectionError, GatewayRuntimeError)
    assert issubclass(GatewayTimeoutError, GatewayConnectionError)
    assert issubclass(GatewayAPIStatusError, GatewayRuntimeError)
    assert issubclass(GatewayBadRequestError, GatewayAPIStatusError)
    assert issubclass(GatewayAuthenticationError, GatewayAPIStatusError)
    assert issubclass(GatewayPermissionDeniedError, GatewayAPIStatusError)
    assert issubclass(GatewayNotFoundError, GatewayAPIStatusError)
    assert issubclass(GatewayUnprocessableEntityError, GatewayAPIStatusError)
    assert issubclass(GatewayRateLimitError, GatewayAPIStatusError)
    assert issubclass(GatewayInternalServerError, GatewayAPIStatusError)


def test_catching_as_value_error_or_sdk_error() -> None:
    with pytest.raises(ValueError):
        raise MissingGatewayConfigError("Missing required gateway setting")

    with pytest.raises(GatewaySDKError):
        raise InvalidGatewayURLError("Invalid gateway URL")

    with pytest.raises(GatewaySDKError):
        raise GatewayAuthenticationError("Unauthorized", status_code=401, request_id="req-1")
