# LLM Proxy Architecture

## Goals

The proxy must support multiple model providers, multiple business scenarios, and grouped billing. Business services should not know provider-specific URLs, API keys, model names, or billing rules.

## Request identity

- `request_id`: idempotency key for one model call. Repeated requests with the same value return the saved result.
- `session_id`: billing group for many calls. One album generation task can call copywriting, image review, and retry flows under the same session.
- `business_scenario`: a stable business name, for example `moments_album` or `ai_secretary_moments_copywriting`.
- `purpose`: the concrete model task, for example `moments_album_copywriting`.

## Data model

- `llm_model_configs`: provider, model type, model name, base URL, API-key environment variable name, and charge defaults.
- `llm_business_scenarios`: route from business scenario and purpose to provider/model.
- `llm_call_records`: one row per model call. Stores request, response, usage, cost, status, and error.
- `llm_call_sessions`: totals per session. This is updated only when a new request record is created.

## Routing order

1. If the request explicitly sets `provider` and `model`, use them.
2. Otherwise, look for a matching row in `llm_business_scenarios`.
3. Otherwise, use environment defaults.
4. If provider calls fail and fallback is enabled, return a mock-compatible response while still recording the call.

## Billing policy

Provider token usage is kept separately from platform charged tokens.

Current default platform charges:

- Moments decision: 1,200 tokens.
- Moments copywriting: at least 12,000 tokens.
- VLM image review: 2,500 tokens per image.

For real providers, the proxy records provider usage and applies `max(min_charged_tokens, total_tokens * charged_token_multiplier)`.

## Provider adapters

The first real adapter is DeepSeek through its OpenAI-compatible chat completion API. Other providers can be added behind the same `ModelRoute` interface without changing business services.
