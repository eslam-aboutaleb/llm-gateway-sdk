"""Unit tests for SDK configuration exception hierarchy and native OpenAI error pass-through."""

from __future__ import annotations

import pytest

from llm_gateway_sdk import (
    GatewayConfigError,
    GatewaySDKError,
    InvalidGatewaySettingsError,
    InvalidGatewayURLError,
    MissingGatewayConfigError,
)


def test_exception_inheritance_hierarchy() -> None:
    assert issubclass(GatewaySDKError, ValueError)
    assert issubclass(GatewayConfigError, GatewaySDKError)
    assert issubclass(MissingGatewayConfigError, GatewayConfigError)
    assert issubclass(InvalidGatewayURLError, GatewayConfigError)
    assert issubclass(InvalidGatewaySettingsError, GatewayConfigError)


def test_catching_as_value_error_or_sdk_error() -> None:
    with pytest.raises(ValueError):
        raise MissingGatewayConfigError("Missing required gateway setting")

    with pytest.raises(GatewaySDKError):
        raise InvalidGatewayURLError("Invalid gateway URL")
