# AIXiaoMi LLM Proxy

AIXiaoMi unified model proxy service.

This service hides model providers from business services. Business services call one internal API with a `purpose`, `business_scenario`, optional `session_id`, and optional `request_id`. The proxy routes the request to the configured provider, records every call, and aggregates billing by session.

## Current scope

- Text model endpoint: `POST /v1/chat/completions`
- Vision endpoint placeholder: `POST /v1/vision/analyze`
- Billing lookup by session: `GET /v1/billing/sessions/{session_id}`
- Billing lookup by request: `GET /v1/billing/requests/{request_id}`
- Route inspection: `GET /v1/routes`
- Providers:
  - `mock`
  - `deepseek` for Moments copywriting when configured

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8004
```

## Important environment variables

```env
DATABASE_URL="mysql+pymysql://user:password@host:3306/llm_proxy_db?charset=utf8mb4"
MOCK_MODE="false"
DEEPSEEK_API_KEY="set in environment only"
DEEPSEEK_BASE_URL="https://api.deepseek.com"
MOMENTS_COPYWRITING_PROVIDER="deepseek"
MOMENTS_COPYWRITING_MODEL="deepseek-v4-flash"
FALLBACK_TO_MOCK_ON_PROVIDER_ERROR="true"
```

Do not commit API keys. Use `.env` only for local development and server environment files for deployment.

## Idempotency and billing

- `request_id` is the idempotency key. Repeating the same `request_id` returns the stored response and does not add another charge.
- `session_id` groups many model calls into one billable unit, such as one album generation task.
- Every successful or failed call is stored in `llm_call_records`.
- Session totals are stored in `llm_call_sessions`.

## DeepSeek notes

The current default base URL is `https://api.deepseek.com`, and the default Moments copywriting model is `deepseek-v4-flash`.

## Test

```bash
pytest
```
