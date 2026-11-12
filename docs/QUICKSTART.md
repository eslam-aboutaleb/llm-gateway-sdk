# Quickstart Guide

## 1. Install `llm-gateway-sdk`

```bash
pip install llm-gateway-sdk
```

Or using `uv`:

```bash
uv add "llm-gateway-sdk @ git+https://github.com/eslam-aboutaleb/llm-gateway-sdk.git@v0.1.0"
```

## 2. Configure Environment Variables

```dotenv
LLM_GATEWAY_BASE_URL=https://gateway.example.com/v1
LLM_GATEWAY_API_KEY=sk-consumer-key
LLM_GATEWAY_DEFAULT_MODEL=general-fast
LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL=rag-embedding
```

## 3. Synchronous Chat Completion

```python
from llm_gateway_sdk import GatewaySettings

settings = GatewaySettings.from_env()

with settings.create_client() as client:
    response = client.complete(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.content)
```

## 4. Asynchronous Chat Completion

```python
import asyncio
from llm_gateway_sdk import GatewaySettings


async def main() -> None:
    settings = GatewaySettings.from_env()
    async with settings.create_async_client() as client:
        response = await client.complete(
            model="general-fast",
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(response.content)


asyncio.run(main())
```

## 5. Real-Time SSE Streaming

```python
async with await client.stream(
    model="general-fast",
    messages=[{"role": "user", "content": "Explain this."}],
) as stream:
    async for delta in stream.iter_text():
        print(delta, end="", flush=True)
```

## 6. Vector Embeddings

```python
response = await client.embed(
    model="rag-embedding",
    input=["Example document"],
)
print(len(response.embedding))
```
