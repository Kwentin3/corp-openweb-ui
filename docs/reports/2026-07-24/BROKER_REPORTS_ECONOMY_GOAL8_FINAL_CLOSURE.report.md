# Broker Reports — Economy Model Policy and Gate 2 Live Closure v1

Дата: 2026-07-24

Итоговый статус программы: `NOT_CLOSED`.

## Executive result

Repository-side cost and selection guards реализованы, но ни одна дешёвая
модель не прошла неизменённый Gate 2 financial evidence contract. Поэтому
full-scope economy reproof, economy checksum и production migration не
выполнены.

Дорогая модель не использовалась для обхода blocker:

- expensive model calls в этой программе: `0`;
- fallback: `0`;
- hidden repair: `0`;
- production release mutations: `0`.

Статус не повышен до `COMPLETED_WITH_PROVIDER_GAPS`, потому что обязательные
`FULL_SCOPE` и `CHECKSUM` acceptance не пройдены.

## Goals

| Goal | Статус | Evidence |
| --- | --- | --- |
| Goal 0 — model/cost audit | `COMPLETED` | Все call sites и дорогие defaults инвентаризированы; предыдущий full-scope cost оценён |
| Goal 1 — economy policy | `COMPLETED` | Versioned code-owned policy; только Nano, Flash-Lite, Haiku |
| Goal 2 — budgets | `COMPLETED` | Token/call/cost/reasoning/tool guards и preflight |
| Goal 3 — provider qualification | `COMPLETED_WITH_PROVIDER_GAPS` | Ни одного qualified exact ID |
| Goal 4 — provider selection | `COMPLETED` | Deterministic cheapest-qualified-first; no-qualified fail-closed |
| Goal 5 — full-scope reproof | `NOT_CLOSED` | Blocked до scope/provider call |
| Goal 6 — checksum | `NOT_CLOSED` | Blocked до answering call; control vector не запускался |
| Goal 7 — migration | `NOT_CLOSED` | Release запрещён preconditions; stage не изменён |
| Goal 8 — final closure | `NOT_CLOSED` | Live/quality acceptance остаются незакрыты |

Основные delivery PR: #96–#98 и #104–#108. Во время qualification были также
приняты узкие corrective PR #99–#103; они не ослабляли Registry, decision
contract или materializer.

## Exact provider/model statuses

| Provider | Exact model | Status | Failed capability / terminal code |
| --- | --- | --- | --- |
| OpenAI | `gpt-5-nano-2025-08-07` | `UNAVAILABLE` | maintained inventory / `stage_models_endpoint_model_absent` |
| OpenAI | `gpt-5.4-nano-2026-03-17` | `UNAVAILABLE` | maintained inventory / `stage_models_endpoint_model_absent` |
| Gemini | `models/gemini-3.1-flash-lite` | `NOT_QUALIFIED` | canonical acceptance / `financial_evidence_decision_unclassified_shape_invalid` |
| Gemini | `models/gemini-3.5-flash-lite` | `UNSUPPORTED_CONTRACT` | financial qualification route / `financial_qualification_not_exposed_by_capability_probe_route` |
| Anthropic | `claude-haiku-4-5-20251001` | `UNSUPPORTED_CONTRACT` | provider schema acceptance / `gate2_model_schema_response_format_rejected` |

Qualified/active allowlist: пуст.

## Calls, tokens and cost

В Goal 3 выполнено `5` разрешённых economy attempts:

- Gemini 3.1 source: 1 call, `5 058` input, `700` output, `5 758` total;
- Gemini 3.1 financial: 1 call, usage не был полностью получен;
- Gemini 3.5 source: 1 call, `5 065` input, `687` output, `5 752` total;
- Gemini 3.5 financial: 0 calls — route отсутствует;
- Haiku source: 1 call, `6 395` input, `464` output, total не reported;
- Haiku financial: 1 provider attempt, usage не получен;
- OpenAI Nano: 0 calls.

Итого по reported source usage:

- input tokens: `16 518`;
- output tokens: `1 851`;
- provider-reported total-token sum: `11 510` для двух Gemini calls;
- рассчитанный source-only cost subtotal: `$0.0142665`.

Subtotal не является полной стоимостью qualification: usage двух financial
attempts отсутствует. Полный bounded cost поэтому
`NOT_FULLY_MEASURED`.

Goal 5–7:

- provider calls: `0`;
- tokens: `0`;
- blocked preflight cost: `$0`;
- successful economy bounded/full-scope cost: `NOT_MEASURED_NO_RUN`.

Previous expensive full-scope comparison baseline, не часть этой economy
программы:

- model: `gpt-5.6-sol`;
- calls: `39`;
- input/output/total: `47 533 / 7 102 / 54 635`;
- estimated cost: `$0.450725`.

Same-token economy estimates из Goal 0: `$0.005217`–`$0.083043`.
Достигнутая экономия не заявляется, поскольку успешного economy full-scope
run не было.

## Guards

Repository:

- allowed families: только Flash-Lite, Nano, Haiku;
- unknown/expensive exact IDs отклоняются;
- runtime config/valves могут только сузить allowlist;
- source/domain/financial Pipes используют economy selection и budgets;
- checksum runner policy-bound;
- migration verifier policy-bound и не имеет Sol default;
- default provider calls: 1;
- fallback maximum: 1, checksum: 0;
- paid tools/search: 0;
- multi-provider consensus: 0;
- reasoning: disabled/minimal;
- safe receipts не содержат customer content.

Explicit guard checks отклонили `gpt-5.6-sol` на checksum и migration
entrypoints до model call. Policy tests также отклоняют Mini, Sol, Luna,
full/Pro/o-series, обычный Gemini Flash/Pro, Sonnet и Opus.

Live stage:

- economy selection factory: отсутствует;
- economy budget enforcement marker: отсутствует;
- legacy resolver marker: присутствует;
- repository/live Function parity: не exact;
- economy release mutations: `0`.

Следовательно, code guards доказаны в repository, но не выпущены в live.

## Provider gaps and owners

- OpenAI Nano — owner: maintained `openai_gpt` connection. Следующий шаг:
  добавить exact Nano ID и повторить strict financial qualification.
  Запрещённый fallback: Mini, Sol, full GPT, Pro, o-series.
- Gemini 3.1 Flash-Lite — owner: Gemini schema projection/prompt boundary.
  Следующий шаг: получить canonical-valid conditional disposition без repair.
  Запрещённый fallback: обычный Flash, Pro.
- Gemini 3.5 Flash-Lite — owner: qualification harness. Следующий шаг:
  предоставить bounded financial probe. Запрещённый fallback: обычный Flash,
  Pro.
- Anthropic Haiku — owner: maintained Anthropic adapter/connection. Следующий
  шаг: подтвердить strict financial schema support. Запрещённый fallback:
  Sonnet, Opus.

После qualification одного exact ID необходимо заново, по порядку и в
отдельных PR, выполнить full-scope reproof, checksum и controlled migration.

## Validation

- final policy/selection/budget/checksum/migration focused suite:
  `61 passed`;
- последний полный regression suite: `1332 passed, 20 skipped`;
- expensive provider calls: `0`;
- Knowledge/RAG/vector writes: `0`;
- customer values/provider raw output/private refs в Git: `0`.

## Final acceptance

- `ALLOWED_MODEL_CLASSES`: `FLASH_LITE_NANO_HAIKU_ONLY`;
- `EXPENSIVE_MODEL_CALLS`: `ZERO`;
- `FULL_SCOPE`: `NOT_PASSED`;
- `CHECKSUM`: `NOT_RUN`;
- `COST_GUARDS`: `ENFORCED_IN_REPOSITORY_NOT_RELEASED`;
- `PROGRAM_STATUS`: `NOT_CLOSED`.

