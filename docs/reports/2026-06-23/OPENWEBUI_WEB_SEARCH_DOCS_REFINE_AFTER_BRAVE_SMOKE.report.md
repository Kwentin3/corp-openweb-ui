# OpenWebUI Web Search Docs Refine After Brave Smoke

Date: 2026-06-23

Verdict: `docs_refined_to_brave_runtime_baseline`

## 1. Executive Summary

Документация Stage 2 Web Search актуализирована после успешного runtime smoke
для Brave `brave_llm_context`.

До рефайна документы описывали Web Search как подготовленный, но ещё не
доказанный runtime-кандидат. После диагностики и изменения runtime-конфигурации
текущий статус изменился:

- Brave `brave_llm_context` является рабочим native OpenWebUI smoke baseline;
- SearXNG остаётся self-hosted comparison track, а не заменой Brave;
- Yandex остаётся later RU-provider candidate после privacy/data-egress review;
- vectorized `web-search-*` retrieval path зафиксирован как known issue;
- текущий рабочий Brave path использует direct-context режим без дополнительной
  web-search embedding/retrieval прослойки.

Код приложения в этом документационном рефайне не менялся.

## 2. Runtime Context That Triggered The Refine

Проблема выглядела как "поиск нашёл сайты, но ответ пишет, что онлайн-данных
нет". Диагностика разделила цепочку на этапы:

1. OpenWebUI генерировал web-search queries.
2. Brave `brave_llm_context` возвращал результаты.
3. OpenWebUI показывал candidate source list в UI.
4. При классическом пути OpenWebUI сохранял результаты в `web-search-*`
   vector collection.
5. Следующий retrieval из этой коллекции возвращал `0` sources.
6. Модель получала пустой evidence context и отвечала, что данных нет.

Отдельно был отключён default Code Interpreter для выбранной smoke-модели,
потому что модель могла уходить в browser Pyodide/Python path вместо Web Search
context. Это был отдельный симптом, не поломка Brave.

Рабочая конфигурация:

```env
ENABLE_WEB_SEARCH=true
WEB_SEARCH_ENGINE=brave_llm_context
WEB_SEARCH_RESULT_COUNT=3
WEB_SEARCH_CONCURRENT_REQUESTS=1
WEB_SEARCH_TRUST_ENV=true
BYPASS_WEB_SEARCH_WEB_LOADER=true
BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true
BRAVE_SEARCH_CONTEXT_TOKENS=8192
```

`BRAVE_SEARCH_API_KEY` остаётся только server-side через Admin UI, env или
approved secret store. Реальное значение ключа в документы не попадало.

## 3. New Runtime Baseline Report

Создан отдельный runtime baseline report:

`docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`

Он фиксирует:

- verdict `brave_llm_context_native_smoke_passed_with_direct_context`;
- текущий provider/runtime baseline;
- факт, что Brave/API/parser работали;
- known issue по vectorized retrieval;
- оставшиеся gates до pilot rollout.

Предыдущий report:

`docs/reports/2026-06-23/OPENWEBUI_STAGE2_WEB_SEARCH_ANAMNESIS_AUDIT.report.md`

помечен как superseded. Он остаётся полезным как pre-smoke anamnesis snapshot,
но больше не является текущим статусом Web Search.

## 4. Documentation Files Refined

### Root Navigation

`README.md`

- Добавлен короткий текущий статус рядом со Stage 2 Web Search context link.
- Зафиксировано, что Brave `brave_llm_context` native smoke baseline proven on
  2026-06-23.
- SearXNG обозначен как comparison track.

### Stage 2 Entrypoints

`docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`

- Статус изменён с pre-smoke preparation-state на "Brave native smoke baseline
  proven".
- Старый SHA `be49bbd...` заменён на актуальный предрефайн baseline
  `7d0e02c...`.
- Добавлена ссылка на новый Brave runtime baseline report.
- Добавлен current Brave baseline status.
- Active Decisions обновлены: Brave стал working baseline, а не только
  recommendation.
- Open Questions сфокусированы на rollout scope, data policy, cost and
  retention, а не на выборе первого smoke provider.

`docs/stage2/CONTEXT_INDEX.md`

- В кратком Stage 2 context блоке Brave теперь описан как current working native
  smoke baseline.
- Зафиксированы result count `3`, concurrency `1`, web-loader bypass и
  web-search embedding/retrieval bypass.

### Acceptance

`docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`

- Web Search status обновлён с pre-smoke runtime blocker wording на "Brave native
  smoke baseline passed".
- Добавлен рабочий baseline:
  - result count `3`;
  - search concurrency `1`;
  - `BYPASS_WEB_SEARCH_WEB_LOADER=true`;
  - `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=true`;
  - Code Interpreter not enabled by default.
- Vectorized web-search retrieval path зафиксирован как known issue.
- Pending items перенесены в rollout gates: group scope, permission checks,
  EN matrix, forbidden-query policy checks, logging/retention proof, cost
  visibility.

`docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`

- Добавлены требования для текущего Brave baseline:
  - web loader bypass must be enabled;
  - web-search embedding/retrieval bypass must be enabled;
  - Code Interpreter must not be enabled by default for the selected smoke
    model.

### Blueprint

`docs/stage2/blueprints/WEB_SEARCH.blueprint.md`

- Implementation readiness обновлена: Brave smoke baseline proven.
- Оставшиеся blockers теперь относятся к pilot rollout, а не к provider
  selection research.

### ADR

`docs/stage2/decisions/ADR-0007-web-search-provider.md`

- Status изменён на:
  `accepted_for_brave_native_smoke; pilot_rollout_pending_policy_checks`.
- Добавлен runtime update `2026-06-23`.
- Brave `brave_llm_context` отмечен как accepted first native runtime smoke
  baseline.
- Provider comparison table обновлена:
  - Brave role: `First paid API baseline`;
  - RU quality: runtime smoke passed for safe RU query;
  - EN matrix: pending;
  - risk: vectorized retrieval path needs separate fix;
  - pilot fit: current working default.
- Required Runtime Probes дополнены current runtime status.
- Acceptance Signals дополнены требованием recorded/reproducible Brave native
  smoke baseline.

### Implementation Plans

`docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md`

- Status обновлён на proven Brave baseline, user pilot rollout pending.
- Добавлен раздел `3.1 Current Runtime Baseline`.
- В config plan добавлен `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL`.
- Initial smoke values обновлены:
  - web loader bypassed for `brave_llm_context`;
  - web-search embedding/retrieval bypassed for `brave_llm_context`;
  - trust env enabled when runtime egress requires proxy env.
- Smoke plan дополнен current partial result: safe RU manual smoke passed, full
  RU/EN matrix pending.

`docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`

- Status обновлён: Brave side has proven runtime baseline; SearXNG pending.
- Path A уточнён как direct Web Search docs context.
- Добавлен current Path A baseline.
- Зафиксировано, что SearXNG нельзя сравнивать с broken vectorized Brave path;
  comparison должен использовать current working Brave direct-context baseline.

### Contracts

`docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`

- Status дополнен Brave runtime baseline observation.
- Добавлен раздел `Current Brave LLM Context Baseline`.
- Указано, что для `brave_llm_context` текущий accepted smoke path напрямую
  передаёт Brave LLM-oriented passages в LLM.
- Alternative vector collection path не считается accepted до отдельного fix.

`docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md`

- Status дополнен runtime observation.
- Добавлен current runtime note:
  - Brave passes native smoke with direct Web Search docs context;
  - vectorized retrieval path not accepted;
  - wrapper/sidecar не нужны, пока direct-context baseline достаточен.

### Infra / Provider Docs

`docs/infra/ENVIRONMENT_VARIABLES.md`

- Добавлен раздел `Stage 2 Web Search / Brave runtime baseline`.
- Зафиксированы воспроизводимые config names и placeholder values без секретов.
- Добавлены notes:
  - реальный `BRAVE_SEARCH_API_KEY` не коммитить;
  - bypasses intentional for `brave_llm_context`;
  - vectorized path is known issue;
  - Code Interpreter should not be default for smoke model.

`docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md`

- Добавлен Stage 2 runtime update.
- Минимальный профиль теста дополнен `BYPASS_WEB_SEARCH_WEB_LOADER=True` и
  `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL=True`.
- Рекомендованный порядок теста обновлён: начинать с текущего рабочего
  `brave_llm_context` baseline.

`docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md`

- Добавлен runtime note со ссылкой на Brave runtime baseline report.
- Status изменён: research complete, Brave proven as first native smoke
  baseline, SearXNG and Yandex remain follow-up tracks.

## 5. Current Product/Architecture Position

Текущий approved-for-smoke path:

```text
OpenWebUI native Web Search
  -> Brave brave_llm_context
  -> direct LLM-oriented docs context
  -> LLM answer with visible sources
```

Текущий not-accepted path:

```text
OpenWebUI native Web Search
  -> Brave brave_llm_context
  -> web-search-* vector collection
  -> retrieval sources
  -> LLM answer
```

Причина: runtime diagnostics показали, что второй путь может возвращать `0`
sources после успешного поиска и embedding.

Стратегическое решение:

- не чинить vectorized retrieval сейчас в основном потоке;
- принять direct-context Brave baseline как нормальный путь для
  `brave_llm_context`;
- оставить vectorized path как backlog/known issue до сценария, где реально
  нужен RAG over long fetched pages.

## 6. Remaining Work

До pilot rollout:

- определить pilot group;
- проверить permission allow/deny для ordinary user и pilot user;
- прогнать EN smoke matrix;
- прогнать forbidden-query policy checks без отправки чувствительных данных
  внешнему provider;
- проверить logging/retention;
- подтвердить provider dashboard или native cost visibility;
- решить, нужен ли SearXNG runtime comparison сейчас;
- не запускать Yandex до privacy/data-egress review.

Для future RAG/page-loading сценария:

- отдельно исследовать `vectorized_web_search_retrieval_returns_zero_sources`;
- не включать глобальный `BYPASS_RETRIEVAL_ACCESS_CONTROL` как быстрый обход;
- если чинить, делать узкий fix вокруг trusted `type=web_search` items и
  ephemeral `web-search-*` collections.

## 7. Validation

Проверки после рефайна:

- stale-status grep по live docs: чисто;
- trailing whitespace scan: чисто;
- secret-pattern scan: чисто; реальных provider keys нет;
- UTF-8 BOM сохранён на русских markdown/report файлах;
- `git diff --check` по tracked docs прошёл;
- Git показал только стандартные Windows CRLF warnings.

## 8. Git State

На момент отчёта:

- branch: `main`;
- upstream: `origin/main`;
- изменения не закоммичены;
- code/runtime files в repo не менялись в этом docs-refine step;
- изменены tracked docs и добавлены новые reports под
  `docs/reports/2026-06-23/`.

Diff-stat перед созданием этого отчёта:

```text
14 files changed, 210 insertions(+), 36 deletions(-)
```

Новые/актуализированные report artifacts:

- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_STAGE2_WEB_SEARCH_ANAMNESIS_AUDIT.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_DOCS_REFINE_AFTER_BRAVE_SMOKE.report.md`
