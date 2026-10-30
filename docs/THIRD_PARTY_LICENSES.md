# Third-Party License Inventory

`llm-gateway-sdk` is licensed under the **MIT License**.

All mandatory and optional dependencies use permissive open-source licenses compatible with MIT distribution and commercial or personal use at zero cost.

## 1. Core Runtime Dependencies

| Package | Version Constraint | License | Purpose |
|---|---|---|---|
| `openai` | `>=1.40.0,<3.0.0` | Apache-2.0 | Official OpenAI-compatible HTTP/SSE client and type definitions |
| `httpx` (transitive) | `>=0.23.0,<1.0.0` | BSD-3-Clause | Underlying synchronous and asynchronous HTTP transport |
| `pydantic` (transitive) | `>=2.0.0,<3.0.0` | MIT | Response model typing and validation |
| `anyio` (transitive) | `>=3.5.0,<5.0.0` | MIT | Async concurrency primitives |
| `distro` (transitive) | `>=1.7.0,<2.0.0` | Apache-2.0 | OS platform metadata |
| `jiter` (transitive) | `>=0.4.0,<1.0.0` | MIT | Fast JSON parser |
| `sniffio` (transitive) | `>=1.1.0,<2.0.0` | MIT OR Apache-2.0 | Async library detection |
| `tqdm` (transitive) | `>=4.0.0` | MPL-2.0 AND MIT | Progress bar utility |
| `typing-extensions` (transitive) | `>=4.11,<5.0` | PSF-2.0 | Backported typing constructs |

## 2. Optional Integration Extras

| Extra | Package | Version Constraint | License | Commercial Restrictions |
|---|---|---|---|---|
| `settings` | `pydantic-settings` | `>=2.2.0,<3.0.0` | MIT | None |
| `structured` | `instructor` | `>=1.4.0,<2.0.0` | MIT | None |
| `langchain` | `langchain-openai` | `>=0.2.0,<2.0.0` | MIT | None |
| `observability` | `traceloop-sdk` | `>=0.30.0,<1.0.0` | Apache-2.0 | None (self-hosted OTLP supported; no SaaS required) |

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

