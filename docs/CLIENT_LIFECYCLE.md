# Client Lifecycle Management

`settings.create_client()` and `settings.create_async_client()` return provider-agnostic `GatewayClient` and `AsyncGatewayClient` instances backed by `httpx` connection pools.

## 1. Best Practices

- **Reuse clients across requests:** Creating a new `GatewayClient` or `AsyncGatewayClient` on every request defeats HTTP connection pooling and increases TLS handshake overhead.
- **No hidden global singletons in the SDK:** `llm-gateway-sdk` intentionally does not cache a global client singleton so multi-tenant configurations, tests, and graceful shutdowns remain under application control.
- **Always close clients on shutdown:** Use context managers (`with` / `async with`) or call `client.close()` / `await async_client.close()`.

## 2. Short-Lived Scripts & CLI Tools

Use context managers so the underlying HTTP pool closes automatically:

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

with settings.create_client() as client:
    res = client.complete(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
```

Async context manager:

```python
async with settings.create_async_client() as async_client:
    res = await async_client.complete(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
```

## 3. FastAPI Lifespan Integration

Initialize a single `AsyncGatewayClient` in your FastAPI `lifespan` context manager and store it on `app.state`:

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


@app.post("/analyze")
async def analyze(request: Request) -> dict[str, str | None]:
    client = request.app.state.llm_client
    response = await client.complete(
        model="general-fast",
        messages=[{"role": "user", "content": "Summarize market activity."}],
    )
    return {"content": response.content}
```
