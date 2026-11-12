# Third-Party License Inventory

`llm-gateway-sdk` is licensed under the **MIT License**.

All mandatory and optional dependencies use permissive open-source licenses compatible with MIT distribution and commercial or personal use at zero cost.

## 1. Core Runtime Dependencies

| Package | Version Constraint | License | Purpose |
|---|---|---|---|
| `httpx` | `>=0.27.0,<1.0.0` | BSD-3-Clause | Synchronous and asynchronous HTTP/SSE transport |
| `pydantic` | `>=2.7.0,<3.0.0` | MIT | Response model typing and validation |
| `anyio` (transitive) | `>=3.5.0,<5.0.0` | MIT | Async concurrency primitives |
| `certifi` (transitive) | `*` | MPL-2.0 | Root CA bundle for TLS verification |
| `httpcore` (transitive) | `*` | BSD-3-Clause | Low-level HTTP transport |
| `idna` (transitive) | `*` | BSD-3-Clause | Internationalized domain names |
| `typing-extensions` (transitive) | `>=4.11,<5.0` | PSF-2.0 | Backported typing constructs |

## 2. Optional Integration Extras

| Extra | Package | Version Constraint | License | Commercial Restrictions |
|---|---|---|---|---|
| `settings` | `pydantic-settings` | `>=2.2.0,<3.0.0` | MIT | None |

## 3. Development & CI Dependencies

| Package | License | Purpose |
|---|---|---|
| `pytest` | MIT | Test runner |
| `pytest-asyncio` | Apache-2.0 | Async test execution |
| `pytest-cov` | MIT | Code coverage reporting |
| `ruff` | MIT | Linter and formatter |
| `mypy` | MIT | Static type checker |
| `hatchling` | MIT | PEP 517 build backend |
| `build` | MIT | Package builder |
| `twine` | Apache-2.0 | Distribution metadata validator |
