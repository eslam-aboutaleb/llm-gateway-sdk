"""Synchronous chat completion example using ``llm_gateway_sdk``."""

from __future__ import annotations

from llm_gateway_sdk import GatewaySettings


def main() -> None:
    settings = GatewaySettings.from_env()
    model = settings.default_model or "general-fast"

    with settings.create_client() as client:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "Hello from llm-gateway-sdk!"},
            ],
        )
        print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
