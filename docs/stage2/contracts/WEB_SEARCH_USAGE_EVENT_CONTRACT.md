# Web Search Usage Event Contract

Status: draft for analytics/cost review.

## Purpose

Define sanitized Web Search events needed for pilot cost visibility, debugging
and policy audit without storing raw queries or result bodies.

## Events

- `web_search_request_started`
- `web_search_request_completed`
- `web_search_request_failed`
- `web_search_request_blocked_by_policy`
- `web_search_provider_rate_limited`
- `web_search_source_fetch_failed`

## Common Fields

Required fields:

- `timestamp`
- `tenant_ref` or deployment scope reference
- `group_ref`
- `user_ref`
- `scenario_ref` or workspace/template reference
- `model_ref`
- `provider`
- `engine`
- `mode`
- `query_hash`
- `result_count`
- `concurrency`
- `web_loader_used`
- `status`
- `latency_ms`
- `error_type`
- `estimated_cost_unit`

Optional fields:

- `provider_request_count`
- `source_fetch_count`
- `source_fetch_failed_count`
- `timeout_ms`
- `rate_limit_retry_count`
- `policy_rule_ref`
- `runtime_version`

## Field Rules

- `query_hash` is a stable salted hash, not raw query text.
- `user_ref` must be an internal reference, not an email or display name unless
  the retention policy allows it.
- `estimated_cost_unit` should be provider-neutral: request count, credit count,
  or configured cost bucket.
- `error_type` must be categorical: `timeout`, `rate_limited`, `no_results`,
  `policy_blocked`, `provider_error`, `source_fetch_error`,
  `permission_denied`, `unknown`.

## Prohibited Event Content

Do not store by default:

- raw query text;
- full search result list;
- fetched page content;
- provider API key or auth header;
- private URL values;
- customer document text;
- full user prompt or chat transcript.

## Pilot Acceptance

The first pilot may use native OpenWebUI analytics plus provider dashboard
counts if hard event capture is not available. If native visibility is
insufficient, record the gap and do not build hard billing in the first slice
unless the owner explicitly requires it.
