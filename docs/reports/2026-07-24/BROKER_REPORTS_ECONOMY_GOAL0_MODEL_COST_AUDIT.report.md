# Broker Reports — Economy Goal 0: current model usage and cost audit

Дата: 2026-07-24

Терминальный статус: `COMPLETED`.

## Результат

Все model-selection surfaces Broker Reports инвентаризированы. Gate 2 сейчас не соответствует новой economy policy: production defaults и qualification/live-proof инструменты допускают либо прямо выбирают дорогие модели. Gate 1 visual master также использует более дорогие Flash/Mini-модели, но в этом Goal он только зафиксирован как отдельная accepted quality boundary и не изменён.

Главный измеренный cost baseline — последний успешный full-scope Registry-driven shadow:

- canonical decision scopes: `39`;
- provider calls: `39`;
- provider/model: `openai_gpt` / `gpt-5.6-sol`;
- input tokens: `47 533`;
- output tokens: `7 102`;
- total tokens: `54 635`;
- fallback: `0`;
- estimated standard API cost: `$0.450725`.

Token usage взят агрегированно из private qualification evidence. Customer labels, values, source refs и raw provider output в Git не перенесены.

## Model call inventory

| Surface | Factory/runtime path | Current selection | Calls and retry behavior | Budget state | Economy replacement |
| --- | --- | --- | --- | --- | --- |
| Gate 1 PDF table intake | `PdfTableIntakeRuntimeFactory` | `models/gemini-3.5-flash` | один detection call на admitted candidate | Gate 1-specific bounds | Не менять в этой программе без отдельной visual qualification |
| Gate 1 dual VLM | `PdfDualVlmRuntimeFactory` | Gemini 3.5 Flash + `gpt-5.4-mini-2026-03-17` | multi-provider quality contour | 24k counted input / 16 384 output | Вне Gate 2 economy migration |
| Gate 1 structural repair | `PdfStructuralRepairRuntimeFactory` | `models/gemini-3.5-flash` | windowed visual calls | собственные structural bounds | Вне Gate 2 economy migration |
| Gate 1 passport/clarification | Gate 1 managed Prompt boundary | operator/workflow model selection | optional calls per document/run | отдельные Gate 1 limits | Вне Gate 2 economy migration |
| Gate 2 source extraction | `Gate2StructuredModelClientFactory` → `Gate2SourceFactRuntimeFactory` | default profile `openai_gpt`, resolved default `gpt-5.6-luna`; valve/config may request another approved ID | один call на package; no provider consensus | input estimate cap `12 000`; output/reasoning/cost cap отсутствует | qualified Nano/Flash-Lite/Haiku |
| Gate 2 domain extraction | `Gate2StructuredModelClientFactory` → `Gate2DomainSourceFactRuntimeFactory` | default profile `openai_gpt`, default `gpt-5.6-luna` | один call на package; `max_repair_attempts=1` допускает второй same-provider call | output/reasoning/cost cap отсутствует | qualified economy model, default one attempt |
| Gate 2 financial decision | `Gate2FinancialEvidenceProductionRuntimeFactory` через тот же model factory | наследует domain provider/model | один call на каждый accepted domain package | отдельного token/cost budget нет | qualified economy model |
| Full-scope shadow qualification | financial evidence shadow factory + canonical client | последний успешный run: `gpt-5.6-sol` | `39` calls, fallback/repair `0` | pre-run cost estimate отсутствует | cheapest qualified economy model |
| Gate 2-only checksum | checksum factory + canonical client | предыдущий run использовал явно выбранную модель | один strict call | token/cost budget отсутствует | qualified economy answering model |
| Production migration verifier | released Function boundary | hardcoded default `gpt-5.6-sol`; CLI override разрешён | один bounded domain call, затем один financial call при успехе domain | economy allowlist отсутствует | policy-generated exact economy ID |
| Full-document/e2e runner | released Function boundary | default `models/gemini-3.1-flash-lite` | package-count-derived calls | model identity фиксируется, cost guard отсутствует | сохранить после qualification |
| Synthetic/domain smokes | released Function boundary | explicit/default provider profile + model selection | bounded calls; direct provider bypass отсутствует | economy policy отсутствует | policy-generated allowlist |
| Atomic release config | release manifest and Function valves | Gate 2 profiles публикуют expensive approved/fallback IDs | не выполняет calls | позволяет дорогой runtime selection | economy policy identity + restrictive valves |
| Test fixtures | model client/provider/runtime tests | содержат Sol/Luna/Terra, Gemini Flash/Pro и Sonnet cases | network boundaries mocked; domain logic не mocked | доказывают текущий широкий profile contract | оставить expensive IDs только как rejected test cases |
| Private diagnostic runner | ignored local Goal 9 verifier wrapper | parameterized; сохранённый Flash-Lite candidate | bounded Function call | policy enforcement отсутствует | тот же policy-generated exact ID |
| Managed OpenWebUI connections | maintained OpenWebUI config | enabled OpenAI, Anthropic и Gemini connections | transport boundary only | connection сама не ограничивает workload tier | runtime policy должна сузить connection models |

## Expensive defaults and escalation surfaces

Обнаружены:

- `gpt-5.6-luna` — текущий рекомендуемый extraction default, запрещён новой policy;
- `gpt-5.6-sol` — approved ID, recommended fallback и default production migration verifier;
- `models/gemini-3.5-flash` — approved Gate 2 ID, но не Flash-Lite;
- `models/gemini-3.1-pro-preview` — recommended Gemini fallback;
- `claude-sonnet-5` — recommended Anthropic fallback;
- `gpt-5.4-mini-2026-03-17` — Gate 1 visual path и historical qualification tooling;
- `model_id` runtime/config surface может выбрать любой уже approved дорогой ID;
- provider profiles содержат дорогие fallback IDs, хотя canonical runtime сейчас не выполняет cross-provider automatic fallback;
- domain `max_repair_attempts=1` допускает повторный платный вызов;
- OpenAI/Gemini requests не задают явный output cap, reasoning policy или paid-tool prohibition;
- Anthropic adapter задаёт чрезмерный `max_tokens=32768`;
- full-scope runner не формирует safe cost estimate до начала provider calls.

Hidden automatic cross-provider tier escalation в текущем canonical runtime не найден. Риск — explicit valve/config/runner selection и future fallback metadata, а не действующий consensus router.

## Maintained stage availability

Read-only `/api/models` вернул `37` моделей. Релевантные дешёвые exact IDs:

- `models/gemini-3.1-flash-lite` — доступен;
- `models/gemini-3.5-flash-lite` — доступен;
- `gpt-5-nano` — не опубликован;
- `gpt-5.4-nano` — не опубликован;
- `claude-haiku-4-5-20251001` — не опубликован aggregate models endpoint.

OpenAI, Anthropic и Gemini maintained connections включены. Connection presence не считается contract qualification.

## Cost baseline and economy estimates

Оценки используют измеренные `47 533` input и `7 102` output tokens, standard synchronous pricing и предполагают неизменный token profile. Они не являются qualification result.

| Model | Official tier | Input/output USD per MTok | Estimated 39-call run | Saving vs Sol |
| --- | --- | ---: | ---: | ---: |
| `gpt-5.6-sol` | prohibited frontier | `5.00 / 30.00` | `$0.450725` | baseline |
| `gpt-5.6-luna` | prohibited until separately accepted | `1.00 / 6.00` | `$0.090145` | `80.00%` |
| `gpt-5-nano` | allowed Nano | `0.05 / 0.40` | `$0.005217` | `98.84%` |
| `gpt-5.4-nano` | allowed Nano | `0.20 / 1.25` | `$0.018384` | `95.92%` |
| `models/gemini-3.1-flash-lite` | allowed Flash-Lite | `0.25 / 1.50` | `$0.022536` | `95.00%` |
| `models/gemini-3.5-flash-lite` | allowed Flash-Lite | `0.30 / 2.50` | `$0.032015` | `92.90%` |
| `claude-haiku-4-5-20251001` | allowed Haiku | `1.00 / 5.00` | `$0.083043` | `81.58%` |

Official references:

- OpenAI GPT-5 nano: https://developers.openai.com/api/docs/models/gpt-5-nano
- OpenAI GPT-5.4 nano: https://developers.openai.com/api/docs/models/gpt-5.4-nano
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini 3.5 Flash-Lite model: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- Claude models/pricing: https://platform.claude.com/docs/en/about-claude/models/overview
- Claude structured outputs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs

## Acceptance

- `MODEL_CALL_SITES`: `FULLY_INVENTORIED`;
- `EXPENSIVE_DEFAULTS`: `IDENTIFIED`;
- `HIDDEN_TIER_ESCALATION`: `IDENTIFIED`;
- `COST_PER_FULL_SCOPE_RUN`: `ESTIMATED`;
- Gate 1 runtime change: `ZERO`;
- provider calls made by this audit: `ZERO`;
- Knowledge/RAG/vector delta: `ZERO`.

## Required next slice

Goal 1 должен создать отдельный versioned code-owned economy policy. Нельзя просто заменить default model string: policy обязана запретить дорогие IDs во всех runtime/config/verifier surfaces и генерировать один exact allowlist.
