# `llm-gateway-sdk` Layered Architecture & Clean Code Design

## 1. Core Architectural Principle

`llm-gateway-sdk` is a **thin, strongly-typed configuration and client-factory layer** around the official `openai` Python SDK (`OpenAI` and `AsyncOpenAI`), purpose-built for self-hosted LiteLLM Gateways.

### Strict Layered Architecture (Unidirectional Dependency Graph)

To adhere to Clean Code and SOLID principles (Single Responsibility, Open/Closed, Dependency Inversion, and Acyclic Dependencies), the codebase is organized into 5 strictly ordered layers:

```text
+------------------------------------------------------------------------+
| Layer 4: Optional Ecosystem Adapters (llm_gateway_sdk.integrations.*)  |
|   - pydantic_settings.py  (GatewayBaseSettings, connection_options)    |
|   - instructor.py         (create_instructor_client, async variant)    |
|   - langchain.py          (create_chat_model, create_embeddings_model) |
|   - openllmetry.py        (configure_observability)                    |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
| Layer 3: Client Factory Layer (llm_gateway_sdk.clients)                |
|   - create_client()       -> openai.OpenAI                             |
|   - create_async_client() -> openai.AsyncOpenAI                        |
|   - _resolve_client_options() (shared DRY parameter resolution)        |
+------------------------------------------------------------------------+
                                    |
                                    v
+------------------------------------------------------------------------+
| Layer 2: Configuration Model & Env Resolution (llm_gateway_sdk.settings)|
|   - GatewaySettings (frozen dataclass, secret redaction, headers)      |
|   - _EnvironmentLookup (single-responsibility env variable resolver)   |
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
|   - GatewaySDKError -> GatewayConfigError hierarchy                    |
+------------------------------------------------------------------------+
```

### Clean Code Principles Applied

1. **Single Responsibility Principle (SRP):**
   - `constants.py` owns domain constants and defaults (no magic numbers or strings in logic).
   - `exceptions.py` owns the configuration exception hierarchy.
   - `validation.py` owns stateless input validation and security boundary enforcement.
   - `settings.py` owns the immutable `GatewaySettings` value object and `_EnvironmentLookup`.
   - `clients.py` owns `OpenAI` and `AsyncOpenAI` instantiation.
   - `integrations/*` each own a single optional third-party framework adapter.
2. **Don't Repeat Yourself (DRY):**
   - `_resolve_client_options()` in `clients.py` centralizes option resolution between synchronous and asynchronous OpenAI clients.
   - `_build_common_langchain_kwargs()` in `integrations/langchain.py` centralizes option resolution between `ChatOpenAI` and `OpenAIEmbeddings`.
   - `_parse_int_setting()` in `validation.py` centralizes integer parsing for `max_retries` and `embedding_dimensions`.
3. **Fail-Closed Security & Redaction:**
   - Every layer treats `api_key` as sensitive data that must never appear in `repr()`, `str()`, `to_dict()`, validation exceptions, or telemetry attributes.
