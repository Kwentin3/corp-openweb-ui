# Broker Reports — Economy model research final decision

Дата: 2026-07-24.

`RESEARCH_STATUS: COMPLETED_WITH_EXPLICIT_GAPS`

Этот статус не закрывает economy migration. Production-ready models:
`ZERO`.

## Решение

Рекомендуемая target architecture выбирает не одну модель на pipeline, а:

`CHEAPEST QUALIFIED FOR THIS EXACT WORKLOAD`.

До live qualification target выглядит так:

| Workload | Target exact model | Provider profile | Expected calls/cost | Schema mode | Qualified fallback | Gaps | Release readiness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| source | `gpt-5-nano-2025-08-07` | `openai_gpt` | 1/package; `$0.000533` | strict response schema | none yet; qualify Gemini 2.5/3.1 | ID unpublished, no calls | not ready |
| domain | `gpt-5-nano-2025-08-07` | `openai_gpt` | 1/package; `$0.000620` planning proxy | strict response schema/function | none | domain usage unmeasured; no calls | not ready |
| financial evidence | `gpt-5-nano-2025-08-07` | `openai_gpt` | 1/scope; `$0.000134`; 39 `$0.005217` | strict response schema | none; next GPT-4.1 Nano | unpublished, no financial probe | not ready |
| checksum | `gpt-5-nano-2025-08-07` | `openai_gpt` | 1; `$0.006191` | strict response schema | none; next GPT-4.1 Nano/Gemini 2.5 FL | unpublished, no long-context probe | not ready |

Одномодельный GPT-5 Nano set — cheapest documented hypothesis, а не
доказанный answer. Если exact subject не проходит, selector берёт следующий
дешёвый qualified subject только для этого workload.

## Однозначные ответы

### 1. Какие дешёвые exact models опубликованы?

Целевые: `models/gemini-3.1-flash-lite` и
`models/gemini-3.5-flash-lite`.

Также опубликованы дешёвые по фактической цене:

- `deepseek-v4-pro`, но без достаточного strict schema contract;
- Gemma 4, но free-only/privacy boundary неприемлема;
- `models/gemini-2.5-flash`, но он дороже 2.5 Flash-Lite и не cheapest.

Все 37 stage entries инвентаризированы в отдельном отчёте.

### 2. Какие подходят конкретным workloads?

По документации и цене, как qualification candidates:

- source/domain: GPT-5 Nano → Gemini 2.5 Flash-Lite → Gemini 3.1
  Flash-Lite;
- financial evidence: GPT-5 Nano → GPT-4.1 Nano → GPT-4o Mini;
- checksum: GPT-5 Nano → GPT-4.1 Nano → Gemini 2.5 Flash-Lite.

“Подходит” здесь означает shortlist, не `QUALIFIED`.

### 3. Что доказано через фактический route?

- Gemini 3.1 Flash-Lite: source passed;
- Gemini 3.5 Flash-Lite: source passed;
- Haiku 4.5: source passed через native Anthropic route;
- Gemini 3.1 financial: route исполнился, canonical validation failed;
- Haiku financial: route дошёл до schema rejection;
- Gemini 3.5 financial: route отсутствовал, calls `0`;
- OpenAI Nano/Gemini 2.5/GPT-4.1 Nano: calls `0`.

Других workload-specific capabilities фактически не доказано.

### 4. Где модель, adapter или harness?

- OpenAI Nano: `MODEL_NOT_PUBLISHED`;
- Gemini 3.5 financial: `HARNESS_ROUTE_MISSING`;
- Haiku financial:
  `PROVIDER_SCHEMA_LIMITATION | OPENWEBUI_ADAPTER_LIMITATION`, пока не
  разделено native minimal probe;
- Gemini 3.1 financial: `UNKNOWN` между projection/branch prompt/model;
- DeepSeek: `PROVIDER_SCHEMA_LIMITATION` относительно strict response
  contract;
- доказанный `MODEL_QUALITY_FAILURE`: `NONE`.

### 5. Самый дешёвый набор, закрывающий pipeline?

`NOT_ESTABLISHED`.

Теоретически cheapest — GPT-5 Nano на всех четырёх workloads. Он не
опубликован и не вызывался. Среди опубликованных моделей нет набора с
доказанным прохождением всех workloads.

### 6. Ожидаемая стоимость?

Measured 39 financial scopes:

- current Sol baseline: `$0.450725`;
- theoretical GPT-5 Nano: `$0.005217`;
- Gemini 3.1 Flash-Lite: `$0.022536`;
- Gemini 3.5 Flash-Lite: `$0.032015`.

Checksum:

- theoretical GPT-5 Nano: `$0.006191`;
- GPT-4.1 Nano/Gemini 2.5 Flash-Lite: `$0.012069`.

Полный document total `NOT_ESTABLISHED`, потому что число source/domain
packages и отдельный domain token profile не измерены. Нельзя выдавать
один planning proxy за document total.

### 7. Что добавить в maintained inventory?

В порядке qualification:

1. `gpt-5-nano-2025-08-07`;
2. `models/gemini-2.5-flash-lite`;
3. `gpt-4.1-nano-2025-04-14`;
4. `gpt-4o-mini-2024-07-18`;
5. `gpt-5.4-nano-2026-03-17`;
6. `claude-haiku-4-5-20251001` для диагностики.

Только exact stable/snapshot IDs. Не использовать `latest`/preview.

### 8. Что можно квалифицировать сейчас без architecture changes?

- published Gemini 3.1/3.5 для source, domain и затем checksum;
- Gemini 3.1 minimal financial branch fixture;
- Gemini 3.5 financial после узкого добавления harness route;
- Haiku source/domain и minimal native financial schema diagnostic через
  уже существующий provider adapter.

OpenAI Nano, Gemini 2.5 FL и GPT-4.1 Nano требуют maintained publication,
но не нового provider stack. Это configuration/qualification work, не новая
архитектура.

## Delivered research artifacts

- full stage inventory;
- structured-output subset matrix by provider/adapter/canonical layer;
- pricing and measured-profile cost matrix;
- four workload profiles;
- workload-specific shortlist;
- frozen 17-case synthetic fixtures;
- deterministic comparator and safe report formatter;
- focused tests;
- workload-specific live qualification plan.

## Unresolved gaps

- no exact Nano publication/live call;
- no Gemini 2.5/GPT-4.1 Nano live call;
- no measured domain token profile;
- no Gemini 3.5 financial route execution;
- no native-vs-projection Haiku schema isolation;
- no successful economy financial full scope;
- no economy checksum;
- no actual-corpus shadow;
- no production migration.

## Non-goals preserved

Gate 1 visual models, Registry, four-disposition contract, canonical
validator, materialization, Gate 3, Knowledge/RAG/vector policy and live
stage configuration не изменялись. Free JSON, repair, expensive fallback,
multi-provider consensus and customer full-scope calls не использовались.

## Final boundary

Research is sufficient to start a narrow implementation/qualification
program. It is not sufficient to release an economy model. Следующий
terminal gate — публикация exact candidates и выполнение ordered
workload-specific qualification plan.
