"""``llm_gateway_sdk`` — Provider-agnostic, framework-agnostic Python SDK for LLM Gateways.

Layered Architecture
--------------------
- **Layer 0 (Domain Primitives):** ``constants.py``, ``exceptions.py``
- **Layer 1 (Validation & Security Boundary):** ``validation.py``
- **Layer 2 (Configuration Model & Env Resolution):** ``settings.py``, ``models.py``
- **Layer 3 (Gateway HTTP Clients & Streaming):** ``clients.py``
- **Layer 4 (Optional Ecosystem Adapters):** ``integrations/``
"""

from __future__ import annotations

from llm_gateway_sdk.clients import (
    AsyncGatewayClient,
    GatewayClient,
    create_async_client,
    create_client,
)
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
from llm_gateway_sdk.models import (
    AsyncGatewayStream,
    ChatChoice,
    ChatCompletion,
    ChatCompletionChunk,
    ChatDelta,
    ChatDeltaFunctionCall,
    ChatDeltaToolCall,
    ChatMessage,
    ChatResponse,
    ChatStreamChoice,
    ChatStreamChunk,
    CreateEmbeddingResponse,
    EmbeddingData,
    EmbeddingResponse,
    EmbeddingUsage,
    FunctionCall,
    GatewayStream,
    ModelInfo,
    ModelListResponse,
    RawGatewayResponse,
    TokenUsage,
    ToolCall,
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
    "AsyncGatewayClient",
    "AsyncGatewayStream",
    "ChatChoice",
    "ChatCompletion",
    "ChatCompletionChunk",
    "ChatDelta",
    "ChatDeltaFunctionCall",
    "ChatDeltaToolCall",
    "ChatMessage",
    "ChatResponse",
    "ChatStreamChoice",
    "ChatStreamChunk",
    "CreateEmbeddingResponse",
    "EmbeddingData",
    "EmbeddingResponse",
    "EmbeddingUsage",
    "FunctionCall",
    "GatewayAPIStatusError",
    "GatewayAuthenticationError",
    "GatewayBadRequestError",
    "GatewayClient",
    "GatewayConfigError",
    "GatewayConnectionError",
    "GatewayInternalServerError",
    "GatewayNotFoundError",
    "GatewayPermissionDeniedError",
    "GatewayRateLimitError",
    "GatewayRuntimeError",
    "GatewaySDKError",
    "GatewaySettings",
    "GatewayStream",
    "GatewayTimeoutError",
    "GatewayUnprocessableEntityError",
    "InvalidGatewaySettingsError",
    "InvalidGatewayURLError",
    "MissingGatewayConfigError",
    "ModelInfo",
    "ModelListResponse",
    "RawGatewayResponse",
    "TokenUsage",
    "ToolCall",
    "__version__",
    "create_async_client",
    "create_client",
]
