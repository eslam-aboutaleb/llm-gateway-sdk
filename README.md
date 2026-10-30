# `llm-gateway-sdk`

**A Lightweight, Reusable, OpenAI-Compatible Python SDK for Self-Hosted LiteLLM Gateways**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Typed: PEP 561](https://img.shields.io/badge/typing-PEP%20561-green.svg)](src/llm_gateway_sdk/py.typed)

`llm-gateway-sdk` standardizes how Python applications connect to a self-hosted [LiteLLM Gateway](https://github.com/eslam-aboutaleb/llm-gateway). It provides a clean, layered configuration and client-factory boundary around the official `openai` Python SDK—without introducing another LLM framework, middleware server, or heavyweight runtime dependency.

---

## Why Does This SDK Exist?

1. **Eliminates Duplicated Gateway Boilerplate:** Centralizes URL validation, virtual API key validation, secret redaction, timeout settings, and attribution headers across repositories (`polymarket-ai-trading` and future services).
2. **Prevents Retry Multiplication (`max_retries=0`):** The LiteLLM Gateway already performs upstream provider retries and fallbacks. The official `openai` SDK defaults to `max_retries=2`, which can inadvertently multiply retries up to 9x. `llm-gateway-sdk` defaults to `max_retries=0`.
3. **Prevents Accidental Gateway Bypass:** Never silently falls back to `OPENAI_API_KEY` or accepts `LITELLM_MASTER_KEY`.
4. **Returns Native OpenAI Clients:** `settings.create_client()` returns `openai.OpenAI` and `settings.create_async_client()` returns `openai.AsyncOpenAI`. Consumers retain 100% access to native OpenAI resources, types, streaming, tool calling, and exceptions.
5. **Zero Heavyweight Dependencies in Core:** The core package depends only on `openai>=1.40.0,<3.0.0`. Framework adapters (`pydantic-settings`, `instructor`, `langchain-openai`, `traceloop-sdk`) live in isolated optional extras.

---

## Layered Architecture

```text
+-------------------------------------------------------------------+
| Layer 4: Optional Ecosystem Adapters (llm_gateway_sdk.integrations)|
|   - pydantic_settings.py  - instructor.py                         |
|   - langchain.py          - openllmetry.py                        |
+-------------------------------------------------------------------+
                                 |
                                 v
+-------------------------------------------------------------------+
| Layer 3: Client Factories (llm_gateway_sdk.clients)               |
|   - create_client() -> openai.OpenAI                              |
|   - create_async_client() -> openai.AsyncOpenAI                   |
+-------------------------------------------------------------------+
                                 |
                                 v
+-------------------------------------------------------------------+
| Layer 2: Configuration Model (llm_gateway_sdk.settings)           |
|   - GatewaySettings (immutable dataclass, from_env(), redaction)  |
+-------------------------------------------------------------------+
                                 |
                                 v
+-------------------------------------------------------------------+
| Layer 1: Validation & Security Boundary (llm_gateway_sdk.validation)|
|   - URL, API key, timeout, retry, dimension & header validators   |
+-------------------------------------------------------------------+
                                 |
                                 v
+-------------------------------------------------------------------+
| Layer 0: Domain Primitives (constants.py, exceptions.py)          |
+-------------------------------------------------------------------+
```

---

## Installation

### Core Package (Minimal Footprint)

```bash
pip install llm-gateway-sdk
```

Or via `uv` from a pinned Git tag:

```bash
uv add "llm-gateway-sdk @ git+https://github.com/eslam-aboutaleb/llm-gateway-sdk.git@v0.1.0"
```

### Optional Extras

```bash
# Pydantic Settings integration
pip install "llm-gateway-sdk[settings]"

# Instructor structured outputs
pip install "llm-gateway-sdk[structured]"

# LangChain (ChatOpenAI & OpenAIEmbeddings)
pip install "llm-gateway-sdk[langchain]"

# OpenLLMetry / OpenTelemetry observability
pip install "llm-gateway-sdk[observability]"

# All optional integrations
pip install "llm-gateway-sdk[all]"
```

---

## Configuration

Set the following environment variables (see [`.env.example`](.env.example)):

```dotenv
LLM_GATEWAY_BASE_URL=https://gateway.example.com/v1
LLM_GATEWAY_API_KEY=sk-consumer-virtual-key

LLM_GATEWAY_DEFAULT_MODEL=general-fast
LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL=rag-embedding
LLM_GATEWAY_EMBEDDING_DIMENSIONS=1536

LLM_GATEWAY_TIMEOUT=30
LLM_GATEWAY_MAX_RETRIES=0

LLM_GATEWAY_APP_NAME=polymarket-ai-trading
LLM_GATEWAY_ENVIRONMENT=production
```

---

## Quickstart

### 1. Synchronous Chat Completion

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

with settings.create_client() as client:
    response = client.chat.completions.create(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.choices[0].message.content)
```

### 2. Asynchronous Chat Completion

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

async with settings.create_async_client() as client:
    response = await client.chat.completions.create(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.choices[0].message.content)
```

### 3. Streaming

```python
stream = await async_client.chat.completions.create(
    model="general-fast",
    messages=[{"role": "user", "content": "Explain this."}],
    stream=True,
)

async for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="")
```

### 4. Vector Embeddings

```python
response = await async_client.embeddings.create(
    model="rag-embedding",
    input=["Example document"],
)
vector = response.data[0].embedding
```

### 5. Optional Integrations

- **Instructor (`llm-gateway-sdk[structured]`):**
  ```python
  from llm_gateway_sdk.integrations.instructor import create_instructor_client

  structured_client = create_instructor_client(client)
  ```
- **LangChain (`llm-gateway-sdk[langchain]`):**
  ```python
  from llm_gateway_sdk.integrations.langchain import create_chat_model

  llm = create_chat_model(settings=settings, model="general-reasoning")
  ```
- **Pydantic Settings (`llm-gateway-sdk[settings]`):**
  ```python
  from llm_gateway_sdk.integrations.pydantic_settings import GatewayBaseSettings
  ```
- **OpenLLMetry (`llm-gateway-sdk[observability]`):**
  ```python
  from llm_gateway_sdk.integrations.openllmetry import configure_observability

  configure_observability(settings, record_content=False)
  ```

---

## What Intentionally Remains in Consumer Applications?

- Domain-specific prompts, agent workflows, and trading/business logic.
- Application-specific model tier mappings (e.g., `CHEAP`, `STANDARD`, `STRONG`, `WRITER`).
- Vector store schemas, SQLite/pgvector index management, and embedding fingerprint checks.
- Gateway administration (`/key/*`, `/user/*`, `/team/*`, `/spend/*`).

---

## Documentation

- [Quickstart Guide](docs/QUICKSTART.md)
- [SDK Architecture & Layered Design](docs/SDK_ARCHITECTURE.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- [Client Lifecycle & FastAPI Guide](docs/CLIENT_LIFECYCLE.md)
- [Framework Integrations](docs/FRAMEWORK_INTEGRATIONS.md)
- [Gateway Compatibility Matrix](docs/GATEWAY_COMPATIBILITY.md)
- [Error Handling & Retry Safety](docs/ERROR_HANDLING.md)
- [Security & Privacy Model](docs/SECURITY.md)
- [Polymarket Migration Guide](docs/POLYMARKET_MIGRATION.md)
- [Testing Guide](docs/TESTING.md)
- [Versioning Policy](docs/VERSIONING.md)
- [Release Process](docs/RELEASE_PROCESS.md)
- [Third-Party License Inventory](docs/THIRD_PARTY_LICENSES.md)

---

## License

Released under the [MIT License](LICENSE).

