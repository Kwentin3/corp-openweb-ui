# Web Search Native Pilot Plan

Status: provider connectivity baseline proven for Brave, Yandex and private
SearXNG on 2026-06-23; user pilot rollout pending policy, group, logging,
comparison and cost checks.

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

- private SearXNG if foreign paid API use is rejected or if owner wants a
  self-hosted meta-search comparison track;
- Yandex Search API as the working RU-provider path after 2026-06-23 Admin
  UI/native smoke, with rollout gated by metadata-forwarding/cost-mode review;
- defer if no provider/data/cost decision is approved.

Private SearXNG setup details live in
[SEARXNG_PRIVATE_INSTANCE_PLAN](SEARXNG_PRIVATE_INSTANCE_PLAN.md). It is not a
custom gateway or sidecar; OpenWebUI still uses native Web Search provider
`searxng`.

Candidate-set comparison details live in
[WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN](WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md).
Use the same query matrix for Brave, Yandex and SearXNG where policy allows it.

## 3.1 Current Runtime Baseline

The deployed OpenWebUI instance has a working admin/manual smoke baseline:

- provider: Brave;
- engine: `brave_llm_context`;
- result count: `3`;
- search concurrency: `1`;
- web loader bypass: enabled;
- web-search embedding/retrieval bypass: enabled;
- selected smoke model: `gpt-5.4-mini-2026-03-17`;
- Code Interpreter: not enabled by default for this model during Web Search
  smoke.

Additional provider status:

- Yandex Search API was configured through OpenWebUI Admin UI and passed
  operator/native smoke on 2026-06-23.
- Treat Yandex as a working RU-provider path for controlled testing, not as
  all-user rollout approval.
- Private SearXNG native provider smoke passed in snippet/bypass mode on
  2026-06-23. Treat it as a comparison path, not primary.

Reasoning:

- `brave_llm_context` already returns LLM-oriented passages plus URLs.
- The classic OpenWebUI path that stores web-search snippets in a vector
  collection and retrieves them again returned `0` sources during runtime
  diagnostics.
- The direct Brave context path worked after bypassing that extra
  embedding/retrieval step.
- Keep the vectorized retrieval path as a deferred known issue, not a pilot
  blocker. Revisit it only when long page loading, classic `brave`, SearXNG page
  loading or full RAG over fetched content becomes a real product requirement.

## 4. Config Plan

Config names only; do not put values in docs:

- `ENABLE_WEB_SEARCH`
- `WEB_SEARCH_ENGINE`
- `WEB_SEARCH_RESULT_COUNT`
- `WEB_SEARCH_CONCURRENT_REQUESTS`
- `WEB_LOADER_CONCURRENT_REQUESTS`
- `BYPASS_WEB_SEARCH_WEB_LOADER`
- `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL`
- `WEB_SEARCH_TRUST_ENV`
- `BRAVE_SEARCH_API_KEY`
- `BRAVE_SEARCH_CONTEXT_TOKENS`
- `SEARXNG_QUERY_URL`
- `SEARXNG_LANGUAGE`
- `YANDEX_WEB_SEARCH_API_KEY`
- `YANDEX_WEB_SEARCH_URL`
- `YANDEX_WEB_SEARCH_CONFIG`
- provider-specific API key/config variable for any alternative engine.

For private SearXNG overlay, additional non-secret/runtime config names:

- `SEARXNG_IMAGE`
- `SEARXNG_VALKEY_IMAGE`
- `SEARXNG_SECRET`
- `SEARXNG_LIMITER`
- `SEARXNG_VALKEY_URL`
- `SEARXNG_PUBLIC_INSTANCE`
- `SEARXNG_IMAGE_PROXY`

Initial smoke values to approve:

- result count: `3`;
- search concurrency: `1`;
- web loader: bypassed for the `brave_llm_context` baseline;
- web-search embedding/retrieval: bypassed for the `brave_llm_context`
  baseline;
- trust env: enabled when runtime egress requires proxy env.

## 5. Rollout Plan

1. Admin-only no-user smoke.
2. Small pilot group.
3. Expand to all approved users only after acceptance.
4. Keep provider dashboard usage visible during pilot.
5. Record all evidence in sanitized report; no raw secrets or sensitive queries.
6. If SearXNG is compared, keep it internal-only and run direct JSON API smoke
   before OpenWebUI smoke.

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

Current partial result:

- one safe RU manual smoke passed after the current Brave baseline config was
  applied;
- the full RU/EN matrix remains pending before pilot rollout.

SearXNG-specific smoke:

- `/search?q=OpenWebUI&format=json` returns valid JSON;
- private SearXNG is not exposed publicly;
- upstream-engine leakage warning is accepted by owner;
- candidate set is captured before answer generation;
- candidate URL/title/snippet/source engine are captured where available;
- no third-party search API key is present in OpenWebUI/browser for the SearXNG
  path;
- empty/CAPTCHA/rate-limited result cases are recorded.

Comparison smoke:

- same query set is used for Brave and SearXNG;
- candidate set quality is scored;
- final answer groundedness is scored;
- source visibility is checked;
- search, load/extraction and total answer latency are recorded;
- logs are checked for raw query/raw result/provider key exposure.

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
