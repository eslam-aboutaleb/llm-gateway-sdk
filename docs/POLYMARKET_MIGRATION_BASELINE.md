# Polymarket Migration Baseline (`polymarket-ai-trading`)

**Baseline Date:** 2026-10-30  
**Repository Path:** `/Users/eslamaboutaleb/Documents/polymarket`  
**Remote:** `https://github.com/eslam-aboutaleb/polymarket-ai-trading.git`

---

## 1. Pre-Migration Test Execution Baseline

All existing gateway, CLI agent, RAG store, and backend LLM gateway tests were executed prior to any modifications and passed:

### 1.1 AI Services Test Suite (`services/tests/`)

Command:
```bash
PYTHONPATH=services/shared:services/llm-chain \
  uv run --project services/llm-chain --frozen \
  pytest services/tests/test_gateway.py services/tests/test_cli_gateway.py services/tests/test_market_rag_store.py -q
```
Result:
- **`41 passed, 1 skipped in 3.87s`** (the 1 skipped test is `test_live_gateway_factories_and_rag`, which requires `RUN_GATEWAY_INTEGRATION=1`).

### 1.2 Backend LLM Gateway & Shared Settings Test Suite (`backend/tests/`)

Command:
```bash
cd backend && uv run --frozen pytest tests/test_llm_gateway.py tests/test_shared_llm_settings.py -o addopts="" -q
```
Result:
- **`64 passed in 2.25s`**

---

## 2. Locked Dependency Versions Before Migration

### `services/llm-chain` (Python 3.12 venv / `requires-python = ">=3.11"`)
- `openai`: `2.54.0`
- `pydantic`: `2.14.1`
- `pydantic-settings`: `2.16.1`
- `langchain-openai`: `1.7.2`
- `langchain-core`: `1.6.12`
- `langchain-litellm`: `0.8.x`
- `litellm`: `1.103.9`
- `filelock`: `4.2.4`
- `httpx`: `0.28.1`

### `backend` (Python 3.11 venv / `requires-python = ">=3.11"`)
- `openai`: `2.24.0`
- `pydantic`: `2.12.5`
- `pydantic-settings`: `2.13.1`
- `langchain-openai`: `1.1.10`
- `langchain-core`: `1.2.16`
- `httpx`: `0.28.1`

---

## 3. Baseline Behavior & Invariants to Preserve

1. **Environment Variables & Precedence:**
   - `LITELLM_API_BASE` -> `settings.gateway_base` (`SecretStr | None`)
   - `LITELLM_API_KEY` -> `settings.gateway_key` (`SecretStr | None`)
   - `LITELLM_MODEL` -> `settings.gateway_model` (`str | None`), falling back to `LLM_MODEL` (`settings.llm_model`, default `"gpt-4o-mini"`)
   - `LITELLM_EMBEDDING_MODEL` -> `settings.embedding_model` (`str | None`), falling back to `RAG_EMBEDDING_MODEL` (`settings.rag_embedding_model`, default `"text-embedding-3-small"`)
   - `LITELLM_EMBEDDING_DIMENSIONS` -> `RAG_EMBEDDING_DIMENSIONS` -> `settings.embedding_dimensions` (`int | None`, empty string `""` treated as `None`, `<= 0` rejected).
   - Legacy `LITELLM_EMBEDDING_API_BASE` and `LITELLM_EMBEDDING_API_KEY` are validated for URL safety if supplied, but `connection_options(settings, embedding=True)` **ignores** them and always returns the primary gateway's `{"api_base": base.rstrip("/"), "api_key": key}`.
2. **Error Redaction on Validation & Provider Failures:**
   - Invalid URLs or invalid `embedding_dimensions` raise `pydantic.ValidationError` with `input` redacted to `"[redacted]"` so `gateway_key` never appears in `str(exc)`, `exc.json()`, or `exc.errors()`.
   - `ProviderRequestError` wraps chat/embedding configuration and runtime failures so raw provider payloads or secrets never leak into logs or responses.
3. **Vector Index Fingerprinting (`embedding_identity`):**
   - `embedding_identity(settings)` computes:
     ```python
     hashlib.sha256(
         json.dumps(
             [
                 settings.embedding_model or settings.rag_embedding_model,
                 connection_options(settings, embedding=True).get("api_base", ""),
                 settings.embedding_dimensions,
             ]
         ).encode()
     ).hexdigest()
     ```
   - Stored in `vector_config (id=1, identity, dimensions)` inside SQLite (`market_rag.py`). Any change to model, endpoint, or dimensions blocks reads and writes on a populated index until `clear()` and full reindexing.
4. **Per-Task Model Tiering (`resolve_tier_config`):**
   - `CHEAP` (`gpt-4o-mini`, `t=0.0`, `512` tokens)
   - `STANDARD` (`gpt-4o-mini`, `t=0.2`, `2048` tokens)
   - `STRONG` (`gpt-4o`, `t=0.2`, `2048` tokens, `reasoning_effort="medium"`)
   - `WRITER` (`gpt-4o`, `t=0.6`, `4096` tokens)
   - When `provider == LLMProvider.LITELLM`, tier model overrides (`LLM_TIER_<TIER>_MODEL`) take precedence if `LLM_TIERING_ENABLED=true`, followed by `settings.gateway_model`, then `settings.llm_model`.
5. **CLI Agent (`services/cli-agent/src/cli_agent.py`):**
   - Uses `connection_options(self.settings)` to obtain `api_base` and `api_key`, and sends requests to `{self.api_base}/chat/completions` with `Bearer {self.api_key}`, refusing to fall back to `github_token` or `openai_api_key`.

