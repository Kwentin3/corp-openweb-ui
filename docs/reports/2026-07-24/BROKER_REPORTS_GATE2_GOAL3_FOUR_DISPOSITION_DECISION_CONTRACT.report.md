# Broker Reports — Gate 2 Goal 3: four-disposition decision contract

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Добавлен factory-managed model-facing contract:
`broker_reports_gate2_financial_evidence_decision_v1`.

Contract допускает ровно четыре terminal dispositions:

1. `typed_input`;
2. `unclassified_financial_input`;
3. `no_financial_input`;
4. `unsupported`.

Единый перегруженный `unknown` не используется.

## Model authority

Модель может вернуть только:

- один из четырёх dispositions;
- Registry-bound `input_type_id` только для `typed_input`;
- package-bound `source_value_ref` bindings;
- bounded reason code.

Модель не возвращает:

- canonical objects или artifact IDs;
- provenance, coverage и audit objects;
- context projections;
- налоговые поля;
- свободные type IDs;
- source values вне package;
- free-JSON fallback.

Production contract создаётся только через
`Gate2FinancialEvidenceDecisionContractFactory.create`.

## Структурные гарантии

Canonical JSON Schema строится из immutable Registry snapshot и конкретного
source package.

- Для `typed_input` создаётся отдельная ветвь на каждый допустимый active
  Registry type.
- Required roles обязательны и принимают только совместимые candidate refs.
- Optional roles присутствуют в strict schema как candidate ref или `null`.
- Typed-ветвь не публикуется, если package не содержит совместимый candidate
  хотя бы для одной required role.
- `unclassified_financial_input` не имеет canonical type ID, но сохраняет
  один или несколько package-bound value refs.
- `no_financial_input` и `unsupported` содержат только disposition и bounded
  reason code.
- `additionalProperties: false` закрывает смешанные и system-owned states.

Таким образом структурно непредставимы:

- `no_financial_input` с bindings;
- `typed_input` без type ID;
- `typed_input` без required roles;
- `unclassified_financial_input` с canonical type ID;
- свободный type ID;
- binding на ref вне package.

## Provider projections

OpenAI и Gemini projections создаются из одного canonical contract.

- OpenAI получает strict `json_schema` без ослабления canonical constraints.
- Gemini получает structural projection с сохранёнными disposition, type,
  role и source-ref enums.
- Не поддерживаемые Gemini `minItems`, `maxItems` и `uniqueItems` снимаются
  только в provider projection.
- Canonical parser повторно проверяет exact shape, non-empty unclassified
  bindings, uniqueness, Registry scope, role/value-type compatibility и
  package membership.

Для синтетического contract fixture:

- Registry SHA-256:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- canonical schema SHA-256:
  `ac4e501c8cf7133e5acadfda4024fea1d6b9b48b48eae5e00895dedb271a2ef0`;
- OpenAI projection SHA-256:
  `3e83d4d0120b9cd57372869373bfa29b4da5fc33b7d18cee645b2d799a865ad5`;
- Gemini projection SHA-256:
  `43108084c526fe5f1cb705f94673468d765cfadfa9a63cad4032ed8209437e50`.

Hashes provider schemas являются package-bound и не объявляются глобальными
product-schema hashes.

## Boundary и anti-drift

- Contract импортирует только stdlib и Registry authority.
- ArtifactStore, provider clients, customer data и runtime state не нужны.
- Prompt/provider не может расширить dispositions, type IDs или refs.
- Source family фильтрует Registry types до построения schema.
- В module нет materialization, canonical artifact publication или context
  projection.

Goal 3 не включает production runtime switch или stage release. Следующий
отдельный Goal 4 должен материализовать подтверждённое decision в
детерминированные terminal artifacts.

## Validation

- decision contract tests: `22 passed`;
- decision + Registry + catalog tests: `44 passed`;
- full Broker Reports suite: `1191 passed`, `20 skipped`;
- module/test ruff: `passed`;
- repository privacy guard: `3 passed`;
- private labels, values, filenames и provider output в Git: `ZERO`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL3_FOUR_DISPOSITION_DECISION_CONTRACT.receipt.safe.json).

## Acceptance

`UNKNOWN_OVERLOAD: ZERO`

`CONTRADICTORY_STATES: UNREPRESENTABLE`

`REGISTRY_BOUND_TYPES: ONLY`

`NO_FINANCIAL_INPUT_WITH_BINDINGS: IMPOSSIBLE`

`UNCLASSIFIED_VALUES: PRESERVED`

`PROVIDER_FALLBACK_TO_FREE_JSON: ZERO`

`GOAL_3_FOUR_DISPOSITION_DECISION_CONTRACT: COMPLETED`
