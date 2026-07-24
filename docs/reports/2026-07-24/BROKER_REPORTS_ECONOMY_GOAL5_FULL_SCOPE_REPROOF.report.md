# Broker Reports — Economy Goal 5: full-scope shadow reproof

Дата: 2026-07-24

Терминальный статус: `NOT_CLOSED`.

## Результат

Economy full-scope shadow run не начат: code-owned selection preflight для
`gate2_financial_evidence` завершился typed blocker:

`gate2_economy_no_qualified_model`.

Policy `broker_reports_economy_model_policy_v1` версии `1.2.0`, hash
`e6a297c359ff55fe48b22cf568261ae3bc0e329378f648b6438227e9a93ef35c`,
содержит `0` qualified/active models. Provider calls, fallback, repair и
дорогие model calls равны нулю.

Это не считается full-scope success. Coverage и value retention дешёвой
моделью не переподтверждены.

## Authorized scope

Preflight связан с последним принятым repository-safe scope receipt:

- receipt SHA-256:
  `9b2990f59972caa1f3dde920d180ab17d38f4d6b65ba22a797e3beff20dd5288`;
- source-ready documents: `1`;
- parent source units: `12`;
- derived segments: `210`;
- domain packages: `41`;
- canonical decision scopes: `39`;
- authorized selected source refs: `455`.

Эти показатели являются идентичностью предыдущего принятого scope, а не
новым economy result. Private corpus не загружался, поскольку fail-closed
selection сработал раньше.

Существующий private runner закреплён за запрещённым `gpt-5.6-sol`; он не
использовался и не изменялся. Registry, materializer, checksum comparator и
financial evidence contract не ослаблялись.

## Economy execution evidence

- provider calls: `0`;
- input/output/total tokens: `0 / 0 / 0`;
- fallback: `0`;
- hidden repair: `0`;
- expensive models used: `0`;
- actual successful economy run cost: `NOT_MEASURED_NO_RUN`;
- blocked preflight cost: `$0`.

Последний принятый дорогой baseline, только для сравнения:

- exact model: `gpt-5.6-sol`;
- calls: `39`;
- input/output/total tokens: `47 533 / 7 102 / 54 635`;
- estimated cost: `$0.450725`.

Ранее рассчитанные same-token economy estimates (`$0.005217`–`$0.083043`)
остаются гипотетическими. Экономия не считается достигнутой без успешного
economy contract run.

## Provider gaps

| Exact model | Failed capability / terminal code | Owner | Запрещённый fallback | Узкий следующий шаг |
| --- | --- | --- | --- | --- |
| `gpt-5-nano-2025-08-07` | maintained inventory unavailable / `stage_models_endpoint_model_absent` | `openai_gpt` connection | Mini, Sol, full GPT, o-series | добавить exact Nano ID и повторить strict financial qualification |
| `gpt-5.4-nano-2026-03-17` | maintained inventory unavailable / `stage_models_endpoint_model_absent` | `openai_gpt` connection | Mini, Sol, full GPT, o-series | добавить exact Nano ID и повторить strict financial qualification |
| `models/gemini-3.1-flash-lite` | canonical acceptance / `financial_evidence_decision_unclassified_shape_invalid` | Gemini schema/prompt boundary | обычный Flash, Pro | получить валидный conditional disposition без repair |
| `models/gemini-3.5-flash-lite` | financial qualification route / `financial_qualification_not_exposed_by_capability_probe_route` | qualification harness | обычный Flash, Pro | предоставить bounded financial probe |
| `claude-haiku-4-5-20251001` | provider schema acceptance / `gate2_model_schema_response_format_rejected` | Anthropic adapter/connection | Sonnet, Opus | подтвердить strict financial schema support |

## Проверки

- economy preflight: typed blocker, provider calls `0`;
- shadow contract + selection + budget focused suite: `31 passed`;
- provider raw output/customer values/private refs в Git: `0`.

## Acceptance

- `FULL_SCOPE_COVERAGE`: `NOT_PASSED_NO_QUALIFIED_MODEL`;
- `VALUE_RETENTION`: `NOT_REPROVEN`;
- `EXPENSIVE_MODELS_USED`: `ZERO`;
- `ECONOMY_RUN_COST`: `NOT_MEASURED_NO_RUN`;
- `GOAL_5_FULL_SCOPE_ECONOMY_REPROOF`: `NOT_CLOSED`.
