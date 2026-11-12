"""Streaming chat completion example using ``llm_gateway_sdk``."""

from __future__ import annotations

import asyncio

from llm_gateway_sdk import GatewaySettings


async def main() -> None:
    settings = GatewaySettings.from_env()
    model = settings.default_model or "general-fast"

    async with (
        settings.create_async_client() as client,
        await client.stream(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "Explain why centralized LLM routing simplifies operations.",
                }
            ],
        ) as stream,
    ):
        async for delta_text in stream.iter_text():
            print(delta_text, end="", flush=True)
        print()


if __name__ == "__main__":
    asyncio.run(main())
