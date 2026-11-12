# Changelog

All notable changes to `llm-gateway-sdk` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-30

### Added
- **Provider-Agnostic & Framework-Agnostic Core Architecture:**
  - `constants.py` and `exceptions.py` (Layer 0) providing typed configuration and runtime exceptions (`GatewaySDKError`, `GatewayConfigError`, `GatewayRuntimeError`, `GatewayAPIStatusError`, `GatewayBadRequestError`, `GatewayAuthenticationError`, `GatewayPermissionDeniedError`, `GatewayNotFoundError`, `GatewayUnprocessableEntityError`, `GatewayRateLimitError`, `GatewayInternalServerError`, `GatewayConnectionError`, `GatewayTimeoutError`).
  - `validation.py` (Layer 1) enforcing strict URL, virtual key, timeout, retry, embedding dimension, HTTP header, and origin checks.
  - `settings.py` and `models.py` (Layer 2) providing the immutable `GatewaySettings` dataclass and Pydantic v2 response/stream models (`ChatResponse`, `ChatStreamChunk`, `EmbeddingResponse`, `ModelListResponse`, `GatewayStream`, `AsyncGatewayStream`, `RawGatewayResponse`).
  - `clients.py` (Layer 3) providing pure-`httpx` `GatewayClient` and `AsyncGatewayClient` supporting synchronous and asynchronous chat completions, SSE streaming, tool calling, vector embeddings, model discovery, and health checks with `max_retries=0` by default.
- **Optional Settings Integration (Layer 4):**
  - `llm_gateway_sdk.integrations.pydantic_settings` (`[settings]` extra): `GatewayBaseSettings` and `connection_options` with automatic validation error redaction.
- **Testing & Documentation:**
  - Complete unit, integration, and gateway contract test suites (`tests/`).
  - Working example scripts (`examples/`) and comprehensive developer documentation (`docs/`).
