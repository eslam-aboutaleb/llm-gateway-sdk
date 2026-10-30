"""Layer 4: Optional OpenLLMetry / OpenTelemetry integration (`llm-gateway-sdk[observability]`).

Depends inward on Layers 0-2 (``constants``, ``exceptions``, ``validation``, ``settings``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from llm_gateway_sdk.constants import FORBIDDEN_TELEMETRY_KEYS
from llm_gateway_sdk.exceptions import InvalidGatewaySettingsError
from llm_gateway_sdk.settings import GatewaySettings
from llm_gateway_sdk.validation import validate_optional_str

__all__ = [
    "ObservabilityConfig",
    "configure_observability",
]


@dataclass(frozen=True)
class ObservabilityConfig:
    """Validated observability configuration applied to OpenLLMetry."""

    app_name: str
    environment: str
    record_content: bool
    resource_attributes: Mapping[str, str]


def _import_traceloop() -> Any:
    try:
        from traceloop.sdk import Traceloop
    except ImportError as exc:
        raise ImportError(
            "traceloop-sdk is required for llm_gateway_sdk.integrations.openllmetry. "
            "Install it with: pip install 'llm-gateway-sdk[observability]'"
        ) from exc
    return Traceloop


def _sanitize_resource_attributes(
    attributes: Mapping[str, str] | None,
    *,
    secret_to_redact: str | None = None,
) -> dict[str, str]:
    if attributes is None:
        return {}
    if not isinstance(attributes, Mapping):
        raise InvalidGatewaySettingsError(
            "Observability 'resource_attributes' must be a mapping of string keys to string values"
        )

    sanitized: dict[str, str] = {}
    for raw_k, raw_v in attributes.items():
        if not isinstance(raw_k, str) or not isinstance(raw_v, str):
            raise InvalidGatewaySettingsError(
                "Observability 'resource_attributes' keys and values must be strings"
            )
        key = raw_k.strip()
        if not key:
            raise InvalidGatewaySettingsError(
                "Observability 'resource_attributes' must not contain empty keys"
            )
        if key.lower() in FORBIDDEN_TELEMETRY_KEYS:
            raise InvalidGatewaySettingsError(
                f"Observability 'resource_attributes' must not include secret attribute '{key}'"
            )
        if secret_to_redact and secret_to_redact in raw_v:
            raise InvalidGatewaySettingsError(
                f"Observability 'resource_attributes' value for '{key}' "
                "contains the gateway API key"
            )
        sanitized[key] = raw_v
    return sanitized


def configure_observability(
    settings: GatewaySettings | None = None,
    *,
    app_name: str | None = None,
    environment: str | None = None,
    exporter: Any | None = None,
    api_endpoint: str | None = None,
    headers: Mapping[str, str] | None = None,
    record_content: bool = False,
    disable_batch: bool = False,
    resource_attributes: Mapping[str, str] | None = None,
) -> ObservabilityConfig:
    """Explicitly initialize OpenLLMetry tracing with privacy-first defaults."""
    if settings is not None and not isinstance(settings, GatewaySettings):
        raise InvalidGatewaySettingsError(
            "configure_observability 'settings' must be a GatewaySettings instance or None"
        )
    if not isinstance(record_content, bool):
        raise InvalidGatewaySettingsError(
            "configure_observability 'record_content' must be a boolean"
        )

    resolved_app_name = (
        validate_optional_str(app_name, field_name="app_name")
        or (settings.app_name if settings else None)
        or "llm-gateway-consumer"
    )
    resolved_environment = (
        validate_optional_str(environment, field_name="environment")
        or (settings.environment if settings else None)
        or "development"
    )

    secret = settings.api_key if settings else None
    merged_attrs: dict[str, str] = {
        "service.name": resolved_app_name,
        "deployment.environment": resolved_environment,
    }
    if settings is not None:
        merged_attrs["llm.gateway.base_url"] = settings.base_url
    merged_attrs.update(_sanitize_resource_attributes(resource_attributes, secret_to_redact=secret))

    if headers is not None:
        _sanitize_resource_attributes(headers, secret_to_redact=secret)

    # Set privacy control environment variable BEFORE Traceloop.init reads it
    os.environ["TRACELOOP_TRACE_CONTENT"] = "true" if record_content else "false"

    Traceloop = _import_traceloop()

    init_kwargs: dict[str, Any] = {
        "app_name": resolved_app_name,
        "disable_batch": disable_batch,
        "resource_attributes": merged_attrs,
    }
    if exporter is not None:
        init_kwargs["exporter"] = exporter
    if api_endpoint is not None:
        init_kwargs["api_endpoint"] = api_endpoint
    if headers is not None:
        init_kwargs["headers"] = dict(headers)

    Traceloop.init(**init_kwargs)

    return ObservabilityConfig(
        app_name=resolved_app_name,
        environment=resolved_environment,
        record_content=record_content,
        resource_attributes=MappingProxyType(merged_attrs),
    )
