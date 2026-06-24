# Web Search Blueprint

## 1. Purpose

Спланировать web-search для всех пользователей с rules, limits, cost visibility and safe usage
policy.

## 2. PRD-1 requirements covered

- Web-search нужен всем пользователям.
- Нужны result count, concurrency settings, instruction and cost visibility.
- Исследовать Brave and Russian provider.
- Yandex Search is search; YandexGPT/GigaChat are LLM providers.

## 3. Current known context

PRD-0 did not include web-search. Existing `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md` is Stage 2
research context, not PRD-0 implementation evidence.

## 4. Target user workflow

Пользователь запускает web-search in allowed scenario, получает grounded answer/source links, видит
ограничения and knows when not to use web-search.

## 5. Native OpenWebUI first path

- Native OpenWebUI Web Search.
- Provider configuration through Admin UI/env if appropriate.
- Feature permissions by groups/policy.
- Result count and concurrency settings.

## 6. Integration / custom implementation path

- Adapter if Russian provider is not native.
- Gateway only if hard limits/cost enforcement require it.
- Custom audit/logging only after privacy/cost decision.

## 7. Data and security notes

Do not send sensitive personal/financial/accounting data into external search. Policy must name
prohibited examples.

## 8. Dependencies

- Web-search provider research.
- Data policy.
- Usage analytics.
- Provider catalog.

## 9. Risks and constraints

- Cost spikes.
- Provider limits.
- Poor source quality.
- Privacy leakage in search query.
- Confusion between LLM provider and search provider.

## 10. Open questions

- Which Russian search provider is acceptable?
- What default result count and concurrency?
- What smoke queries represent business use?

## 11. Research links

- [WEB_SEARCH_PROVIDERS_RESEARCH](../research/WEB_SEARCH_PROVIDERS_RESEARCH.md)
- [USAGE_ANALYTICS_BILLING_RESEARCH](../research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- Existing: [WEB_SEARCH_PROVIDER_RESEARCH](../../infra/WEB_SEARCH_PROVIDER_RESEARCH.md)

## 12. Acceptance signals

- Russian and English smoke queries work.
- Result count/concurrency documented.
- Admin can see or estimate cost.
- User instruction says when web-search is forbidden.

## 13. Implementation readiness

Provider connectivity baseline is proven for Brave `brave_llm_context`, Yandex
Search API and private SearXNG native snippet/bypass path. Pilot rollout still
needs group scope, forbidden-query policy, logging/retention proof, EN/RU
comparison matrix and cost visibility.
