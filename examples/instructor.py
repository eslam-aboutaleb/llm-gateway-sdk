"""Structured output extraction using the optional ``instructor`` integration."""

from __future__ import annotations

from pydantic import BaseModel, Field

from llm_gateway_sdk import GatewaySettings
from llm_gateway_sdk.integrations.instructor import create_instructor_client


class MarketSignal(BaseModel):
    market_title: str = Field(..., description="Title of the prediction market")
    recommendation: str = Field(..., description="One of: buy_yes, buy_no, hold")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")


def main() -> None:
    settings = GatewaySettings.from_env()
    model = settings.default_model or "structured-output"

    with settings.create_client() as raw_client:
        structured_client = create_instructor_client(raw_client)
        signal: MarketSignal = structured_client.chat.completions.create(
            model=model,
            response_model=MarketSignal,
            max_retries=1,
            messages=[
                {
                    "role": "user",
                    "content": "Market: Will Fed hold rates in November? Current YES price: 0.92.",
                }
            ],
        )
        print(signal.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
