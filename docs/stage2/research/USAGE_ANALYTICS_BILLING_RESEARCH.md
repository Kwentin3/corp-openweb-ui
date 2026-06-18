# Usage Analytics Billing Research

## 1. Question

Is native OpenWebUI analytics enough for Stage 2 cost visibility, or is a gateway/hard billing slice needed?

## 2. Research status

Status: researched from official OpenWebUI and LiteLLM docs on 2026-06-18.

Result type: decision input. No deployed analytics UI was inspected.

## 3. Findings

- OpenWebUI documents an Admin Panel Analytics feature.
- Analytics is admin-only and covers message volume, token usage, model performance, user activity, time periods and group filtering.
- OpenWebUI analytics data is derived from message history stored in the instance database.
- This is a good fit for PRD-1 "basic analytics / cost visibility" if the deployed version exposes it.
- Native analytics is not the same as hard budget enforcement, provider-side spend limits or guaranteed quota blocking.
- OpenWebUI filter functions can be used for patterns such as cost tracking and rate limiting, but that is custom extension work and needs design/testing.
- LiteLLM Proxy explicitly supports virtual keys, spend tracking, budgets and rate limits per key/team/user. It is the right class of tool for hard budgets, but adding it changes architecture and was outside PRD-0.

## 4. Recommendation

For Practical Stage 2:

- start with native OpenWebUI analytics after runtime verification;
- maintain a simple provider price catalog in docs/admin handoff;
- avoid promising hard billing or automatic spend blocking;
- create a separate ADR only if the customer requires enforceable limits, per-team budgets, virtual keys or provider routing.

## 5. Decision options

| Option | Use when | Tradeoff |
| ------ | -------- | -------- |
| Native OpenWebUI analytics | Need basic visibility and admin reporting | Low architecture change; no hard budget guarantee |
| OpenWebUI filter/custom logging | Need lightweight custom metadata/rate checks | Custom code/upgrade risk; must test carefully |
| LiteLLM/gateway | Need hard budgets, virtual keys, routing, provider spend enforcement | More infra, secrets, DB, ops and failure modes |

## 6. Runtime proof needed

- Verify analytics tab exists in deployed/staging version.
- Generate sample usage across two users/groups and two models.
- Confirm token/model/user/group breakdown is sufficient for customer reporting.
- Compare provider invoice/usage dashboard with OpenWebUI estimates.

## 7. Sources

- https://docs.openwebui.com/features/administration/analytics/
- https://docs.openwebui.com/features/extensibility/plugin/functions/filter/
- https://docs.litellm.ai/docs/simple_proxy
- https://docs.litellm.ai/docs/proxy/virtual_keys
- https://docs.litellm.ai/docs/proxy/users
- https://docs.litellm.ai/docs/proxy/architecture

## 8. Status

Research complete. Native analytics first; hard billing remains optional/future ADR.
