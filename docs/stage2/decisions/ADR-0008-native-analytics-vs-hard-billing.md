# ADR-0008 Native Analytics vs Hard Billing

Status: Proposed

## 1. Context

PRD-1 requires basic analytics / cost visibility. It does not require hard
billing/gateway by default. LiteLLM/gateway remains optional/future unless native
analytics cannot satisfy customer needs.

## 2. Problem

"Basic analytics" and "hard billing" are different requirements. If they are
mixed, the project may add gateway complexity before proving a real need.

## 3. Decision needed

Approve whether native OpenWebUI analytics are enough for Practical Stage 2, or
whether hard billing/enforcement requires a separate gateway slice.

## 4. Options

Option 1. Native OpenWebUI analytics first.

- Lowest operational complexity.
- Recommended default.

Option 2. Manual price catalog plus native usage exports.

- Acceptable if native analytics are partial but sufficient for customer.

Option 3. LiteLLM/gateway.

- Enables stronger budgets, routing and enforcement.
- Adds ops/security/rollback surface.
- Optional/future unless explicitly required.

## 5. Recommended option

Use Option 1 for Practical Stage 2 until runtime proof shows a gap.

Basic analytics means:

- usage visibility by user/model where available;
- price catalog;
- approximate cost review for LLM, web-search, STT and storage/files;
- group/model access control for expensive capabilities.

Hard billing/enforcement means:

- guaranteed blocking;
- virtual keys;
- team budgets;
- rate limits;
- centralized provider routing.

## 6. Consequences

- LiteLLM/gateway is not introduced automatically.
- Runtime proof decides whether native analytics are enough.
- Hard billing remains future if customer does not require enforceable budgets.

## 7. Runtime proof needed

- Check deployed/staging OpenWebUI analytics.
- Generate sample usage by two users/groups/models.
- Verify model/user/group breakdown if available.
- Record native gaps.
- Decide whether manual catalog is enough.

## 8. Customer input needed

- Required cost visibility granularity.
- Whether hard monthly limits are required.
- Whether per-department reporting is required.
- Budget owner and reporting cadence.

## 9. Acceptance signals

- Native analytics proof completed.
- Customer accepts native/manual cost visibility, or gateway is separately scoped.
- Hard billing/gateway is not silently included in Practical Stage 2.

## 10. Links

- [USAGE_ANALYTICS_AND_COSTS](../blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md)
- [USAGE_ANALYTICS_BILLING_RESEARCH](../research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- [PROVIDERS_MODEL_CATALOG](../blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
