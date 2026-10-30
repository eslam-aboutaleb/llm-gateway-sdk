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
    response = client.chat.completions.create(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.choices[0].message.content)
```

## 4. Asynchronous Chat Completion

```python
import asyncio
from llm_gateway_sdk import GatewaySettings


async def main() -> None:
    settings = GatewaySettings.from_env()
    async with settings.create_async_client() as client:
        response = await client.chat.completions.create(
            model="general-fast",
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(response.choices[0].message.content)


asyncio.run(main())
```

## 5. Streaming

```python
stream = await client.chat.completions.create(
    model="general-fast",
    messages=[{"role": "user", "content": "Explain this."}],
    stream=True,
)

async for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="")
```

## 6. Embeddings

```python
response = await client.embeddings.create(
    model="rag-embedding",
    input=["Example document"],
)
print(len(response.data[0].embedding))
```

