# Reference Research & Architectural Analysis

**Project:** `llm-gateway-sdk`  
**Target Gateway:** [`eslam-aboutaleb/llm-gateway`](https://github.com/eslam-aboutaleb/llm-gateway) (LiteLLM Proxy `v1.46.1`)  
**First Consumer:** [`eslam-aboutaleb/polymarket-ai-trading`](https://github.com/eslam-aboutaleb/polymarket-ai-trading)

---

## 1. Executive Summary

This document records the architectural research conducted across the five upstream reference repositories and our deployed LiteLLM Gateway prior to implementing `llm-gateway-sdk`. The overarching design mandate is:

> **Build a thin, reusable configuration and client-integration layer. Do not build another LLM framework.**

The official `openai` Python SDK handles all HTTP protocol transport, SSE streaming, request/response serialization, pagination, and exception hierarchy. `llm-gateway-sdk` standardizes gateway configuration, URL & credential validation, safe retry/timeout defaults (`max_retries=0`), secret redaction, and optional ecosystem adapters (`pydantic-settings`, `instructor`, `langchain-openai`, `traceloop-sdk`).

---

## 2. Primary Reference: OpenAI Python SDK (`openai/openai-python`)

- **Repository:** https://github.com/openai/openai-python
- **License:** Apache-2.0
- **Tested Range:** `openai>=1.40.0,<3.0.0` (verified with `1.x` and `2.x`, including `2.24.0` and `2.54.0`)

### 2.1 What Was Studied
- `OpenAI` and `AsyncOpenAI` constructor signatures and configuration precedence (`api_key`, `base_url`, `timeout`, `max_retries`, `default_headers`, `http_client`).
- Transport customization via `httpx.Client` / `httpx.AsyncClient` and `openai.DefaultHttpxClient` / `openai.DefaultAsyncHttpxClient`.
- Native timeout support (`float | httpx.Timeout | None`).
- Native exception hierarchy (`APIConnectionError`, `APITimeoutError`, `APIStatusError`, `BadRequestError` [400], `AuthenticationError` [401], `PermissionDeniedError` [403], `NotFoundError` [404], `ConflictError` [409], `UnprocessableEntityError` [422], `RateLimitError` [429], `InternalServerError` [>=500]).
- Request ID propagation (`response._request_id` and `APIStatusError.request_id` populated from `x-request-id` / `x-litellm-call-id`).
- Synchronous and asynchronous context manager lifecycle (`with client:` / `async with async_client:` and `.close()` / `await .close()`).
- Streaming via `Stream[ChatCompletionChunk]` and `AsyncStream[ChatCompletionChunk]`.

### 2.2 Architectural Patterns Adopted
1. **Return Native Clients Directly:** `settings.create_client()` returns `openai.OpenAI` and `settings.create_async_client()` returns `openai.AsyncOpenAI`. Consumers retain 100% access to `.chat.completions`, `.embeddings`, `.models`, `.with_options()`, and `.with_raw_response`.
2. **Disable Client-Side Retries by Default (`max_retries=0`):** The official `openai` SDK defaults to `max_retries=2`. Because the LiteLLM Gateway already configures `num_retries: 2` in `router_settings` on status codes `[429, 500, 502, 503, 504]`, keeping the OpenAI SDK default would multiply retries to `3 x 3 = 9` upstream attempts. `GatewaySettings` defaults to `max_retries=0`.
3. **Pass-Through Exceptions:** All runtime API/HTTP errors remain native `openai.OpenAIError` subclasses. `llm-gateway-sdk` only defines configuration/validation exceptions (`GatewaySDKError`, `GatewayConfigError`, `MissingGatewayConfigError`, `InvalidGatewayURLError`, `InvalidGatewaySettingsError`).
4. **Public Transport Interfaces Only:** Custom HTTP clients or `verify_ssl=False` overrides use `httpx.Client` / `httpx.AsyncClient` passed via the public `http_client=` parameter rather than mutating private `_client` attributes.

### 2.3 Features Intentionally Not Adopted
- Custom `GatewayClient` wrapper classes around `.chat.completions.create()` or `.embeddings.create()`.
- Custom HTTP retry loops or Tenacity dependencies in the core package.
- Implicit fallback to `os.environ["OPENAI_API_KEY"]` (which could silently bypass the gateway if misconfigured).

---

## 3. Gateway Reference: LiteLLM Proxy (`BerriAI/litellm`)

- **Repository:** https://github.com/BerriAI/litellm
- **License:** MIT
- **Gateway Deployment Version:** `ghcr.io/berriai/litellm:main-v1.46.1` (pinned by SHA256 digest in `llm-gateway/gateway/compose.yaml`)

### 3.1 What Was Studied
- LiteLLM Proxy OpenAI-compatible endpoints exposed through Caddy ingress (`llm-gateway/gateway/caddy/Caddyfile`):
  - `POST /v1/chat/completions` (300s timeout, `flush_interval -1` for SSE streaming)
  - `POST /v1/embeddings` (120s timeout)
  - `GET /v1/models`
  - `GET /health`, `/ready`, `/status` (rewritten to `/health/liveness`)
- Blocked administrative routes at public ingress (`404 Not Found`):
  - `/ui*`, `/key*`, `/team*`, `/user*`, `/config*`, `/spend*`, `/model*`, `/provider*`, `/callback*`, `/litellm*`, `/health/readiness*`, `/health/liveness*`, `/metrics*`, `/docs*`, `/openapi*`, `/redoc*`, `/swagger*`
- Virtual key behavior (`key_defaults` in `litellm.yaml`):
  - `allowed_routes: ["/v1/chat/completions", "/v1/embeddings", "/v1/models"]`
  - Authentication via `Authorization: Bearer <virtual-key>`
- Configured model aliases (`gateway/config/litellm.yaml` & `model-catalog.yaml`):
  - `general-fast` (chat, streaming, function calling)
  - `general-reasoning` (chat, streaming, function calling, reasoning)
  - `structured-output` (chat, streaming, structured output, JSON mode)
  - `agent-tools` (chat, streaming, function calling, parallel tools)
  - `rag-embedding` (embeddings, 1536 dimensions)
  - `rag-embedding-large` (embeddings, 3072 dimensions, disabled by default)

### 3.2 Architectural Patterns Adopted
- **Zero `litellm` Python Package Dependency:** Consumer applications communicate with the LiteLLM Proxy exclusively over its OpenAI-compatible HTTPS API using `openai`. Avoiding the `litellm` Python SDK in consumers eliminates massive transitive dependency bloat and `filelock` version conflicts.
- **Exact Base URL Preservation:** The SDK validates that `base_url` is a clean HTTP(S) URL without embedded credentials, query strings, or fragments, and preserves the configured path without silently appending or stripping `/v1` (except normalizing trailing slashes appropriately when needed by callers).
- **Consumer Virtual Keys Only:** The SDK rejects `LITELLM_MASTER_KEY` and never exposes administrative `/key/*`, `/user/*`, `/team/*`, or `/spend/*` methods.

---

## 4. Structured Output Reference: Instructor (`567-labs/instructor`)

- **Repository:** https://github.com/567-labs/instructor
- **License:** MIT
- **Optional Extra:** `llm-gateway-sdk[structured]` (`instructor>=1.4.0,<2.0.0`)

### 4.1 What Was Studied
- `instructor.from_openai(client, mode=...)` for both `OpenAI` and `AsyncOpenAI`.
- Structured output modes (`instructor.Mode.TOOLS`, `instructor.Mode.JSON`, `instructor.Mode.JSON_SCHEMA`).
- Validation retry behavior (`max_retries` argument in `instructor` completion calls).

### 4.2 Architectural Patterns Adopted
- Thin helper functions `create_instructor_client()` and `create_async_instructor_client()` in `llm_gateway_sdk.integrations.instructor`.
- Defaulting `mode=instructor.Mode.TOOLS` (broadest compatibility across LiteLLM Proxy routed models) while allowing callers to override `mode`.
- Explicit documentation and bounded default retry guidance (`max_retries=0` or explicit small integer) to prevent runaway token costs on schema validation failures.

---

## 5. Configuration Reference: Pydantic Settings (`pydantic/pydantic-settings`)

- **Repository:** https://github.com/pydantic/pydantic-settings
- **License:** MIT
- **Optional Extra:** `llm-gateway-sdk[settings]` (`pydantic-settings>=2.2.0,<3.0.0`)

### 5.1 What Was Studied
- `BaseSettings`, `SettingsConfigDict`, `SecretStr`, `AliasChoices`, and `@model_validator(mode="wrap")` for redacting secret inputs in `ValidationError`.
- How `polymarket-ai-trading` currently uses `GatewaySettings(BaseSettings)` in `services/shared/polymarket_settings/gateway.py`.

### 5.2 Architectural Patterns Adopted
- Core `GatewaySettings` in `llm_gateway_sdk.settings` is implemented using standard-library `dataclasses` so the base `llm-gateway-sdk` package has **only `openai` as a direct runtime dependency**.
- Optional `GatewayBaseSettings(BaseSettings)` in `llm_gateway_sdk.integrations.pydantic_settings` provides a drop-in Pydantic Settings base class with `SecretStr` masking, `ValidationError` input redaction, `LLM_GATEWAY_*` primary aliases, optional `LITELLM_*` backward-compatibility aliases, and `.to_gateway_settings()` / `.create_client()` / `.create_async_client()` helpers.

---

## 6. Framework Reference: LangChain (`langchain-ai/langchain`)

- **Repository:** https://github.com/langchain-ai/langchain (`libs/partners/openai`)
- **License:** MIT
- **Optional Extra:** `llm-gateway-sdk[langchain]` (`langchain-openai>=0.2.0,<2.0.0`)

### 6.1 What Was Studied
- `ChatOpenAI` and `OpenAIEmbeddings` initialization parameters (`model`, `api_key`, `base_url`, `timeout`, `max_retries`, `default_headers`, `http_client`, `http_async_client`, `dimensions`, `check_embedding_ctx_length`).
- Behavior when sending plain strings vs. tokenized arrays to `/v1/embeddings` through LiteLLM Proxy (`check_embedding_ctx_length=False` ensures plain text strings are sent cleanly to any upstream embedding provider behind LiteLLM).

### 6.2 Architectural Patterns Adopted
- `create_chat_model()` and `create_embeddings_model()` in `llm_gateway_sdk.integrations.langchain` return configured `ChatOpenAI` and `OpenAIEmbeddings` instances wired to `GatewaySettings`.
- Zero automatic retries (`max_retries=0`) and explicit timeout propagation by default.

---

## 7. Observability Reference: OpenLLMetry (`traceloop/openllmetry`)

- **Repository:** https://github.com/traceloop/openllmetry
- **License:** Apache-2.0
- **Optional Extra:** `llm-gateway-sdk[observability]` (`traceloop-sdk>=0.30.0,<1.0.0`)

### 7.1 What Was Studied
- `Traceloop.init()` and `opentelemetry-instrumentation-openai`.
- Environment variables controlling prompt/completion content capture (`TRACELOOP_TRACE_CONTENT`).
- Span attribute injection and privacy controls.

### 7.2 Architectural Patterns Adopted
- Explicit opt-in initialization via `configure_observability(settings, ...)` in `llm_gateway_sdk.integrations.openllmetry`.
- **Never** initializes tracing on import.
- **Privacy by default:** `record_content=False` sets `TRACELOOP_TRACE_CONTENT="false"` before initializing instrumentation so prompts and completions are never exported unless explicitly enabled.
- Redacts API keys and authorization headers, and attaches safe attribution metadata (`app_name`, `environment`).

---

## 8. Third-Party Dependency & License Summary

| Package | Role | Scope | License | Commercial Restrictions |
|---|---|---|---|---|
| `openai` | Official OpenAI Python client | Core (Required) | Apache-2.0 | None |
| `httpx` | Transitive via `openai` | Transitive | BSD-3-Clause | None |
| `pydantic` | Transitive via `openai` | Transitive | MIT | None |
| `pydantic-settings` | Settings management | Optional (`[settings]`) | MIT | None |
| `instructor` | Structured outputs | Optional (`[structured]`) | MIT | None |
| `langchain-openai` | LangChain integration | Optional (`[langchain]`) | MIT | None |
| `traceloop-sdk` | OpenLLMetry observability | Optional (`[observability]`) | Apache-2.0 | None |

