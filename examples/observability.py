"""Privacy-first OpenLLMetry observability example (`llm-gateway-sdk[observability]`)."""

from __future__ import annotations

from llm_gateway_sdk import GatewaySettings
from llm_gateway_sdk.integrations.openllmetry import configure_observability


def main() -> None:
    settings = GatewaySettings.from_env()

    # Explicitly initialize OpenLLMetry with prompt/completion content recording disabled
    obs_config = configure_observability(
        settings,
        record_content=False,
    )
    print(f"Initialized observability for {obs_config.app_name} ({obs_config.environment})")

    with settings.create_client() as client:
        response = client.chat.completions.create(
            model=settings.default_model or "general-fast",
            messages=[{"role": "user", "content": "Hello with safe OpenTelemetry tracing!"}],
        )
        print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
