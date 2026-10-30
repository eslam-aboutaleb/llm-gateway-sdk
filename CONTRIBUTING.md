# Contributing to `llm-gateway-sdk`

Thank you for contributing to `llm-gateway-sdk`!

## Architectural Principles

1. **Keep the Core Thin:** `llm-gateway-sdk` configures and returns native `openai.OpenAI` and `openai.AsyncOpenAI` clients. Do not wrap resource methods or create parallel HTTP transports.
2. **Preserve Strict Layering:**
   - Layer 0 (`constants.py`, `exceptions.py`) -> no internal imports.
   - Layer 1 (`validation.py`) -> imports only Layer 0.
   - Layer 2 (`settings.py`) -> imports only Layers 0–1 (and delegates client creation to Layer 3).
   - Layer 3 (`clients.py`) -> imports Layers 0–2.
   - Layer 4 (`integrations/*`) -> optional adapters importing Layers 0–3 lazily.
3. **Never Leak Secrets:** Never include `api_key`, `Authorization` headers, or raw user inputs in exception messages, `repr()`, logs, or telemetry attributes.
4. **Keyless CI:** All default unit, integration, and compatibility tests must run offline using `httpx.MockTransport` without requiring live gateway credentials.

## Local Development Setup

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run mypy src/llm_gateway_sdk
uv run pytest
```

