# Optional Framework Integrations

All ecosystem integrations are optional extras and are never installed by the base `llm-gateway-sdk` package.

---

## 1. Pydantic Settings (`llm-gateway-sdk[settings]`)

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
- Accepts both `LLM_GATEWAY_*` and legacy `LITELLM_*` environment variables via `AliasChoices`.
- Masks `gateway_base` and `gateway_key` using `SecretStr`.
- Redacts all `ValidationError` input payloads to `"[redacted]"` so credentials never leak in error logs or JSON dumps.

---

## 2. Instructor Structured Outputs (`llm-gateway-sdk[structured]`)

```bash
pip install "llm-gateway-sdk[structured]"
```

```python
from pydantic import BaseModel
from llm_gateway_sdk import GatewaySettings
from llm_gateway_sdk.integrations.instructor import create_instructor_client


class TradeDecision(BaseModel):
    action: str
    confidence: float


settings = GatewaySettings.from_env()
with settings.create_client() as client:
    structured = create_instructor_client(client)
    decision = structured.chat.completions.create(
        model="structured-output",
        response_model=TradeDecision,
        max_retries=1,
        messages=[{"role": "user", "content": "Evaluate BTC > 100k market."}],
    )
```

> **Cost Note:** Each Instructor validation retry sends an additional completion request to the gateway. Always bound `max_retries` to `0` or `1`.

---

## 3. LangChain (`llm-gateway-sdk[langchain]`)

```bash
pip install "llm-gateway-sdk[langchain]"
```

```python
from llm_gateway_sdk import GatewaySettings
from llm_gateway_sdk.integrations.langchain import (
    create_chat_model,
    create_embeddings_model,
)

settings = GatewaySettings.from_env()

llm = create_chat_model(
    settings=settings,
    model="general-reasoning",
    temperature=0.2,
)

embeddings = create_embeddings_model(
    settings=settings,
    model="rag-embedding",
)
```

Features:
- Uses official `langchain_openai.ChatOpenAI` and `langchain_openai.OpenAIEmbeddings`.
- Propagates `max_retries=0`, `timeout`, and attribution headers.
- Sets `check_embedding_ctx_length=False` by default so plain strings are sent to the LiteLLM Proxy `/v1/embeddings` endpoint without client-side tiktoken assumptions.

---

## 4. OpenLLMetry & OpenTelemetry (`llm-gateway-sdk[observability]`)

```bash
pip install "llm-gateway-sdk[observability]"
```

```python
from llm_gateway_sdk import GatewaySettings
from llm_gateway_sdk.integrations.openllmetry import configure_observability

settings = GatewaySettings.from_env()

# Privacy-first: record_content=False (default) disables prompt/completion capture
configure_observability(
    settings,
    record_content=False,
)
```

Privacy guarantees:
- Tracing is **never** initialized automatically on import.
- `record_content=False` sets `TRACELOOP_TRACE_CONTENT="false"` before instrumentation starts.
- API keys and secret attribute names are strictly rejected if passed in `resource_attributes` or `headers`.

