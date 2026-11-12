# Configuration Guide

## 1. Direct Programmatic Configuration

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings(
    base_url="https://gateway.example.com/v1",
    api_key="sk-consumer-virtual-key",
    default_model="general-fast",
    default_embedding_model="rag-embedding",
    embedding_dimensions=1536,
    timeout=30.0,
    max_retries=0,
    app_name="my-service",
    environment="production",
)
```

## 2. Environment Variable Loading (`GatewaySettings.from_env()`)

| Environment Variable | Field | Required | Default |
|---|---|---|---|
| `LLM_GATEWAY_BASE_URL` | `base_url` | Yes | — |
| `LLM_GATEWAY_API_KEY` | `api_key` | Yes | — |
| `LLM_GATEWAY_DEFAULT_MODEL` | `default_model` | No | `None` |
| `LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL` | `default_embedding_model` | No | `None` |
| `LLM_GATEWAY_EMBEDDING_DIMENSIONS` | `embedding_dimensions` | No | `None` |
| `LLM_GATEWAY_TIMEOUT` | `timeout` | No | `30.0` |
| `LLM_GATEWAY_MAX_RETRIES` | `max_retries` | No | `0` |
| `LLM_GATEWAY_APP_NAME` | `app_name` | No | `None` |
| `LLM_GATEWAY_ENVIRONMENT` | `environment` | No | `None` |
| `LLM_GATEWAY_VERIFY_SSL` | `verify_ssl` | No | `True` |

### Testing with Custom Environment Dictionaries

```python
test_env = {
    "LLM_GATEWAY_BASE_URL": "http://localhost:4000/v1",
    "LLM_GATEWAY_API_KEY": "sk-test-key",
}
settings = GatewaySettings.from_env(environ=test_env)
```

### Opt-In Legacy `LITELLM_*` Compatibility

Existing applications that configure `LITELLM_API_BASE`, `LITELLM_API_KEY`, `LITELLM_MODEL`, `LITELLM_EMBEDDING_MODEL`, and `LITELLM_EMBEDDING_DIMENSIONS` / `RAG_EMBEDDING_DIMENSIONS` can opt in explicitly:

```python
settings = GatewaySettings.from_env(allow_legacy_litellm_env=True)
```

## 3. Pydantic Settings Integration (`llm-gateway-sdk[settings]`)

```bash
pip install "llm-gateway-sdk[settings]"
```

```python
from llm_gateway_sdk.integrations.pydantic_settings import GatewayBaseSettings


class ServiceSettings(GatewayBaseSettings):
    service_name: str = "my-service"


settings = ServiceSettings()
client = settings.create_client()
```

Features:
- Accepts `LLM_GATEWAY_*` (including `LLM_GATEWAY_URL` and `LLM_GATEWAY_KEY`) and legacy `LITELLM_*` environment variables via `AliasChoices`.
- Masks `gateway_base` and `gateway_key` using `SecretStr`.
- Redacts all `ValidationError` input payloads to `"[redacted]"` so credentials never leak in error logs or JSON dumps.

## 4. Base URL Rules

- Must use `http://` or `https://`.
- Must include a valid hostname and valid port (`1..65535`).
- Must **not** contain embedded `username:password@` credentials, `?query` parameters, `#fragment` identifiers, whitespace, control characters, or backslashes (`\`).
- `GatewaySettings` preserves the supplied URL path verbatim and does **not** automatically append or strip `/v1`. Always include `/v1` in `LLM_GATEWAY_BASE_URL` (e.g., `https://gateway.example.com/v1`) as required by the gateway route contract.

