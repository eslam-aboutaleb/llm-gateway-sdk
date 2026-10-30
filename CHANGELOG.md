# Changelog

All notable changes to `llm-gateway-sdk` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-30

### Added
- **Layered Core Architecture:**
  - `constants.py` and `exceptions.py` (Layer 0) providing typed configuration exceptions (`GatewaySDKError`, `GatewayConfigError`, `MissingGatewayConfigError`, `InvalidGatewayURLError`, `InvalidGatewaySettingsError`).
  - `validation.py` (Layer 1) enforcing strict URL, virtual key, timeout, retry, embedding dimension, HTTP header, and origin checks.
  - `settings.py` (Layer 2) providing the immutable `GatewaySettings` dataclass with `from_env()`, secret redaction (`[REDACTED]`), and opt-in legacy `LITELLM_*` environment compatibility.
  - `clients.py` (Layer 3) providing `create_client()` and `create_async_client()` returning native `openai.OpenAI` and `openai.AsyncOpenAI` instances with `max_retries=0` by default.
- **Optional Framework Integrations (Layer 4):**
  - `llm_gateway_sdk.integrations.pydantic_settings` (`[settings]` extra): `GatewayBaseSettings` and `connection_options` with automatic validation error redaction.
  - `llm_gateway_sdk.integrations.instructor` (`[structured]` extra): `create_instructor_client` and `create_async_instructor_client`.
  - `llm_gateway_sdk.integrations.langchain` (`[langchain]` extra): `create_chat_model` and `create_embeddings_model` backed by `langchain-openai`.
  - `llm_gateway_sdk.integrations.openllmetry` (`[observability]` extra): `configure_observability` with privacy-by-default (`TRACELOOP_TRACE_CONTENT="false"`).
- **Testing & Documentation:**
  - Complete unit, integration, and gateway contract test suites (`tests/`).
  - Working example scripts (`examples/`) and comprehensive developer documentation (`docs/`).

