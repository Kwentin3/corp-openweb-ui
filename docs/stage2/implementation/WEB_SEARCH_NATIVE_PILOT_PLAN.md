# Web Search Native Pilot Plan

Status: ready for owner/provider approval, not approved for live traffic yet.

## 1. Goal

Run a controlled native OpenWebUI Web Search pilot with low cost, low
concurrency, visible sources and no provider secrets in the browser.

## 2. Scope

In scope:

- native OpenWebUI Web Search;
- one approved provider;
- result count `3` for first smoke;
- search concurrency `1` for first smoke;
- approved pilot group or admin-only smoke;
- source attribution;
- privacy/logging check;
- provider-dashboard or native analytics cost evidence.

Out of scope:

- sidecar;
- fork;
- universal web-search framework;
- hidden automatic browsing;
- separate search portal;
- hard billing gateway unless the owner makes it a pilot gate;
- STT changes.

## 3. Recommended Provider Path

Default:

- provider: Brave;
- engine: `brave_llm_context`;
- reason: native OpenWebUI support, AI-oriented context, reduced page-scraping
  dependency compared with classic web search.

Alternatives:

- private SearXNG if foreign paid API use is rejected;
- Yandex Search API after metadata-forwarding/cost-mode review;
- defer if no provider/data/cost decision is approved.

## 4. Config Plan

Config names only; do not put values in docs:

- `ENABLE_WEB_SEARCH`
- `WEB_SEARCH_ENGINE`
- `WEB_SEARCH_RESULT_COUNT`
- `WEB_SEARCH_CONCURRENT_REQUESTS`
- `WEB_LOADER_CONCURRENT_REQUESTS`
- `BYPASS_WEB_SEARCH_WEB_LOADER`
- `WEB_SEARCH_TRUST_ENV`
- `BRAVE_SEARCH_API_KEY`
- `BRAVE_SEARCH_CONTEXT_TOKENS`
- `SEARXNG_QUERY_URL`
- `SEARXNG_LANGUAGE`
- `YANDEX_WEB_SEARCH_API_KEY`
- `YANDEX_WEB_SEARCH_CONFIG`
- provider-specific API key/config variable for any alternative engine.

Initial smoke values to approve:

- result count: `3`;
- search concurrency: `1`;
- web loader: enabled unless `brave_llm_context` smoke intentionally bypasses
  page fetch;
- trust env: enabled only if runtime egress requires proxy env.

## 5. Rollout Plan

1. Admin-only no-user smoke.
2. Small pilot group.
3. Expand to all approved users only after acceptance.
4. Keep provider dashboard usage visible during pilot.
5. Record all evidence in sanitized report; no raw secrets or sensitive queries.

## 6. Smoke Plan

Preflight:

- exact OpenWebUI image/version;
- Admin UI Web Search settings visible;
- selected provider engine available;
- result count/concurrency configurable;
- group permission behavior understood.

Provider smoke:

- 3 Russian safe queries;
- 3 English safe queries;
- result count `3`;
- concurrency `1`;
- visible source links/cards;
- latency recorded;
- no-results case recorded;
- provider 429/timeout behavior recorded if safe.

Permissions smoke:

- admin can use Web Search;
- pilot user with permission can use Web Search;
- ordinary user without permission cannot use Web Search.

Privacy/logging smoke:

- provider key not visible in browser responses/config/storage;
- key values not printed in logs;
- raw sensitive queries not logged by default;
- policy-blocked examples do not call provider.

Cost visibility smoke:

- request count visible in provider dashboard or native analytics;
- if no per-user/group visibility exists, record the gap.

## 7. Safe Test Queries

Russian examples:

- `курс ключевой ставки ЦБ РФ сегодня`
- `новые правила электронных доверенностей 2026`
- `праздничные дни в России 2026`
- `актуальная версия Firefox ESR`
- `как проверить статус самозанятого без персональных данных`

English examples:

- `OpenWebUI web search documentation current providers`
- `Brave Search API LLM Context pricing`
- `SearXNG JSON output configuration`
- `Yandex Search API quotas limits`

Forbidden examples:

- queries containing passport, tax ID, account number, payroll, customer names,
  uploaded document text, internal URLs, credentials or provider keys.

## 8. Rollback

- Disable Web Search in Admin UI/config.
- Remove provider key from Admin UI/secret store.
- Revert result count/concurrency settings.
- Remove pilot group permission.
- Preserve sanitized report only.

## 9. Owner Decisions Needed

- Provider and provider account owner.
- Budget and monthly stop condition.
- Allowed data classes.
- Forbidden query examples.
- Pilot group.
- Retention for search metadata.
- Whether native/provider-dashboard cost visibility is enough.
- Whether hard budget enforcement is required before rollout.

## 10. Stop Conditions

Stop the pilot and do not expand if:

- provider key appears in browser;
- raw sensitive query text appears in logs;
- permission bypass is found;
- source attribution is not visible;
- provider costs cannot be observed at all;
- native runtime lacks required provider/settings and no acceptable wrapper path
  is approved.
