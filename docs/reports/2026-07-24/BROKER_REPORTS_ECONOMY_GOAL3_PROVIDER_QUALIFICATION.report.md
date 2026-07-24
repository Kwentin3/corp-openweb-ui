# Broker Reports — Economy Goal 3: квалификация дешёвых провайдеров

Дата: 2026-07-24

Терминальный статус: `COMPLETED_WITH_PROVIDER_GAPS`.

## Результат

Ни одна доступная economy-модель не прошла неизменённый Gate 2 financial
evidence contract полностью. Policy обновлена до `1.2.0`; hash:
`e6a297c359ff55fe48b22cf568261ae3bc0e329378f648b6438227e9a93ef35c`.
Qualified/active allowlist остаётся пустым.

| Provider | Exact model | Статус | Terminal evidence |
| --- | --- | --- | --- |
| OpenAI | `gpt-5-nano-2025-08-07` | `UNAVAILABLE` | exact ID отсутствует в maintained stage model inventory |
| OpenAI | `gpt-5.4-nano-2026-03-17` | `UNAVAILABLE` | exact ID отсутствует в maintained stage model inventory |
| Gemini | `models/gemini-3.1-flash-lite` | `NOT_QUALIFIED` | `financial_evidence_decision_unclassified_shape_invalid` |
| Gemini | `models/gemini-3.5-flash-lite` | `UNSUPPORTED_CONTRACT` | source probe проходит, но capability-probe route не запускает financial contract |
| Anthropic | `claude-haiku-4-5-20251001` | `UNSUPPORTED_CONTRACT` | `gate2_model_schema_response_format_rejected` |

HTTP success сам по себе не считался квалификацией. Gemini 3.1 успешно
прошёл source extraction, затем financial provider response был отклонён
canonical validator. Haiku успешно прошёл source extraction, но maintained
Anthropic adapter не смог представить financial response schema провайдеру.

## Bounded live evidence

Использован один synthetic non-customer CSV slice домена `income` с
candidate binding. PDF, customer values, direct provider bypass, search,
tools и multi-provider consensus не использовались.

- Gemini 3.1 source: 1 call, 5 058 input, 700 output, 5 758 total tokens;
- Gemini 3.1 financial: 1 call, canonical reject;
- Gemini 3.5 source probe: 1 call, 5 065 input, 687 output, 5 752 total;
- Gemini 3.5 financial: 0 calls — route не предоставляет этот contract;
- Haiku source: 1 call, 6 395 input, 464 output;
- Haiku financial: 1 provider attempt, schema response format rejected;
- OpenAI Nano: 0 calls;
- expensive fallback: 0;
- hidden repair: 0.

Все synthetic artifact cases очищены. Knowledge/RAG/vector delta равен нулю.
Provider raw output и private refs в Git не записывались.

## Contract checks

Неизменёнными остались:

- four-disposition decision schema;
- Registry-bound type IDs;
- source-ref enums;
- canonical parsing и malformed-state rejection;
- deterministic materialization;
- fallback/repair prohibition.

Source-only success не повышал статус до `QUALIFIED`. Policy кодирует
terminal statuses явно и по-прежнему fail-closed отклоняет все пять exact
model IDs при runtime selection.

## Provider gaps и следующий шаг

- OpenAI Nano: владелец — maintained `openai_gpt` connection; следующий шаг —
  добавить exact Nano ID в connection и повторить strict financial probe;
  Mini/Sol/full GPT/o-series запрещены.
- Gemini 3.1 Flash-Lite: владелец — Gemini schema projection/prompt boundary;
  следующий шаг — добиться валидного conditional disposition без repair;
  обычный Flash и Pro запрещены.
- Gemini 3.5 Flash-Lite: владелец — qualification harness route; следующий
  шаг — предоставить bounded financial probe для capability candidate;
  обычный Flash и Pro запрещены.
- Anthropic Haiku: владелец — maintained Anthropic schema adapter/connection;
  следующий шаг — подтвердить поддержку financial strict schema;
  Sonnet и Opus запрещены.

## Acceptance

- `GEMINI_FLASH_LITE`: `NOT_QUALIFIED`;
- `OPENAI_NANO`: `UNAVAILABLE`;
- `ANTHROPIC_HAIKU`: `UNSUPPORTED_CONTRACT`;
- `EXPENSIVE_FALLBACK_CALLS`: `ZERO`;
- `GOAL_3_CHEAP_MODEL_QUALIFICATION`: `COMPLETED_WITH_PROVIDER_GAPS`.
