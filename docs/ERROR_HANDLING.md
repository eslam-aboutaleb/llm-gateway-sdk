# Error Handling & Retry Safety

## 1. Provider-Agnostic Exception Architecture

`llm-gateway-sdk` provides a unified, provider-agnostic exception hierarchy rooted at `GatewaySDKError`:

1. **Configuration & Validation Errors** inherit from both `GatewaySDKError` and `ValueError`:
   - `GatewaySDKError`
     - `GatewayConfigError(GatewaySDKError, ValueError)`
       - `MissingGatewayConfigError` (missing `base_url`, `api_key`, or required model alias)
       - `InvalidGatewayURLError` (malformed URL, non-HTTP/HTTPS scheme, embedded credentials, query/fragment)
       - `InvalidGatewaySettingsError` (invalid timeout, negative retries, invalid dimensions, forbidden headers, master key usage)
2. **Runtime Gateway & Network Errors** inherit from `GatewayRuntimeError(GatewaySDKError)`:
   - `GatewayConnectionError` (network or TLS verification failure)
     - `GatewayTimeoutError` (connect, read, or write timeout)
   - `GatewayAPIStatusError` (non-2xx HTTP status returned by the gateway)
     - `GatewayBadRequestError` (HTTP 400)
     - `GatewayAuthenticationError` (HTTP 401 — invalid, expired, or revoked virtual key)
     - `GatewayPermissionDeniedError` (HTTP 403 — model alias or route not allowed for key)
     - `GatewayNotFoundError` (HTTP 404 — blocked management route or unknown endpoint)
     - `GatewayUnprocessableEntityError` (HTTP 422)
     - `GatewayRateLimitError` (HTTP 429 — RPM, TPM, concurrency, or budget limit reached)
     - `GatewayInternalServerError` (HTTP 500, 502, 503, 504)

## 2. Inspecting Request IDs for Gateway Debugging

Every `GatewayAPIStatusError` preserves the gateway's `request_id` (`x-request-id` header) and `status_code`:

```python
from llm_gateway_sdk import GatewayAPIStatusError

try:
    response = client.complete(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
except GatewayAPIStatusError as exc:
    print(f"Gateway returned HTTP {exc.status_code} (request_id={exc.request_id})")
```

## 3. Retry Strategy & Timeout Configuration

The LLM Gateway already handles upstream provider retries and model fallbacks automatically. Therefore, `GatewaySettings` defaults to `max_retries=0` and `timeout=30.0`:
- Prevents multiplying client retries with gateway retries.
- Prevents duplicate token billing when a client read timeout occurs while the upstream provider is still generating a completion.
- Never retries a streaming response after chunks have already been yielded.

You can customize `timeout` per client or per request:

```python
with settings.create_client(timeout=60.0) as client:
    response = client.complete(
        model="general-reasoning",
        messages=[{"role": "user", "content": "Analyze this scenario."}],
        timeout=90.0,
    )
```
