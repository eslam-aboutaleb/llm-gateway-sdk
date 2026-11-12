"""Synchronous chat completion and model discovery example using ``llm_gateway_sdk``."""

from __future__ import annotations

from llm_gateway_sdk import GatewaySettings


def main() -> None:
    settings = GatewaySettings.from_env()
    model = settings.default_model or "general-fast"

    with settings.create_client() as client:
        models = client.list_models()
        print("Available gateway aliases:", models.model_ids)

        response = client.complete(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": "Hello from llm-gateway-sdk!"},
            ],
        )
        print(response.content)


if __name__ == "__main__":
    main()
