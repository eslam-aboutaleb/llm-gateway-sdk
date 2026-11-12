# Contributing to `llm-gateway-sdk`

Thank you for contributing to `llm-gateway-sdk`! This document outlines the architectural invariants, repository structure, development workflow, and pull request requirements.

---

## 1. Architectural Principles

1. **Provider- & Framework-Agnostic Core:** `llm-gateway-sdk` is built directly on `httpx` and `pydantic` with zero dependency on vendor SDKs (`openai`) or orchestration frameworks (`langchain`).
2. **Preserve Strict Unidirectional Layering:**
   - **Layer 0 (`constants.py`, `exceptions.py`):** Domain constants, header names, blocklists, and configuration/runtime exception hierarchy. Imports nothing from other SDK modules.
   - **Layer 1 (`validation.py`):** Stateless input validation and security boundary enforcement. Imports only Layer 0, Python stdlib, and `httpx`.
   - **Layer 2 (`settings.py`, `models.py`):** Immutable `GatewaySettings` dataclass, `_EnvironmentLookup`, typed Pydantic response models (`ChatResponse`, `EmbeddingResponse`, `ModelListResponse`), and SSE stream iterators (`GatewayStream`, `AsyncGatewayStream`).
   - **Layer 3 (`clients.py`):** `GatewayClient`, `AsyncGatewayClient`, and `create_client()` / `create_async_client()` factory functions. Imports Layers 0–2.
   - **Layer 4 (`integrations/*`):** Optional configuration adapter (`pydantic_settings.py`). Imported lazily so the base package never requires optional packages.
3. **Never Leak Secrets:** Never include `api_key`, `Authorization` headers, embedded URL credentials, or raw user inputs in exception messages, `repr()`, `str()`, `to_dict(redact_secrets=True)`, or logs.
4. **Keyless CI:** All default unit, integration, and compatibility tests must run offline using `httpx.MockTransport` without requiring live gateway credentials or network access.

---

## 2. Repository Structure

```text
llm-gateway-sdk/
├── src/llm_gateway_sdk/
│   ├── __init__.py             # Public package exports & __version__
│   ├── constants.py            # Layer 0: Defaults, header names & security blocklists
│   ├── exceptions.py           # Layer 0: GatewaySDKError hierarchy
│   ├── validation.py           # Layer 1: Pure validation & security boundary functions
│   ├── models.py               # Layer 2: Typed Pydantic models & SSE stream iterators
│   ├── settings.py             # Layer 2: Immutable GatewaySettings & from_env()
│   ├── clients.py              # Layer 3: GatewayClient & AsyncGatewayClient
│   └── integrations/           # Layer 4: Optional configuration adapter
│       └── pydantic_settings.py
├── tests/
│   ├── conftest.py             # Autouse env isolation & MockTransport client fixtures
│   ├── unit/                   # Fast unit tests for validation, settings, factories & adapters
│   ├── integration/            # MockTransport tests for chat, async, streaming, tools, embeddings
│   └── compatibility/          # Gateway contract + opt-in @pytest.mark.live tests
├── examples/                   # Runnable example scripts
└── docs/                       # Architecture, configuration, lifecycle & compatibility guides
```

---

## 3. Local Development Setup

Prerequisites: Python `3.10+` and [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. Install all development and test dependencies
uv sync --group dev

# 2. Run Ruff linter and formatter checks
uv run ruff check .
uv run ruff format --check .

# 3. Run strict Mypy type checking across src/, tests/, and examples/
uv run mypy

# 4. Run keyless test suite with branch coverage (>= 90% required)
uv run pytest --cov=llm_gateway_sdk --cov-report=term-missing
```

---

## 4. Pull Request Checklist

- [ ] Layer boundaries and minimal core dependencies (`httpx` and `pydantic` only) are preserved.
- [ ] All new validation or configuration errors inherit from `GatewayConfigError` and never echo secret values.
- [ ] Unit/integration tests cover both happy paths and failure cases using `httpx.MockTransport` (`>= 90%` branch coverage).
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy` pass with zero warnings or errors.
- [ ] Relevant documentation in `README.md` and `docs/` is updated if public behavior changes.
