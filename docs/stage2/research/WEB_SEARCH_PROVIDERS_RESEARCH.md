# Web Search Providers Research

## 1. Question

Which web-search provider should Stage 2 use for all users under rules, limits and cost visibility?

## 2. Why it matters for PRD-1

Web-search is a priority scenario but can leak sensitive data and create uncontrolled costs.

## 3. Current assumptions

- Existing Brave research is relevant.
- Need a Russian provider path as candidate.
- Search providers are separate from LLM providers.

## 4. What to verify

- Brave current suitability.
- Russian search provider availability.
- Native OpenWebUI provider support.
- Result count and concurrency controls.
- Pricing and quotas.
- Source quality.

## 5. Sources to check

- Existing `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md`.
- Official provider docs/pricing.
- OpenWebUI web-search docs/runtime.

## 6. Test plan / proof plan

Run Russian and English smoke queries, compare relevance, latency, source quality and cost.

## 7. Risks

- Cost spikes.
- Weak Russian results.
- Query privacy leakage.
- Misconfigured concurrency/result count.

## 8. Decision options

- Brave as first provider.
- Russian provider as first provider.
- Two-provider strategy.
- Defer provider if privacy/cost cannot be accepted.

## 9. Recommended next step

Refresh provider research before implementation.

## 10. Status

Planned, previous research exists but may be stale.
