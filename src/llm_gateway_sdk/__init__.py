"""``llm_gateway_sdk`` — Lightweight, reusable OpenAI-compatible SDK for LiteLLM Gateways.

Layered Architecture
--------------------
- **Layer 0 (Domain Primitives):** ``constants.py``, ``exceptions.py``
- **Layer 1 (Validation & Security Boundary):** ``validation.py``
- **Layer 2 (Configuration Model & Env Resolution):** ``settings.py``
- **Layer 3 (Native OpenAI Client Factories):** ``clients.py``
- **Layer 4 (Optional Ecosystem Adapters):** ``integrations/``
"""

from __future__ import annotations

from llm_gateway_sdk.clients import create_async_client, create_client
from llm_gateway_sdk.constants import (
    ATTRIBUTION_APP_HEADER,
    ATTRIBUTION_ENV_HEADER,
    ATTRIBUTION_TITLE_HEADER,
    DEFAULT_ENV_PREFIX,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_VERIFY_SSL,
    REDACTED_SECRET,
)
from llm_gateway_sdk.exceptions import (
    GatewayConfigError,
    GatewaySDKError,
    InvalidGatewaySettingsError,
    InvalidGatewayURLError,
    MissingGatewayConfigError,
)
from llm_gateway_sdk.settings import GatewaySettings

__version__ = "0.1.0"

__all__ = [
    "ATTRIBUTION_APP_HEADER",
    "ATTRIBUTION_ENV_HEADER",
    "ATTRIBUTION_TITLE_HEADER",
    "DEFAULT_ENV_PREFIX",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_VERIFY_SSL",
    "REDACTED_SECRET",
    "GatewayConfigError",
    "GatewaySDKError",
    "GatewaySettings",
    "InvalidGatewaySettingsError",
    "InvalidGatewayURLError",
    "MissingGatewayConfigError",
    "__version__",
    "create_async_client",
    "create_client",
]
