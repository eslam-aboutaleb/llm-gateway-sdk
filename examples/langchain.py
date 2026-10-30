"""LangChain integration example using ``llm-gateway-sdk[langchain]``."""

from __future__ import annotations

from llm_gateway_sdk import GatewaySettings
from llm_gateway_sdk.integrations.langchain import (
    create_chat_model,
    create_embeddings_model,
)


def main() -> None:
    settings = GatewaySettings.from_env()

    llm = create_chat_model(
        settings=settings,
        model=settings.default_model or "general-reasoning",
        temperature=0.2,
    )
    reply = llm.invoke("Give a one-sentence overview of prediction market liquidity.")
    print("Chat response:", reply.content)

    embeddings = create_embeddings_model(
        settings=settings,
        model=settings.default_embedding_model or "rag-embedding",
    )
    vector = embeddings.embed_query("Prediction market liquidity")
    print(f"Embedding dimensions: {len(vector)}")


if __name__ == "__main__":
    main()
