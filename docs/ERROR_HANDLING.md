# Error Handling & Retry Safety

## 1. Exception Architecture

`llm-gateway-sdk` does **not** wrap runtime OpenAI API errors in a custom exception hierarchy. Instead:

1. **Configuration & Validation Errors** raise `GatewaySDKError` subclasses (which also inherit from `ValueError`):
   - `GatewaySDKError`
     - `GatewayConfigError`
       - `MissingGatewayConfigError` (missing `base_url`, `api_key`, or required model alias)
       - `InvalidGatewayURLError` (malformed URL, non-HTTP/HTTPS scheme, embedded credentials, query/fragment)
       - `InvalidGatewaySettingsError` (invalid timeout, negative retries, invalid dimensions, forbidden headers, master key usage)
2. **Runtime Gateway & Network Errors** raise native `openai` exceptions directly:
   - `openai.BadRequestError` (HTTP 400)
   - `openai.AuthenticationError` (HTTP 401 — invalid, expired, or revoked virtual key)
   - `openai.PermissionDeniedError` (HTTP 403 — model alias or route not allowed for key)
   - `openai.NotFoundError` (HTTP 404 — blocked route or unknown endpoint)
   - `openai.UnprocessableEntityError` (HTTP 422)
   - `openai.RateLimitError` (HTTP 429 — RPM, TPM, concurrency, or budget limit reached)
   - `openai.InternalServerError` (HTTP 500, 502, 503, 504)
   - `openai.APITimeoutError` (connect or read timeout)
   - `openai.APIConnectionError` (network or TLS verification failure)

## 2. Inspecting Request IDs for Gateway Debugging

Every `openai.APIStatusError` preserves the gateway's `request_id` (`x-request-id` header):

```python
import openai

try:
    response = client.chat.completions.create(
        model="general-fast",
        messages=[{"role": "user", "content": "Hello"}],
    )
except openai.APIStatusError as exc:
    print(f"Gateway returned HTTP {exc.status_code} (request_id={exc.request_id})")
```

## 3. Retry Strategy & Safety (`max_retries=0`)

The LiteLLM Gateway (`gateway/config/litellm.yaml`) is already configured with:
- `num_retries: 2` on status codes `[429, 500, 502, 503, 504]`
- Latency-based routing and model fallbacks

Therefore, `GatewaySettings` sets `max_retries=0` by default:
- Prevents multiplying `3` client attempts by `3` gateway attempts (`9` total provider calls).
- Prevents duplicate token billing when a client read timeout occurs while the upstream provider is still generating a completion.
- Never retries a streaming response after chunks have already been yielded.

