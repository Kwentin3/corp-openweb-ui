# Broker Reports — Gate 2 Goal 4: correction проверки dimension policy

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Закрыт обнаруженный перед Goal 7 fail-open разрыв между Registry и
детерминированной materialization.

Registry уже объявлял для каждого active input type:

- обязательность date/period;
- обязательность currency/unit.

Однако materializer и independent artifact validator проверяли только
`required_roles`. Для optional roles, которые становились обязательными через
отдельную policy, это позволяло создать typed input без требуемого измерения.

## Исправление

Добавлен единый deterministic policy-check, который выполняется:

1. materializer до создания typed input ID и artifact;
2. independent validator при проверке готового artifact.

Поддерживаются все Registry policy:

- `event_date_required`;
- `as_of_date_required`;
- `period_required`;
- `date_or_period_required`;
- `currency_required`;
- `unit_required`;
- `currency_or_unit_required`;
- `optional`;
- `forbidden`.

Для period принимается либо единая роль `period`, либо полная пара
`period_start` + `period_end`. Неполная пара не удовлетворяет policy.

Нарушение date/period или currency/unit policy теперь terminal fail-closed.
Никакого defaulting, fallback или скрытого repair нет.

## Regression proof

Synthetic tests доказывают:

- cash snapshot без currency и unit отклоняется;
- printed metric без date и period отклоняется;
- printed metric без currency и unit отклоняется;
- policy `currency_or_unit_required` принимает явно связанную unit;
- independent validator отдельно отклоняет artifact, из которого после
  materialization удалена обязательная currency;
- legacy compatibility fixture явно содержит currency и продолжает проходить
  dual-read contract.

## Validation

- materialization + compatibility + context + decision + catalog + Registry:
  `101 passed`;
- full Broker Reports suite: `1248 passed`, `20 skipped`;
- ruff для изменённых Python-файлов: `passed`;
- `git diff --check`: `passed`;
- customer/private values в Git: `ZERO`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL4_DIMENSION_POLICY_CORRECTION.receipt.safe.json).

## Scope boundary

Production runtime не переключён. Stage не изменён. Provider calls и
customer contour не выполнялись. Исправление является обязательной
предпосылкой для честной shadow qualification Goal 7.

## Acceptance

`DATE_PERIOD_POLICY: FAIL_CLOSED`

`CURRENCY_UNIT_POLICY: FAIL_CLOSED`

`HIDDEN_DEFAULTING_OR_REPAIR: ZERO`

`INDEPENDENT_ARTIFACT_VALIDATION: PASSED`

`GOAL_4_DIMENSION_POLICY_CORRECTION: COMPLETED`
