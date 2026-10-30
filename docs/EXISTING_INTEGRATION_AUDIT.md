# Existing Integration Audit (`polymarket-ai-trading`)

**Audited Repository:** [`eslam-aboutaleb/polymarket-ai-trading`](https://github.com/eslam-aboutaleb/polymarket-ai-trading)  
**Audit Date:** 2026-10-30  
**Purpose:** Identify reusable gateway integration logic vs. Polymarket-specific business/trading logic prior to SDK extraction and migration.

---

## 1. Architecture of the Existing Polymarket Integration

`polymarket-ai-trading` consists of three Python deployables that share LLM configuration via `services/shared/polymarket_settings`:

1. **`services/shared/polymarket_settings/`**:
   - `settings.py`: Defines `LLMProvider`, `ModelTier`, `MODEL_CATALOG`, `TASK_TIERS`, `TIER_DEFAULTS`, `SharedLLMSettings`, and `resolve_tier_config()`.
   - `gateway.py`: Defines `GatewaySettings(BaseSettings)`, `connection_options()`, `embedding_identity()`, `create_chat()`, and `create_embeddings()`.
   - `litellm_adapter.py`: Defines `ProviderRequestError`, `SafeChatLiteLLM(ChatLiteLLM)`, and `SafeLiteLLMEmbeddings(LiteLLMEmbeddings)`.
2. **`services/llm-chain/`**:
   - `src/config.py`: `Settings(SharedLLMSettings)` for the gRPC analysis service (`grpc_port=50051`).
   - `src/llm_factory.py`: `LLMRequestConfig`, `create_llm()`, `create_llm_for_request()`, `create_llm_for_task()`, `get_provider_info()`, `parse_llm_config_from_proto()`, `get_available_providers()`.
   - `src/market_rag.py`: `MarketRAGService` — SQLite-backed vector index (`market_vectors` and `vector_config` tables) using `create_embeddings(self.settings)` and `embedding_identity(self.settings)`.
   - `src/analysis_chain.py` & `src/orchestrator.py`: Trading analysis prompts, multi-step orchestration, copy-trade parsing, and opportunity scoring.
3. **`services/cli-agent/`**:
   - `src/config.py`: `Settings(SharedLLMSettings)` for the CLI Agent gRPC service (`grpc_port=50052`, `copilot_timeout=120`).
   - `src/cli_agent.py`: `CopilotCLIAgent` — previously used raw `httpx.AsyncClient` to POST directly to `f"{self.api_base}/chat/completions"` with manual `Bearer` header construction and manual JSON parsing.
4. **`backend/`**:
   - `app/services/intelligence/llm_gateway.py`: Backend-to-gRPC routing factory (`LLMGateway`, `PROVIDER_TO_PROTO`, `PROVIDER_TO_BACKEND`) that maps user/request provider preferences to either `AIBackend.LLM_CHAIN` or `AIBackend.CLI_AGENT`.

---

## 2. Classification: Reusable vs. Application-Specific Code

### 2.1 Truly Reusable Gateway Integration Code (Extract to `llm-gateway-sdk`)

| Component | Current Location in Polymarket | Target in `llm-gateway-sdk` |
|---|---|---|
| Endpoint URL validation (HTTP/HTTPS, no credentials, no query/fragment, no port 0, no control chars/whitespace/backslashes) | `polymarket_settings/gateway.py::validate_endpoint` | `llm_gateway_sdk.validation.validate_base_url` |
| API key validation & secret masking (`repr=False`, redacted validation errors) | `polymarket_settings/gateway.py::GatewaySettings` | `llm_gateway_sdk.settings.GatewaySettings` & `llm_gateway_sdk.integrations.pydantic_settings.GatewayBaseSettings` |
| Environment variable parsing & connection option extraction | `polymarket_settings/gateway.py::connection_options` | `GatewaySettings.from_env()` & `.connection_options()` |
| OpenAI-compatible sync/async client creation with timeout and `max_retries=0` | Manual `httpx.AsyncClient` in `cli-agent` / `ChatLiteLLM` in `llm-chain` | `GatewaySettings.create_client()` & `GatewaySettings.create_async_client()` |
| LangChain chat & embedding model construction against the gateway | `polymarket_settings/gateway.py::create_chat` & `create_embeddings` | `llm_gateway_sdk.integrations.langchain` (`create_chat_model`, `create_embeddings_model`) |

### 2.2 Application-Specific & Trading Logic (Must Remain in `polymarket-ai-trading`)

| Component | Location in Polymarket | Why It Remains in Polymarket |
|---|---|---|
| `LLMProvider` enum (`LITELLM`, `OPENAI`, `ANTHROPIC`, `GOOGLE`, `GROQ`, `OLLAMA`, `GITHUB_MODELS`) | `polymarket_settings/settings.py` | Specific to Polymarket's UI provider selector and gRPC `analysis.proto` enum |
| `ModelTier` (`CHEAP`, `STANDARD`, `STRONG`, `WRITER`) & `TASK_TIERS` (`market_assessment`, `copy_trade_eval`, `superforecast`, etc.) | `polymarket_settings/settings.py` | Domain-specific trading tasks and cost-tier routing |
| `resolve_tier_config()` & `LLM_TIERING_ENABLED` | `polymarket_settings/settings.py` | Application-specific tier resolution |
| `embedding_identity()` & SQLite `vector_config` table checks | `polymarket_settings/gateway.py` & `market_rag.py` | Vector index fingerprinting (`sha256(json.dumps([model, base, dimensions]))`) must stay byte-for-byte identical so existing SQLite RAG stores are not silently invalidated or corrupted |
| `ProviderRequestError` & `SafeChatLiteLLM` / `SafeLiteLLMEmbeddings` error boundary | `polymarket_settings/litellm_adapter.py` | Polymarket's specific error-redaction contract tested by `services/tests/test_gateway.py` |
| Backend gRPC routing (`app/services/intelligence/llm_gateway.py`) | `backend/` | Routes between Polymarket's `llm-chain` and `cli-agent` gRPC microservices |

---

## 3. Identified Pain Points & Inconsistencies in Current Polymarket Integration

1. **Direct `litellm` SDK Dependency in `llm-chain`:**
   - `services/llm-chain/pyproject.toml` pins `litellm>=1.103.9,<1.104` and `filelock>=4.2.1,<5` because newer `litellm` SDK releases cap `filelock<4` (conflicting with security fixes for CVE-2026-112940, CVE-2026-112913, CVE-2026-112907).
   - Because the gateway already speaks the standard OpenAI `/v1/chat/completions` and `/v1/embeddings` protocol, consumer applications do not need the heavyweight `litellm` Python SDK at all—though during Polymarket's staged migration we will preserve `SafeChatLiteLLM` / `SafeLiteLLMEmbeddings` compatibility so existing unit tests in `services/tests/test_gateway.py` continue to pass 100% while routing configuration through `llm-gateway-sdk`.
2. **Duplicate Raw HTTP Client in `cli-agent`:**
   - `services/cli-agent/src/cli_agent.py` manually constructs `httpx.AsyncClient(timeout=self.settings.copilot_timeout)` and manually builds `/chat/completions` requests instead of using a shared gateway SDK config.
3. **Environment Variable Naming Evolution:**
   - Polymarket currently uses `LITELLM_API_BASE`, `LITELLM_API_KEY`, `LITELLM_MODEL`, `LITELLM_EMBEDDING_MODEL`, and `LITELLM_EMBEDDING_DIMENSIONS` (with fallback to `RAG_EMBEDDING_DIMENSIONS`).
   - The new `llm-gateway-sdk` standardizes on `LLM_GATEWAY_*` (`LLM_GATEWAY_BASE_URL`, `LLM_GATEWAY_API_KEY`, `LLM_GATEWAY_DEFAULT_MODEL`, `LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL`, `LLM_GATEWAY_EMBEDDING_DIMENSIONS`, `LLM_GATEWAY_TIMEOUT`, `LLM_GATEWAY_MAX_RETRIES`, `LLM_GATEWAY_APP_NAME`, `LLM_GATEWAY_ENVIRONMENT`) while providing explicit opt-in compatibility (`allow_legacy_litellm_env=True` and `GatewayBaseSettings` alias choices) so Polymarket's existing `.env` and CI secrets (`LITELLM_API_BASE`, `LITELLM_API_KEY`) continue to work seamlessly without breaking existing deployments.

