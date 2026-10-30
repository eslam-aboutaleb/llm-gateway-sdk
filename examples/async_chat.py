"""Asynchronous chat completion example using ``llm_gateway_sdk``."""

from __future__ import annotations

import asyncio

from llm_gateway_sdk import GatewaySettings


async def main() -> None:
    settings = GatewaySettings.from_env()
    model = settings.default_model or "general-fast"

    async with settings.create_async_client() as client:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": "Summarize the benefits of an API gateway in one sentence.",
                }
            ],
        )
        print(response.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(main())
