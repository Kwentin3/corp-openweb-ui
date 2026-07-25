# Broker Reports — Economy model shortlist

Дата: 2026-07-24.

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`.

Shortlist — очередь qualification, не production allowlist. Ни одна новая
модель не объявлена qualified по интернет-документации.

## Requalification v2 — authoritative update

Три exact-кандидата опубликованы и получили synthetic replay. Предыдущая
очередь ниже сохраняет исходную research rationale, но текущий фактический
выбор определяется workload evidence:

| Workload | Cheapest synthetic-proven model | Другие результаты |
| --- | --- | --- |
| `gate2_source` | `claude-haiku-4-5-20251001` | GPT/Gemini ждут доставки policy v1.3 в stage |
| `gate2_domain` | `claude-haiku-4-5-20251001` | GPT/Gemini ждут доставки policy v1.3 в stage |
| `gate2_financial_evidence` | `gpt-5.4-nano-2026-03-17` | Haiku `2/4`; Gemini route unavailable |
| `gate2_financial_checksum` | `claude-haiku-4-5-20251001` | GPT `0/3`; Gemini route unavailable |

Это synthetic evidence, а не production allowlist. Полный receipt:
`BROKER_REPORTS_ECONOMY_REQUALIFICATION_V2.report.md`.

## Рекомендуемая очередь

| Workload | Primary candidate | Secondary | Optional fallback |
| --- | --- | --- | --- |
| `gate2_source` | `gpt-5-nano-2025-08-07` | `models/gemini-2.5-flash-lite` | `models/gemini-3.1-flash-lite` |
| `gate2_domain` | `gpt-5-nano-2025-08-07` | `models/gemini-2.5-flash-lite` | `models/gemini-3.1-flash-lite` |
| `gate2_financial_evidence` | `gpt-5-nano-2025-08-07` | `gpt-4.1-nano-2025-04-14` | `gpt-4o-mini-2024-07-18` |
| `gate2_financial_checksum` | `gpt-5-nano-2025-08-07` | `gpt-4.1-nano-2025-04-14` | `models/gemini-2.5-flash-lite` |

Почему GPT-5 Nano primary: самый низкий standard cost, strict Structured
Outputs, достаточный 400k context для всех measured workloads и exact dated
snapshot. Это capability hypothesis; live calls ещё не было.

Почему Gemini 2.5 Flash-Lite: stable, 1M context, цена как GPT-4.1 Nano и
официальное позиционирование для high-volume lightweight tasks. Модель уже
доступна через maintained Gemini connection, но не опубликована.

Почему GPT-4.1 Nano: non-reasoning, строгий output, 1M context и низкая
цена — особенно подходящий checksum secondary. Он требует явного расширения
policy, потому что текущая policy перечисляет только GPT-5 Nano family IDs.

## `gate2_source`

- Primary GPT-5 Nano expected `$0.000533`/package.
- Secondary Gemini 2.5 Flash-Lite expected `$0.000786`.
- Published fallback Gemini 3.1 Flash-Lite expected `$0.002315`; source
  live probe уже passed.
- Gemini 3.5 Flash-Lite тоже source-passed, но `$0.003267` и поэтому идёт
  после 3.1.

Квалифицировать сейчас без architecture change можно Gemini 3.1 и 3.5 на
существующем route. Nano/2.5 требуют только maintained publication/config,
не новый provider stack.

## `gate2_domain`

Тот же порядок выбран по цене, но qualification независима от source.
Dynamic candidate/ref enums и ambiguity fixture обязательны. Source pass не
переносится автоматически на domain.

Gemini 3.1 — practical published fallback. Отдельного measured domain receipt
нет, поэтому cost target provisional.

## `gate2_financial_evidence`

Приоритет отдан OpenAI strict subset:

1. GPT-5 Nano;
2. GPT-4.1 Nano;
3. GPT-4o Mini.

Они дешевле Haiku и не требуют Gemini branch projection. GPT-5.4 Nano
технически подходит, но при тех же задачах дороже GPT-4.1 Nano и GPT-5 Nano;
он остаётся reserve candidate после первых трёх.

Gemini 3.1 и 3.5 не отвергнуты по качеству:

- 3.1 имеет canonical reject на сложном financial fixture; нужен minimal
  branch probe;
- 3.5 не получила financial call из-за harness gap.

После устранения этих gaps они могут войти в workload fallback, но не
получают readiness сейчас.

## `gate2_financial_checksum`

Measured input `117,555` требует запас над 128k:

- GPT-5 Nano: 400k, expected `$0.006191`;
- GPT-4.1 Nano: ~1.05M, `$0.012069`;
- Gemini 2.5 Flash-Lite: ~1M, `$0.012069`.

GPT-4o Mini rejected для checksum: 128k nominal context слишком близок к
measured input плюс instructions/schema. Haiku имеет 200k, но expected
`$0.121470`, почти достигает hard ceiling и втрое превышает target.

## Published cheap non-family candidates

### `deepseek-v4-pro`

Опубликован и фактически недорог (`0.435/0.87`), но официальный route даёт
JSON mode без schema guarantee. Это `REJECTED_UNSUPPORTED_CONTRACT`, не
quality judgement.

### Gemma 4

Обе Gemma 4 опубликованы и поддерживают function calling, но текущая Gemini
API pricing показывает free-only availability без paid production tier;
free-tier content-use/privacy boundary неприемлема для future customer
execution. `REJECTED_PRIVACY_AND_OPERATING_BOUNDARY`.

### Gemini 2.5 Flash

Опубликован, stable и технически подходит, но standard цена
`0.30/2.50` совпадает с 3.5 Flash-Lite и выше 2.5 Flash-Lite. Не cheapest;
`REJECTED_BY_DOMINANCE`, не запрещён навсегда.

## Общие rejects

| Model/family | Причина |
| --- | --- |
| `gpt-5.6-sol`, Terra | frontier/cost prohibited |
| `gpt-5.6-luna` | strict capable, но `1/6`; не проходит target |
| `gpt-5.4-mini-2026-03-17` | `0.75/4.5`; не cheapest and above target |
| Claude Sonnet/Opus | cost |
| `claude-haiku-4-5-20251001` | optional diagnostic only: high target cost + unresolved financial schema rejection |
| Gemini ordinary Flash 3.5/3.6 | output price above Lite target |
| all preview/experimental/latest aliases | moving lifecycle |
| realtime/media/deep-research/AQA/Arena/Pipes | wrong boundary or virtual identity |
| DeepSeek v4 | no strict schema conformance on proven route |

## Maintained inventory changes required before live calls

Exact, dated/stable IDs only:

1. `gpt-5-nano-2025-08-07`;
2. `models/gemini-2.5-flash-lite`;
3. `gpt-4.1-nano-2025-04-14`;
4. `gpt-4o-mini-2024-07-18`;
5. `gpt-5.4-nano-2026-03-17`;
6. `claude-haiku-4-5-20251001` for adapter diagnosis.

Publication must not activate production selection. Exact workload receipts
remain admission authority.

## Readiness

| Candidate | Publication | Existing provider stack | Actual route evidence | Production readiness |
| --- | --- | --- | --- | --- |
| GPT-5 Nano | missing | yes | none | no |
| Gemini 2.5 Flash-Lite | missing | yes | none | no |
| GPT-4.1 Nano | missing | yes | none | no |
| GPT-4o Mini | missing | yes | none | no |
| Gemini 3.1 Flash-Lite | published | yes | source pass; financial reject | source evidence retained, not production-qualified |
| Gemini 3.5 Flash-Lite | published | yes | source pass; financial route missing | source evidence retained, not production-qualified |
| Haiku 4.5 | missing aggregate publication | yes | source pass; financial schema reject | no |

## Decision

Cheapest plausible full set is GPT-5 Nano for all four workloads, but it is
`HYPOTHESIS_NOT_QUALIFIED`. Architecture should allow heterogeneous
selection. If GPT-5 Nano fails one workload, choose the cheapest model
qualified for that exact workload; не повышать весь pipeline на общий
frontier fallback.

После live replay гипотеза о единой модели не подтверждена. Текущий
synthetic-proven набор гетерогенен: GPT-5.4 Nano для financial evidence и
Haiku 4.5 для source/domain/checksum. Из-за цены Haiku и отсутствия
actual-corpus evidence этот набор не готов к production.
