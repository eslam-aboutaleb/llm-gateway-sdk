# Contributing to `llm-gateway-sdk`

Thank you for contributing to `llm-gateway-sdk`! This document outlines the architectural invariants, repository structure, development workflow, and pull request requirements.

---

## 1. Architectural Principles

1. **Keep the Core Thin:** `llm-gateway-sdk` configures and returns native `openai.OpenAI` and `openai.AsyncOpenAI` clients. Do not wrap resource methods (`chat.completions`, `embeddings`, `models`) or introduce custom HTTP transports.
2. **Preserve Strict Unidirectional Layering:**
   - **Layer 0 (`constants.py`, `exceptions.py`):** Domain constants, header names, blocklists, and configuration exception hierarchy. Imports nothing from other SDK modules.
   - **Layer 1 (`validation.py`):** Stateless input validation and security boundary enforcement. Imports only Layer 0, Python stdlib, and `httpx`.
   - **Layer 2 (`settings.py`):** Immutable `GatewaySettings` dataclass and `_EnvironmentLookup`. Imports Layers 0–1 (and delegates `create_client` / `create_async_client` to Layer 3).
   - **Layer 3 (`clients.py`):** Native `OpenAI` / `AsyncOpenAI` factory functions and shared option resolution. Imports Layers 0–2.
   - **Layer 4 (`integrations/*`):** Optional ecosystem adapters (`pydantic-settings`, `instructor`, `langchain-openai`, `traceloop-sdk`). Imported lazily so the base package never requires optional packages.
3. **Never Leak Secrets:** Never include `api_key`, `Authorization` headers, embedded URL credentials, or raw user inputs in exception messages, `repr()`, `str()`, `to_dict(redact_secrets=True)`, logs, or telemetry attributes.
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
│   ├── settings.py             # Layer 2: Immutable GatewaySettings & from_env()
│   ├── clients.py              # Layer 3: create_client() & create_async_client()
│   └── integrations/           # Layer 4: Optional framework adapters
│       ├── pydantic_settings.py
│       ├── instructor.py
│       ├── langchain.py
│       └── openllmetry.py
├── tests/
│   ├── conftest.py             # Autouse env isolation & MockTransport client fixtures
│   ├── unit/                   # Fast unit tests for validation, settings, factories & adapters
│   ├── integration/            # MockTransport tests for chat, async, streaming, tools, embeddings
│   └── compatibility/          # OpenAI & LiteLLM Gateway contract + opt-in @pytest.mark.live tests
├── examples/                   # Runnable example scripts
└── docs/                       # Architecture, configuration, security & operations guides
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

- [ ] Layer boundaries and minimal core dependencies (`openai` only) are preserved.
- [ ] All new validation or configuration errors inherit from `GatewayConfigError` and never echo secret values.
- [ ] Unit/integration tests cover both happy paths and failure cases using `httpx.MockTransport` (`>= 90%` branch coverage).
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy` pass with zero warnings or errors.
- [ ] Relevant documentation in `README.md` and `docs/` is updated if public behavior changes.
