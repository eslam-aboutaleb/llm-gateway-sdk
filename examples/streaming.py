"""Streaming chat completion example using ``llm_gateway_sdk``."""

from __future__ import annotations

import asyncio

from llm_gateway_sdk import GatewaySettings


async def main() -> None:
    settings = GatewaySettings.from_env()
    model = settings.default_model or "general-fast"

    async with settings.create_async_client() as client:
        stream = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "Explain why centralized LLM routing simplifies operations.",
                }
            ],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices:
                print(chunk.choices[0].delta.content or "", end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
