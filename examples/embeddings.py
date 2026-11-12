"""Vector embeddings example using ``llm_gateway_sdk``."""

from __future__ import annotations

import asyncio

from llm_gateway_sdk import GatewaySettings


async def main() -> None:
    settings = GatewaySettings.from_env()
    model = settings.default_embedding_model or "rag-embedding"

    async with settings.create_async_client() as client:
        response = await client.embed(
            model=model,
            input=["Polymarket rate cut probability", "Macroeconomic CPI forecast"],
        )
        for item in response.data:
            print(f"Document {item.index}: {len(item.embedding)} dimensions")


if __name__ == "__main__":
    asyncio.run(main())
