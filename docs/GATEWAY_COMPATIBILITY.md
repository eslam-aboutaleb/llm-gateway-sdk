# Gateway Compatibility & Contract Specification

**Gateway Repository:** [`eslam-aboutaleb/llm-gateway`](https://github.com/eslam-aboutaleb/llm-gateway)  
**Deployed LiteLLM Image:** `ghcr.io/berriai/litellm:main-v1.46.1` (`sha256:622532490d9161c51db67d0bc4027bdd35aaf8c0aef091647765b6fdd78b3d48`)  
**Ingress Reverse Proxy:** Caddy `2.8-alpine` (`gateway/caddy/Caddyfile`)

---

## 1. Public Gateway Route Contract

The production LiteLLM Gateway exposes an explicit route allowlist through Caddy TLS termination (`TLS 1.2` / `TLS 1.3`). All non-allowlisted routes return `404 Not Found` at the reverse proxy layer before reaching LiteLLM.

| HTTP Method & Route | Allowed by Caddy | Allowed for Virtual Keys | Timeout (Caddy / LiteLLM) | Purpose |
|---|---|---|---|---|
| `POST /v1/chat/completions` | Yes (`flush_interval -1`) | Yes | `300s` / `600s` | Sync, async, streaming, tool calling, and structured chat completions |
| `POST /v1/embeddings` | Yes | Yes | `120s` / `600s` | Single and batch vector embeddings |
| `GET /v1/models` | Yes | Yes | Default / `600s` | List allowed model aliases for the virtual key |
| `GET /health`, `/ready`, `/status` | Yes (rewritten to `/health/liveness`) | Unauthenticated | Default | Minimal public liveness probe |

### Prohibited Management Routes (Blocked at Ingress & Forbidden in SDK)

`llm-gateway-sdk` is strictly a **consumer inference client SDK**. It never calls, wraps, or exposes administrative routes:
- `/key/generate`, `/key/update`, `/key/delete`, `/key/info`, `/key/list`
- `/user/*`, `/team/*`, `/spend/*`, `/config/*`, `/model/*`, `/provider/*`, `/ui*`

---

## 2. Authentication & Key Policy

- **Header Format:** `Authorization: Bearer <consumer-virtual-key>`
- **Key Scope:** Virtual keys created by the gateway administrator inherit `key_defaults`:
  - `allowed_routes`: `["/v1/chat/completions", "/v1/embeddings", "/v1/models"]`
  - `duration`: `"30d"`, `max_budget`: `10` USD, `rpm_limit`: `20`, `tpm_limit`: `2000`, `max_parallel_requests`: `2` (unless customized per application/team).
- **Master Key Rejection:** Consumer applications must never configure or transmit `LITELLM_MASTER_KEY`. `llm-gateway-sdk` never reads `LITELLM_MASTER_KEY` for authentication and raises `InvalidGatewaySettingsError` if the consumer API key matches `LITELLM_MASTER_KEY` in the environment.

---

## 3. Approved Model Alias Catalog

From `gateway/config/litellm.yaml` and `gateway/config/model-catalog.yaml`:

| Model Alias | Mode | Capabilities | Default Upstream Mapping | Context / Max Output |
|---|---|---|---|---|
| `general-fast` | `chat` | `chat`, `streaming`, `function_calling` | `openai/gpt-4o-mini` | 128,000 / 4,096 |
| `general-reasoning` | `chat` | `chat`, `streaming`, `function_calling`, `reasoning` | `openai/gpt-4o` (fallback: `gpt-4o-mini`) | 128,000 / 4,096 |
| `structured-output` | `chat` | `chat`, `streaming`, `structured_output`, `json_mode` | `openai/gpt-4o` | 128,000 / 4,096 |
| `agent-tools` | `chat` | `chat`, `streaming`, `function_calling`, `parallel_tools` | `openai/gpt-4o` | 128,000 / 4,096 |
| `rag-embedding` | `embedding` | `embeddings` (1,536 dimensions) | `openai/text-embedding-3-small` | 8,191 input tokens |
| `rag-embedding-large` | `embedding` | `embeddings` (3,072 dimensions, disabled by default) | `openai/text-embedding-3-large` | 8,191 input tokens |

> **Important:** `llm-gateway-sdk` does **not** hardcode or restrict model names to this list. Gateway operators may add key-specific aliases (via `scripts/set-key-model-alias.py`) or new catalog entries at any time. Consumers may pass any model alias string permitted for their virtual key.

---

## 4. Retry & Timeout Division of Responsibility

| Layer | Configured Retries | Configured Timeout | Responsibility |
|---|---|---|---|
| **LiteLLM Gateway Router** (`litellm.yaml`) | `num_retries: 2` on `[429, 500, 502, 503, 504]` (`retry_after: 1s`) | `600s` (Caddy ingress: `300s` chat, `120s` embeddings) | Upstream provider retries, latency-based routing, and model fallbacks |
| **`llm-gateway-sdk` Client** | `max_retries=0` (default) | `timeout=30.0` (default, configurable per client or per request) | Single authenticated request to the gateway without multiplying upstream retries |

---

## 5. Error & Status Code Semantics

`llm-gateway-sdk` maps HTTP status codes and transport errors returned by the gateway directly to typed, provider-agnostic SDK exceptions:

| HTTP Status | `llm-gateway-sdk` Exception | Gateway Cause |
|---|---|---|
| `400 Bad Request` | `GatewayBadRequestError` | Invalid parameters, unsupported model alias, or Caddy 4xx error handler |
| `401 Unauthorized` | `GatewayAuthenticationError` | Missing, invalid, expired, or revoked virtual API key |
| `403 Forbidden` | `GatewayPermissionDeniedError` | Key not authorized for the requested model alias or route |
| `404 Not Found` | `GatewayNotFoundError` | Non-allowlisted route blocked by Caddy or unknown endpoint |
| `408 Request Timeout` / Timeout | `GatewayTimeoutError` | Client or gateway timeout exceeded |
| `422 Unprocessable Entity` | `GatewayUnprocessableEntityError` | Request schema validation failure |
| `429 Too Many Requests` | `GatewayRateLimitError` | Virtual key RPM, TPM, concurrency, or budget limit exceeded |
| `500` / `502` / `503` / `504` | `GatewayInternalServerError` | Upstream provider failure after gateway retries or Caddy 503 error handler |
| Network / TLS Error | `GatewayConnectionError` | DNS, TCP, or TLS certificate verification failure |

---

## 6. Compatibility Matrix

| `llm-gateway-sdk` Version | Python Versions | Core Dependencies | Gateway Proxy Version | Tested Endpoints & Capabilities |
|---|---|---|---|---|
| `0.1.0` | `>=3.10` (`3.10`, `3.11`, `3.12`, `3.13`) | `httpx>=0.27.0,<1.0.0`, `pydantic>=2.7.0,<3.0.0` | `v1.46.1` (HTTP/SSE JSON API v1) | `POST /v1/chat/completions` (sync, async, streaming, tools, JSON/structured), `POST /v1/embeddings`, `GET /v1/models`, `GET /health` |

