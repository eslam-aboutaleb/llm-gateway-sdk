# Polymarket Migration Guide (`polymarket-ai-trading`)

## 1. Migration Objectives

Migrate `polymarket-ai-trading` (`services/shared/polymarket_settings` and `services/cli-agent`) to use `llm-gateway-sdk` while preserving 100% of existing business logic, model tiering, error sanitization (`ProviderRequestError`), and SQLite vector-store fingerprinting (`embedding_identity`).

## 2. What Moved to `llm-gateway-sdk`

1. **`GatewayBaseSettings` & `connection_options` (`llm_gateway_sdk.integrations.pydantic_settings`):**
   - Replaces the hand-rolled URL validator, `SecretStr` fields, validation-error input redaction, and `connection_options()` in `services/shared/polymarket_settings/gateway.py`.
2. **Endpoint & Credential Validation (`llm_gateway_sdk.validation`):**
   - Centralizes HTTP(S) endpoint validation and secret protection.
3. **Gateway Settings & Client Construction:**
   - Standardizes how `polymarket_settings` and `cli-agent` resolve `api_base` and `api_key`.

## 3. What Remains in `polymarket-ai-trading`

- `LLMProvider`, `ModelTier`, `MODEL_CATALOG`, `TASK_TIERS`, `TIER_DEFAULTS`, `SharedLLMSettings`, and `resolve_tier_config()` in `services/shared/polymarket_settings/settings.py`.
- `embedding_identity(settings)` in `services/shared/polymarket_settings/gateway.py` (preserving the exact `sha256(json.dumps([model, base, dimensions]))` hash stored in SQLite `vector_config`).
- `SafeChatLiteLLM`, `SafeLiteLLMEmbeddings`, and `ProviderRequestError` in `services/shared/polymarket_settings/litellm_adapter.py`.
- All trading analysis chains, prompts, orchestrator plans, and SQLite RAG operations.

## 4. Rollback Plan

Because `services/shared/polymarket_settings/gateway.py` preserves the exact public symbols (`GatewaySettings`, `connection_options`, `embedding_identity`, `create_chat`, `create_embeddings`) expected by `llm-chain`, `cli-agent`, and `backend`:
1. Reverting the migration requires only reverting the commit in `services/shared/polymarket_settings/gateway.py` and `pyproject.toml`.
2. No database migration, SQLite RAG reindexing, or `.env` secret change is required during either forward migration or rollback.

