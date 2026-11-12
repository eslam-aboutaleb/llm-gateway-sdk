# Security & Privacy Guide

## 1. Consumer Virtual Keys Only

`llm-gateway-sdk` is strictly designed for consumer applications using **Gateway virtual API keys**:
- Never configure or pass `LITELLM_MASTER_KEY` to a consumer service.
- If `LITELLM_MASTER_KEY` is present in the environment and matches the configured `api_key`, `GatewaySettings` and `GatewaySettings.from_env()` raise `InvalidGatewaySettingsError`.
- Never silently falls back to `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or other upstream provider keys.

## 2. Secret Redaction

- `GatewaySettings.__repr__()`, `GatewayClient.__repr__()`, and `AsyncGatewayClient.__repr__()` always replace `api_key` with `'[REDACTED]'`.
- `GatewaySettings.to_dict()` redacts `api_key` unless `redact_secrets=False` is explicitly passed.
- `GatewayBaseSettings` (Pydantic Settings extra) wraps validation with `redact_validation_errors` so `ValidationError.errors()` and `ValidationError.json()` replace all input values with `'[redacted]'`.
- No validator or HTTP error mapper ever echoes the raw `api_key` or URL credentials in exception messages.

## 3. URL & Origin Validation

`validate_base_url` rejects:
- Non-HTTP(S) schemes (`ftp://`, `ws://`, `file://`, etc.).
- URLs containing `username:password@` credentials.
- URLs containing `?query` strings or `#fragment` identifiers.
- URLs containing whitespace, ASCII control characters, or backslashes (`\`).
- Invalid ports (`0` or `> 65535`).

Furthermore, `validate_http_client_origin` verifies that any custom `httpx.Client` or `httpx.AsyncClient` passed to `create_client()` / `create_async_client()`:
- Does not have `follow_redirects=True` (which could forward the `Authorization: Bearer <key>` header to a third-party redirect target).
- Does not have custom `auth` configured on the `httpx` client.
- Does not have a `base_url` pointing to a different scheme, hostname, or port than `settings.base_url`.

## 4. TLS Verification

- `verify_ssl=True` is the default on `GatewaySettings`.
- Setting `verify_ssl=False` is only for local self-signed testing and should never be enabled in production.

## 5. Prompt & Response Privacy

- The SDK performs zero logging of prompt messages or completion outputs.
