# Usage Analytics Billing Research

## 1. Question

Is native OpenWebUI analytics enough for Stage 2 cost visibility, or is a gateway/hard billing slice needed?

## 2. Why it matters for PRD-1

Stage 2 needs basic analytics/cost visibility, not automatic hard billing.

## 3. Current assumptions

- Native analytics should be checked first.
- Hard billing/gateway is optional/future unless required.

## 4. What to verify

- Usage by user/group/model.
- Export/report options.
- Cost estimation inputs.
- Web-search request accounting.
- STT hours accounting.
- Provider-side budgets.

## 5. Sources to check

- OpenWebUI Analytics docs/runtime.
- Provider pricing docs.
- LiteLLM docs only if native gap requires gateway decision.

## 6. Test plan / proof plan

Generate approved test usage in stage/runtime during implementation planning and compare visible usage to price catalog.

## 7. Risks

- Native analytics lacks needed dimensions.
- Full content logging may create data risk.
- Hard enforcement not possible without gateway.

## 8. Decision options

- Native analytics sufficient.
- Native analytics plus manual price catalog.
- Provider-side budgets.
- LiteLLM/gateway slice.

## 9. Recommended next step

Verify deployed analytics before gateway discussion.

## 10. Status

Planned, not verified.
