# Usage Analytics And Costs Blueprint

## 1. Purpose

Спланировать basic analytics and cost visibility for Stage 2.

## 2. PRD-1 requirements covered

- Basic usage analytics / cost visibility.
- Price catalog.
- LLM tokens, web-search requests, STT hours, storage/files.
- Hard billing/gateway remains optional decision.

## 3. Current known context

PRD-0 did not include cost accounting. PRD-1 requires native analytics first and no hard billing promise without gateway decision.

## 4. Target user workflow

Admin sees usage by user/group/model where native OpenWebUI supports it, references price catalog, and can explain costs to customer.

## 5. Native OpenWebUI first path

- OpenWebUI Analytics.
- Usage by user/model if available.
- Group/model access control for expensive capabilities.
- Provider-side budgets where available.

## 6. Integration / custom implementation path

- LiteLLM/gateway only if hard budgets, virtual keys, rate limits or guaranteed blocking are required.
- Custom reporting only after native gaps are measured.

## 7. Data and security notes

Usage logs must not leak prompts or sensitive data unnecessarily. Cost visibility should avoid storing full content unless explicitly approved.

## 8. Dependencies

- Provider catalog.
- Web-search/STT usage model.
- OpenWebUI capability research.

## 9. Risks and constraints

- Native analytics may be partial.
- Hard limits may not be enforceable natively.
- External provider costs may be hard to normalize.

## 10. Open questions

- What level of cost visibility is enough?
- Are hard monthly limits required?
- Does customer need per-department reporting?

## 11. Research links

- [USAGE_ANALYTICS_BILLING_RESEARCH](../research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- [OPENWEBUI_CAPABILITY_RESEARCH](../research/OPENWEBUI_CAPABILITY_RESEARCH.md)

## 12. Acceptance signals

- Native analytics capability documented.
- Price catalog exists.
- Gateway decision is documented if native analytics insufficient.

## 13. Implementation readiness

Needs deployed capability check before planning.
