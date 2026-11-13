# `llm-gateway-sdk`

**Provider-Agnostic, Framework-Agnostic Python SDK for Self-Hosted LLM Gateways**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![Typed: PEP 561](https://img.shields.io/badge/typing-PEP%20561-green.svg)](src/llm_gateway_sdk/py.typed)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

`llm-gateway-sdk` is a lightweight, strongly-typed Python SDK that standardizes how services connect to a self-hosted [LLM Gateway](https://github.com/eslam-aboutaleb/llm-gateway).

Built directly on **`httpx` and `pydantic`** with **zero dependency on `openai`, `langchain`, or any vendor/framework SDK**, it provides synchronous and asynchronous clients (`GatewayClient` and `AsyncGatewayClient`) for **chat completions**, **SSE streaming**, **tool calling**, **vector embeddings**, and **model discovery**—with strict URL/credential validation, automatic secret redaction, request attribution headers, and safe retry defaults (`max_retries=0`).

---

## Table of Contents

- [30-Second Quickstart](#30-second-quickstart)
- [Why `llm-gateway-sdk`?](#why-llm-gateway-sdk)
- [Installation](#installation)
- [Configuration Reference](#configuration-reference)
- [Usage Examples](#usage-examples)
  - [1. Synchronous Chat Completion](#1-synchronous-chat-completion)
  - [2. Asynchronous Chat & Real-Time SSE Streaming](#2-asynchronous-chat--real-time-sse-streaming)
  - [3. Tool / Function Calling](#3-tool--function-calling)
  - [4. Vector Embeddings](#4-vector-embeddings)
  - [5. FastAPI Lifespan Integration](#5-fastapi-lifespan-integration)
  - [6. Error Handling & Request IDs](#6-error-handling--request-ids)
- [Optional Ecosystem Integrations](#optional-ecosystem-integrations)
- [Gateway Model Aliases & Route Contract](#gateway-model-aliases--route-contract)
- [User Guides](#user-guides)
- [License](#license)

---

## 30-Second Quickstart

**1. Install the SDK:**

```bash
pip install llm-gateway-sdk
```

**2. Set your Gateway URL and Consumer Virtual Key:**

```bash
export LLM_GATEWAY_BASE_URL="https://gateway.example.com/v1"
export LLM_GATEWAY_API_KEY="sk-your-consumer-virtual-key"
export LLM_GATEWAY_DEFAULT_MODEL="general-fast"
```

**3. Call your Gateway:**

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

with settings.create_client() as client:
    response = client.complete(
        messages=[{"role": "user", "content": "Summarize API gateways in one sentence."}],
    )
    print(response.content)
```

---

## Why `llm-gateway-sdk`?

| Problem with Vendor/Framework SDK Boilerplate | How `llm-gateway-sdk` Solves It |
|---|---|
| **Vendor & Framework Coupling:** Importing `openai` or `langchain` just to send HTTP JSON/SSE requests to your own self-hosted gateway couples your services to third-party SDK release cycles and ~90 transitive dependencies. | **100% Provider- & Framework-Agnostic:** Built directly on `httpx` and `pydantic`. Supports both concise top-level methods (`client.complete()`, `client.stream()`, `client.embed()`, `client.list_models()`, `client.health()`) and resource namespaces (`client.chat.completions.create()`, `client.embeddings.create()`, `client.models.list()`). |
| **Retry Multiplication (Up to 9x Calls):** Vendor SDKs default to `max_retries=2` (3 attempts), while the LLM Gateway also retries upstream (`num_retries: 2`), multiplying failures into 9 upstream calls and risking duplicate token billing. | Defaults to **`max_retries=0`** on all clients so retry and fallback logic stays centralized in the LLM Gateway router. |
| **Accidental Gateway Bypass:** Missing env vars can cause vendor SDKs to silently fall back to `OPENAI_API_KEY` and hit upstream providers directly. | **Fail-closed configuration:** Never reads `OPENAI_API_KEY` and actively rejects `LITELLM_MASTER_KEY` in consumer services. |
| **Credential Leaks in Logs & Tracebacks:** Misconfigured URLs, `repr(settings)`, or Pydantic `ValidationError` dumps can expose API keys in logs. | **Automatic secret redaction (`[REDACTED]`):** Masks keys in `repr()`, `str()`, `to_dict()`, gateway error messages, and Pydantic validation errors. |

---

## Installation

### Core Package (Minimal Footprint: `httpx` + `pydantic` only)

```bash
# Using pip
pip install llm-gateway-sdk

# Using uv (from PyPI or pinned Git tag)
uv add llm-gateway-sdk
uv add "llm-gateway-sdk @ git+https://github.com/eslam-aboutaleb/llm-gateway-sdk.git@v0.1.0"
```

### Optional Extras

| Extra | Install Command | Provided Module & Capabilities |
|---|---|---|
| **`settings`** | `pip install "llm-gateway-sdk[settings]"` | `llm_gateway_sdk.integrations.pydantic_settings` (`GatewayBaseSettings` with secret-redacted validation) |

---

## Configuration Reference

Copy [`.env.example`](.env.example) to `.env` or set the following environment variables:

| Environment Variable | Short / Legacy Aliases | Required | Default | Description |
|---|---|---|---|---|
| `LLM_GATEWAY_BASE_URL` | `LLM_GATEWAY_URL`, `LITELLM_API_BASE` | **Yes** | — | HTTP(S) gateway base URL including `/v1` (e.g. `https://gateway.example.com/v1`) |
| `LLM_GATEWAY_API_KEY` | `LLM_GATEWAY_KEY`, `LITELLM_API_KEY` | **Yes** | — | Consumer virtual API key issued by the gateway administrator |
| `LLM_GATEWAY_DEFAULT_MODEL` | `LLM_GATEWAY_MODEL`, `LITELLM_MODEL` | No | `None` | Default chat completion model alias (e.g. `general-fast`) |
| `LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL` | `LLM_GATEWAY_EMBEDDING_MODEL`, `LITELLM_EMBEDDING_MODEL` | No | `None` | Default embedding model alias (e.g. `rag-embedding`) |
| `LLM_GATEWAY_EMBEDDING_DIMENSIONS` | `LITELLM_EMBEDDING_DIMENSIONS`, `RAG_EMBEDDING_DIMENSIONS` | No | `None` | Positive integer vector dimensions (e.g. `1536`) |
| `LLM_GATEWAY_TIMEOUT` | — | No | `30.0` | Request timeout in seconds (`> 0`) |
| `LLM_GATEWAY_MAX_RETRIES` | — | No | `0` | Client-side retries (`0` recommended; gateway handles retries) |
| `LLM_GATEWAY_APP_NAME` | — | No | `None` | Application name sent in `X-Gateway-App-Name` & `X-Title` headers |
| `LLM_GATEWAY_ENVIRONMENT` | — | No | `None` | Environment name (e.g. `production`) sent in `X-Gateway-Environment` |
| `LLM_GATEWAY_VERIFY_SSL` | — | No | `true` | TLS certificate verification (`true` / `false`) |

You can also construct `GatewaySettings` directly in code or override specific environment variables:

```python
from llm_gateway_sdk import GatewaySettings

# Load from environment with explicit overrides
settings = GatewaySettings.from_env(
    app_name="market-analyzer",
    environment="production",
    timeout=45.0,
)

# Or construct directly without environment variables
settings = GatewaySettings(
    base_url="https://gateway.example.com/v1",
    api_key="sk-consumer-virtual-key",
    default_model="general-fast",
    default_embedding_model="rag-embedding",
)
```

---

## Usage Examples

Runnable scripts for every pattern below are available in the [`examples/`](examples/) directory.

### 1. Synchronous Chat Completion

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

with settings.create_client() as client:
    response = client.complete(
        model=settings.default_model or "general-fast",
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Hello!"},
        ],
    )
    print(response.content)
```

### 2. Asynchronous Chat & Real-Time SSE Streaming

```python
import asyncio
from llm_gateway_sdk import GatewaySettings


async def main() -> None:
    settings = GatewaySettings.from_env()

    async with settings.create_async_client() as client:
        async with await client.stream(
            model=settings.default_model or "general-fast",
            messages=[{"role": "user", "content": "Explain why centralized LLM routing matters."}],
        ) as stream:
            async for delta_text in stream.iter_text():
                print(delta_text, end="", flush=True)
            print()


asyncio.run(main())
```

### 3. Tool / Function Calling

```python
import json
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_market_price",
            "description": "Retrieve current market price for a ticker",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    }
]

with settings.create_client() as client:
    response = client.complete(
        model="agent-tools",
        messages=[{"role": "user", "content": "Check the price for BTC-USD"}],
        tools=tools,
        tool_choice="required",
    )
    tool_call = response.tool_calls[0]
    print(tool_call.function.name, json.loads(tool_call.function.arguments))
```

### 4. Vector Embeddings

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

with settings.create_client() as client:
    response = client.embed(
        model=settings.default_embedding_model or "rag-embedding",
        input=["First document to embed", "Second document to embed"],
        dimensions=settings.embedding_dimensions or 1536,
    )
    print(f"Generated {len(response.vectors)} embeddings of {len(response.embedding)} dims")
```

### 5. FastAPI Lifespan Integration

Create a single shared `AsyncGatewayClient` at startup to reuse the underlying HTTP connection pool across requests:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from llm_gateway_sdk import GatewaySettings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = GatewaySettings.from_env()
    async with settings.create_async_client() as client:
        app.state.gateway_settings = settings
        app.state.llm_client = client
        yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat")
async def chat_endpoint(request: Request, prompt: str) -> dict[str, str | None]:
    client = request.app.state.llm_client
    res = await client.complete(
        model="general-fast",
        messages=[{"role": "user", "content": prompt}],
    )
    return {"reply": res.content}
```

### 6. Error Handling & Request IDs

Both configuration problems and runtime HTTP/network failures raise typed `GatewaySDKError` subclasses with full `request_id` traceability:

```python
from llm_gateway_sdk import (
    GatewayAPIStatusError,
    GatewayAuthenticationError,
    GatewayConfigError,
    GatewayRateLimitError,
    GatewaySettings,
)

try:
    settings = GatewaySettings.from_env()
except GatewayConfigError as exc:
    raise SystemExit(f"Invalid gateway configuration: {exc}")

with settings.create_client() as client:
    try:
        response = client.complete(
            model="general-fast",
            messages=[{"role": "user", "content": "Hello"}],
        )
    except GatewayRateLimitError as exc:
        print(f"Virtual key rate/budget limit reached (request_id={exc.request_id})")
    except GatewayAuthenticationError as exc:
        print(f"Invalid or expired virtual key (request_id={exc.request_id})")
    except GatewayAPIStatusError as exc:
        print(f"Gateway returned HTTP {exc.status_code} (request_id={exc.request_id})")
```

---

## Optional Ecosystem Integrations

### Pydantic Settings (`llm-gateway-sdk[settings]`)

Inherit from `GatewayBaseSettings` to embed gateway configuration into your service's Pydantic settings with automatic secret masking and `ValidationError` input redaction:

```python
from llm_gateway_sdk.integrations.pydantic_settings import GatewayBaseSettings


class AppSettings(GatewayBaseSettings):
    service_port: int = 8080


app_settings = AppSettings()
client = app_settings.create_gateway_client()
```

---

## Gateway Model Aliases & Route Contract

Standard model aliases configured on the companion [`llm-gateway`](https://github.com/eslam-aboutaleb/llm-gateway) (consumers can pass any alias authorized for their virtual key):

| Model Alias | Mode | Typical Use Case |
|---|---|---|
| `general-fast` | `chat` | Low-latency chat, summarization, and classification |
| `general-reasoning` | `chat` | Complex reasoning and multi-step analysis with automatic fallback |
| `structured-output` | `chat` | Strict JSON schema / Pydantic model extraction |
| `agent-tools` | `chat` | Single and parallel function/tool calling |
| `rag-embedding` | `embedding` | 1,536-dimension vector embeddings for RAG indexing and search |

> **Scope Boundary:** `llm-gateway-sdk` is strictly a **consumer inference SDK** (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`, `/health`). Gateway administration (`/key/*`, `/user/*`, `/team/*`, `/spend/*`) and application-specific domain logic remain outside this package.

---

## User Guides

| Guide | Description |
|---|---|
| [Configuration Guide](docs/CONFIGURATION.md) | Environment variables, `GatewayBaseSettings`, legacy aliases, and URL rules |
| [Client Lifecycle & FastAPI Guide](docs/CLIENT_LIFECYCLE.md) | Connection pooling, context managers, and FastAPI lifespan |
| [Error Handling & Timeouts](docs/ERROR_HANDLING.md) | Exception hierarchy, `request_id` debugging, and timeout configuration |

---

## License

Released under the [MIT License](LICENSE).
