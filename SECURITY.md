# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| `0.1.x` | Yes |

## Security Invariants

1. **Consumer Virtual Keys Only:** `llm-gateway-sdk` only accepts consumer virtual keys issued by the LiteLLM Gateway administrator. It rejects `LITELLM_MASTER_KEY` and never falls back to `OPENAI_API_KEY` or other upstream provider credentials.
2. **Secret Redaction:** API keys are excluded from `GatewaySettings.__repr__()`, `GatewayClient.__repr__()`, `AsyncGatewayClient.__repr__()`, `str()`, `to_dict()`, and Pydantic `ValidationError` payloads.
3. **TLS Verification:** TLS verification (`verify_ssl=True`) is enabled by default.
4. **Origin & Header Protection:** URLs with embedded credentials, query strings, fragments, or non-HTTP(S) schemes are rejected. Custom `default_headers` cannot override `Authorization` or `Host`, and custom `http_client` instances with mismatched origins or `follow_redirects=True` are rejected.
5. **Privacy by Default:** SDK operations never log prompts, embeddings, or completions.

## Reporting a Vulnerability

Do **not** open a public GitHub issue for security vulnerabilities or leaked keys.
If a virtual API key is compromised, immediately notify the gateway administrator to revoke the key via the private administration runbook (`docs/ADMIN_KEY_RUNBOOK.md` in `llm-gateway`), and report SDK vulnerabilities privately via GitHub Security Advisories.

