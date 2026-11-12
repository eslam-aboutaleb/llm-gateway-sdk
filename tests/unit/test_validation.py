"""Unit tests for URL, API key, timeout, retry, dimension, and header validation."""

from __future__ import annotations

import httpx
import pytest

from llm_gateway_sdk import (
    GatewaySettings,
    InvalidGatewaySettingsError,
    InvalidGatewayURLError,
    MissingGatewayConfigError,
)
from llm_gateway_sdk.validation import (
    parse_bool_env,
    validate_api_key,
    validate_base_url,
    validate_default_headers,
    validate_embedding_dimensions,
    validate_http_client_origin,
    validate_max_retries,
    validate_optional_str,
    validate_timeout,
    validate_verify_ssl,
)


@pytest.mark.parametrize(
    "valid_url",
    [
        "https://gateway.example.com/v1",
        "https://gateway.example.com/v1/",
        "https://gateway.example.com",
        "http://localhost:4000/v1",
        "http://127.0.0.1:4000/v1",
        "http://[::1]:4000/v1",
        "https://10.0.0.5:8443/path/v1",
        "http://provider.internal/v1",
    ],
)
def test_valid_base_urls_preserved_verbatim(valid_url: str) -> None:
    assert validate_base_url(valid_url) == valid_url
    settings = GatewaySettings(base_url=valid_url, api_key="sk-valid")
    assert settings.base_url == valid_url


@pytest.mark.parametrize("missing_url", [None, "", "   "])
def test_missing_base_url_raises_missing_config(missing_url: str | None) -> None:
    with pytest.raises(MissingGatewayConfigError):
        validate_base_url(missing_url)


@pytest.mark.parametrize(
    "invalid_url",
    [
        12345,
        "ftp://localhost/v1",
        "ws://localhost:4000/v1",
        "gateway.example.com/v1",
        "https:///v1",
        "https://user:synthetic-secret@localhost/v1",
        "https://localhost/v1?api_key=synthetic-secret",
        "https://localhost/v1#synthetic-secret",
        "https://localhost/v1?",
        "https://localhost/v1#",
        "https://localhost:0/v1",
        "https://localhost:99999/v1",
        "https://localhost/\nsynthetic-secret",
        "https://localhost/v1 with space",
        "https://localhost\\@evil.example/v1",
        "https://@localhost/v1",
    ],
)
def test_invalid_base_urls_rejected_and_never_leak_secrets(invalid_url: object) -> None:
    with pytest.raises(InvalidGatewayURLError) as exc_info:
        validate_base_url(invalid_url)
    assert "synthetic-secret" not in str(exc_info.value)


@pytest.mark.parametrize("missing_key", [None, "", "   "])
def test_missing_api_key_raises_missing_config(missing_key: str | None) -> None:
    with pytest.raises(MissingGatewayConfigError):
        validate_api_key(missing_key)


@pytest.mark.parametrize(
    "invalid_key",
    [
        123,
        "sk-key with-space",
        "sk-key\nwith-newline",
        "sk-key\x00null",
        "sk-key\x7fdel",
    ],
)
def test_invalid_api_key_rejected_without_echoing_secret(invalid_key: object) -> None:
    with pytest.raises(InvalidGatewaySettingsError) as exc_info:
        validate_api_key(invalid_key)
    if isinstance(invalid_key, str):
        assert invalid_key.strip() not in str(exc_info.value)


@pytest.mark.parametrize(
    ("raw_timeout", "expected"),
    [
        (30, 30.0),
        (15.5, 15.5),
        ("45", 45.0),
        (" 12.5 ", 12.5),
    ],
)
def test_valid_timeout_values(raw_timeout: object, expected: float) -> None:
    assert validate_timeout(raw_timeout) == expected


def test_valid_httpx_timeout_object() -> None:
    t = httpx.Timeout(30.0, connect=5.0, read=25.0, write=10.0)
    assert validate_timeout(t) is t


@pytest.mark.parametrize(
    "invalid_timeout",
    [
        None,
        True,
        False,
        0,
        -5.0,
        float("inf"),
        float("nan"),
        "0",
        "-10",
        "not-a-number",
        httpx.Timeout(30.0, connect=0.0),
        httpx.Timeout(30.0, read=-1.0),
        object(),
    ],
)
def test_invalid_timeout_rejected(invalid_timeout: object) -> None:
    with pytest.raises(InvalidGatewaySettingsError):
        validate_timeout(invalid_timeout)


@pytest.mark.parametrize(
    ("raw_retries", "expected"),
    [
        (0, 0),
        (2, 2),
        ("0", 0),
        (" 3 ", 3),
    ],
)
def test_valid_max_retries(raw_retries: object, expected: int) -> None:
    assert validate_max_retries(raw_retries) == expected


@pytest.mark.parametrize(
    "invalid_retries",
    [None, True, False, -1, 1.5, "-1", "abc", "", object()],
)
def test_invalid_max_retries_rejected(invalid_retries: object) -> None:
    with pytest.raises(InvalidGatewaySettingsError):
        validate_max_retries(invalid_retries)


@pytest.mark.parametrize(
    ("raw_dims", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        (1536, 1536),
        ("1536", 1536),
        (" 256 ", 256),
    ],
)
def test_valid_embedding_dimensions(raw_dims: object, expected: int | None) -> None:
    assert validate_embedding_dimensions(raw_dims) == expected


@pytest.mark.parametrize(
    "invalid_dims",
    [True, False, 0, -128, "0", "-5", "abc", 1536.5, object()],
)
def test_invalid_embedding_dimensions_rejected(invalid_dims: object) -> None:
    with pytest.raises(InvalidGatewaySettingsError):
        validate_embedding_dimensions(invalid_dims)


def test_validate_optional_str() -> None:
    assert validate_optional_str(None, field_name="default_model") is None
    assert validate_optional_str("   ", field_name="default_model") is None
    assert validate_optional_str(" general-fast ", field_name="default_model") == "general-fast"
    with pytest.raises(InvalidGatewaySettingsError):
        validate_optional_str(123, field_name="default_model")
    with pytest.raises(InvalidGatewaySettingsError):
        validate_optional_str("bad\nmodel", field_name="default_model")


@pytest.mark.parametrize(
    "bad_headers",
    [
        "not-a-dict",
        {123: "val"},
        {"X-Key": 123},
        {"": "val"},
        {"   ": "val"},
        {"Authorization": "Bearer other"},
        {"authorization": "Bearer other"},
        {"Host": "evil.example.com"},
        {":authority": "evil.example.com"},
        {"X-Bad:Name": "val"},
        {"X-Bad Name": "val"},
        {"X-Bad\nName": "val"},
        {"X-Good": "bad\r\nvalue"},
    ],
)
def test_invalid_default_headers_rejected(bad_headers: object) -> None:
    with pytest.raises(InvalidGatewaySettingsError):
        validate_default_headers(bad_headers)


def test_validate_verify_ssl_and_parse_bool_env() -> None:
    assert validate_verify_ssl(True) is True
    assert validate_verify_ssl(False) is False
    with pytest.raises(InvalidGatewaySettingsError):
        validate_verify_ssl("true")

    assert parse_bool_env("true", var_name="TEST") is True
    assert parse_bool_env("1", var_name="TEST") is True
    assert parse_bool_env("false", var_name="TEST") is False
    assert parse_bool_env("0", var_name="TEST") is False
    with pytest.raises(InvalidGatewaySettingsError):
        parse_bool_env("maybe", var_name="TEST")


def test_validate_http_client_origin_default_ports_and_auth() -> None:
    with httpx.Client(base_url="https://gateway.example.com/v1") as https_client:
        validate_http_client_origin(https_client, "https://gateway.example.com:443/v1")

    with httpx.Client(base_url="http://localhost/v1") as http_client:
        validate_http_client_origin(http_client, "http://localhost:80/v1")

    with (
        httpx.Client(auth=("user", "pass")) as authed_client,
        pytest.raises(InvalidGatewaySettingsError, match="custom auth"),
    ):
        validate_http_client_origin(authed_client, "https://gateway.example.com/v1")
