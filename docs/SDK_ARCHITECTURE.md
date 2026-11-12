# `llm-gateway-sdk` Layered Architecture & Clean Code Design

## 1. Core Architectural Principle

`llm-gateway-sdk` is a **100% provider-agnostic and framework-agnostic HTTP/SSE client and configuration SDK** built directly on `httpx` and `pydantic`, purpose-built for self-hosted LLM Gateways.

### Strict Layered Architecture (Unidirectional Dependency Graph)

To adhere to Clean Code and SOLID principles (Single Responsibility, Open/Closed, Dependency Inversion, and Acyclic Dependencies), the codebase is organized into 5 strictly ordered layers:

```text
+------------------------------------------------------------------------+
| Layer 4: Optional Configuration Adapters (llm_gateway_sdk.integrations)|
|   - pydantic_settings.py  (GatewayBaseSettings, connection_options)    |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
| Layer 3: Gateway HTTP/SSE Clients (llm_gateway_sdk.clients)            |
|   - GatewayClient / AsyncGatewayClient                                 |
|   - create_client() / create_async_client()                            |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
| Layer 2: Configuration & Response Models (settings.py, models.py)      |
|   - GatewaySettings (frozen dataclass, secret redaction, headers)      |
|   - ChatResponse, EmbeddingResponse, ModelListResponse, GatewayStream  |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
| Layer 1: Validation & Security Boundary (llm_gateway_sdk.validation)   |
|   - Pure, stateless validators for URLs, keys, timeouts, retries,      |
|     dimensions, headers, booleans, and custom httpx client origins     |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
| Layer 0: Domain Primitives (constants.py, exceptions.py)               |
|   - Immutable constants, header names, security blocklists             |
|   - GatewaySDKError -> GatewayConfigError / GatewayRuntimeError        |
+------------------------------------------------------------------------+
```

### Clean Code Principles Applied

1. **Single Responsibility Principle (SRP):**
   - `constants.py` owns domain constants and defaults (no magic numbers or strings in logic).
   - `exceptions.py` owns the configuration and runtime exception hierarchies.
   - `validation.py` owns stateless input validation and security boundary enforcement.
   - `settings.py` owns the immutable `GatewaySettings` value object and `_EnvironmentLookup`.
   - `models.py` owns Pydantic v2 response models and SSE stream iterators (`GatewayStream`, `AsyncGatewayStream`).
   - `clients.py` owns synchronous and asynchronous `httpx` request execution (`GatewayClient`, `AsyncGatewayClient`).
   - `integrations/pydantic_settings.py` owns the optional `pydantic-settings` adapter.
2. **Don't Repeat Yourself (DRY):**
   - `_resolve_client_options()`, `_prepare_chat_payload()`, `_prepare_embeddings_payload()`, and `_wrap_raw_response()` in `clients.py` centralize request/response preparation between synchronous and asynchronous clients.
   - `_parse_int_setting()` in `validation.py` centralizes integer parsing for `max_retries` and `embedding_dimensions`.
3. **Fail-Closed Security & Redaction:**
   - Every layer treats `api_key` as sensitive data that must never appear in `repr()`, `str()`, `to_dict()`, validation exceptions, or gateway HTTP status errors.
