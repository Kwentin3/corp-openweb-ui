# Broker Reports — Gate 2 Goal 3: correction OpenAI schema projection

Дата: 2026-07-24

Статус: `COMPLETED`

## Причина

Первый реальный Goal 7 shadow attempt завершился до model output:

- OpenWebUI/OpenAI вернул `HTTP 400`;
- provider adapter классифицировал ответ как
  `gate2_model_schema_response_format_rejected`;
- точная причина — keyword `uniqueItems` не разрешён live OpenAI strict
  response-format dialect;
- fallback и repair не выполнялись;
- failed qualification сохранён в private ignored contour и не включён в
  успешный результат.

SHA-256 private failure artifact:
`0775b990a15ffef8fc243c7d847797e7eed12c9a748743323b10a7e8a5ff2acb`.

## Исправление

Canonical Goal 3 schema не ослаблена и по-прежнему содержит
`uniqueItems: true`.

Добавлена узкая deterministic OpenAI projection:

- создаётся deep copy canonical schema;
- удаляется только доказанно неподдерживаемый `uniqueItems`;
- `minItems`, `maxItems`, canonical dispositions, type IDs и candidate enums
  сохраняются;
- canonical parser по-прежнему terminally отклоняет duplicate bindings.

Gemini projection и materialization contract не изменены.

## Live proof

На synthetic non-customer package выполнен один strict-schema probe через
существующие OpenWebUI и provider-adapter boundaries:

- HTTP status: `200`;
- provider schema accepted: `true`;
- terminal disposition:
  `unclassified_financial_input`;
- canonical schema содержит `uniqueItems`: `true`;
- OpenAI provider projection содержит `uniqueItems`: `false`;
- fallback: `zero`;
- repair: `zero`.

SHA-256 private probe artifact:
`d66fbcdce09652170cd1ecad3329d49a2e245b99a81880dce7c4ef817c03fc9b`.

Customer values и provider raw output в Git не добавлены.

## Validation

- decision + materialization + compatibility: `63 passed`;
- full Broker Reports suite: `1248 passed`, `20 skipped`;
- ruff: `passed`;
- `git diff --check`: `passed`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL3_OPENAI_SCHEMA_PROJECTION_CORRECTION.receipt.safe.json).

## Scope boundary

Runtime и stage не изменены. Goal 7 остаётся незакрытым до нового полного
shadow run на corrected merged `main`.

## Acceptance

`CANONICAL_SCHEMA_SEMANTICS: PRESERVED`

`OPENAI_SCHEMA_DIALECT: LIVE_ACCEPTED`

`DUPLICATE_BINDING_VALIDATION: FAIL_CLOSED`

`FALLBACK_OR_REPAIR: ZERO`

`GOAL_3_OPENAI_SCHEMA_PROJECTION_CORRECTION: COMPLETED`
