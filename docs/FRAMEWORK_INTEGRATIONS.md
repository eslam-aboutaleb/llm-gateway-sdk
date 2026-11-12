# Optional Configuration Integrations

`llm-gateway-sdk` is framework-agnostic at its core (`httpx` + `pydantic` only) and provides an optional `pydantic-settings` integration for services that manage configuration via `BaseSettings`.

---

## Pydantic Settings (`llm-gateway-sdk[settings]`)

```bash
pip install "llm-gateway-sdk[settings]"
```

```python
from llm_gateway_sdk.integrations.pydantic_settings import GatewayBaseSettings


class ServiceSettings(GatewayBaseSettings):
    service_name: str = "my-service"


settings = ServiceSettings()
client = settings.create_gateway_client()
```

Features:
- Accepts `LLM_GATEWAY_*` (including `LLM_GATEWAY_URL` and `LLM_GATEWAY_KEY`) and legacy `LITELLM_*` environment variables via `AliasChoices`.
- Masks `gateway_base` and `gateway_key` using `SecretStr`.
- Redacts all `ValidationError` input payloads to `"[redacted]"` so credentials never leak in error logs or JSON dumps.
