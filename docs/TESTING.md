# Testing Guide

## 1. Running Keyless Unit, Integration, and Contract Tests

All default tests run offline using `httpx.MockTransport` and deterministic fixtures. No live gateway or provider API keys are required.

```bash
uv run pytest
```

Run with branch coverage report:

```bash
uv run pytest --cov=llm_gateway_sdk --cov-report=term-missing
```

## 2. Static Analysis & Type Checking

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/llm_gateway_sdk
```

## 3. Opt-In Live Gateway Integration Tests

Live tests against a running LiteLLM Gateway are skipped by default and only run when `LLM_GATEWAY_LIVE_TESTS=true` is explicitly set in the environment:

```bash
LLM_GATEWAY_LIVE_TESTS=true \
LLM_GATEWAY_BASE_URL=https://gateway.example.com/v1 \
LLM_GATEWAY_API_KEY=sk-test-virtual-key \
LLM_GATEWAY_DEFAULT_MODEL=general-fast \
LLM_GATEWAY_DEFAULT_EMBEDDING_MODEL=rag-embedding \
uv run pytest -m live -q
```

> **Warning:** Live tests consume the test virtual key's rate limit and budget. Always use a dedicated low-budget test key and never attach production keys to automated PR workflows.

