# Versioning & Compatibility Policy

`llm-gateway-sdk` follows [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR (`X.0.0`):** Incompatible changes to the public `GatewaySettings`, `create_client`, `create_async_client`, or optional integration signatures.
- **MINOR (`0.Y.0` / `X.Y.0`):** Backward-compatible new features or optional integrations.
- **PATCH (`0.Y.Z` / `X.Y.Z`):** Backward-compatible bug fixes, security hardening, or documentation updates.

## Release Roadmap

- `0.1.0`: Initial release with layered core (`GatewaySettings`, `create_client`, `create_async_client`), optional integrations (`settings`, `structured`, `langchain`, `observability`), and initial `polymarket-ai-trading` migration.
- `0.2.0`: Compatible feature refinements based on multi-service adoption.
- `1.0.0`: Long-term stable public API guarantee.

## Decoupling from LiteLLM Proxy Versions

`llm-gateway-sdk` version numbers are **decoupled** from LiteLLM Proxy image versions (`v1.46.1`, etc.). Because the SDK targets the stable OpenAI-compatible HTTP contract (`/v1/chat/completions`, `/v1/embeddings`, `/v1/models`), routine gateway patches or upstream model switches do not require an SDK upgrade.

