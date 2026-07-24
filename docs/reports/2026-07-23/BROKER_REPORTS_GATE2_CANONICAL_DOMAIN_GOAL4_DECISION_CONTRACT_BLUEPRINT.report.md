# Broker Reports — Gate 2: blueprint model-facing decision contract

Дата: 2026-07-23  
Статус: `GOAL_4_DECISION_CONTRACT_BLUEPRINT: COMPLETED`

## Решение

Модель должна возвращать не внутренний canonical fact, а короткое решение: disposition, выбранный registry ID и source-value bindings. Всё остальное строит код.

Четыре состояния имеют разные структуры:

| Disposition | `fact_type` | Evidence/value bindings | Canonical fact |
|---|---|---|---|
| `typed_fact` | обязательный ID из package snapshot | обязательные роли конкретного registry type | создаётся кодом |
| `unclassified_fact` | отсутствует | сохраняются evidence/value refs | не создаётся |
| `no_fact` | отсутствует | отсутствуют | не создаётся |
| `unsupported` | отсутствует | только bounded evidence refs, без role claims | не создаётся |

`unknown_source_row` удаляется из model-facing финансовых типов. Это compatibility status старых artifacts, не новый canonical fact.

## Каноническая форма

Корневой объект остаётся обычным object; union находится внутри `decisions.items`.

```json
{
  "schema_version": "broker_reports_fact_decisions_v1",
  "decisions": [
    {
      "source_unit_ref": "opaque_ref",
      "disposition": "typed_fact",
      "fact_type": "cash_balance_snapshot_v1",
      "bindings": [
        {"role": "amount", "source_value_ref": "opaque_ref"},
        {"role": "as_of_date", "source_value_ref": "opaque_ref"}
      ],
      "reason_code": null
    }
  ]
}
```

Пример показывает transport shape, а не production schema. Factory генерирует отдельные `anyOf` branches.

## Структурные варианты

### `typed_fact`

- `disposition` фиксирован как `typed_fact`;
- `fact_type` — enum из registry snapshot конкретного package;
- для каждого `fact_type` создаётся bounded branch;
- binding roles и source refs ограничены declaration и package candidates;
- required roles присутствуют;
- no-fact/unsupported reason codes запрещены.

### `unclassified_fact`

- `disposition` фиксирован;
- `fact_type` отсутствует либо имеет обязательный `null` для OpenAI strict representation;
- bindings содержат source refs без canonical role claim либо ограниченные evidence roles;
- причина выбирается из небольшого enum: `no_registry_match`, `ambiguous_registry_match`, `insufficient_context`;
- результат идёт в registry-gap review, не в canonical facts.

### `no_fact`

- `fact_type` отсутствует/`null`;
- `bindings` отсутствуют либо обязательный пустой массив в OpenAI strict representation;
- причина выбирается из no-fact enum;
- source unit считается покрытым техническим решением, но не финансовым фактом.

### `unsupported`

- нет `fact_type`;
- допустимы только evidence refs;
- reason code указывает техническое ограничение extractor/profile;
- нельзя использовать как общий синоним неоднозначности.

## Provider capability

### OpenAI

OpenAI Structured Outputs:

- требует корневой `object`, а не root-level `anyOf`;
- поддерживает nested `anyOf`, если каждая ветка сама входит в поддерживаемое подмножество;
- в strict mode требует `additionalProperties: false` и все properties в `required`;
- optional представляется через nullable type;
- не поддерживает `allOf`, `not`, `dependentSchemas`, `if/then/else`.

Поэтому OpenAI projection использует:

```text
root object
  decisions: array
    items: anyOf
      typed_fact branch
      unclassified_fact branch
      no_fact branch
      unsupported branch
```

Ссылки: [OpenAI Structured Outputs — supported schemas](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas), [OpenAI strict mode](https://developers.openai.com/api/docs/guides/function-calling#strict-mode).

### Gemini

Текущая документация Gemini Structured Outputs поддерживает `anyOf`, `enum`, required properties и основные object/array constraints, но предупреждает о неполном JSON Schema subset и отказах для больших или глубоких схем. `oneOf` в Generate Content API трактуется как `anyOf`, поэтому на исключительность `oneOf` полагаться нельзя.

Ссылки: [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output), [Gemini Generate Content schema fields](https://ai.google.dev/api/generate-content).

Текущий repo adapter дополнительно снимает `const`, динамические enums, ranges, formats и descriptions для соблюдения schema-complexity budget (`gate2_provider_adapters.py:663-723`). Он уже умеет сохранять небольшие semantic enums по имени property.

Для будущей реализации нужен bounded adapter change, а не смена provider policy:

- сохранить статический enum `disposition`;
- использовать уже сохраняемый property `fact_type` для package-bound canonical IDs;
- ограничить каждый package небольшим registry snapshot;
- сохранить `anyOf` branches;
- при provider schema rejection завершать вызов fail-closed, не переходить к свободному JSON.

Это должно сначала пройти capability fixture и реальный provider smoke. До этого Gemini projection имеет статус design, не production-ready.

## Почему прямой discriminator не является основой

JSON Schema `discriminator` не нужен и не входит в общий надёжный subset двух provider paths. Различие задают:

- `anyOf`;
- branch-specific required properties;
- small enum на `disposition`;
- package-bound `fact_type` enum;
- `additionalProperties: false`.

Canonical validator всё равно повторно проверяет выбор branch и registry profile. Provider schema уменьшает число недопустимых ответов, но не заменяет бизнес-валидацию.

## Factory generation

`Gate2DecisionContractFactory.create(package, registry_snapshot, provider_profile)`:

1. определяет допустимые registry types по source family/domain hypothesis;
2. создаёт typed branch на каждый допустимый type;
3. встраивает allowed roles и opaque source refs;
4. добавляет три технические disposition branches;
5. строит provider projection;
6. рассчитывает canonical/adapted schema hashes;
7. отдаёт тот же validation profile deterministic validator.

Router domain лишь сокращает snapshot. Он не становится fact type и не исключает `unclassified_fact`.

## Детерминированные проверки после модели

- ровно одно decision на обязательный source decision scope;
- source refs принадлежат package;
- `fact_type` существует и разрешён snapshot;
- roles соответствуют required/optional/forbidden declaration;
- cardinality и value types соблюдены;
- no-fact bindings отсутствуют;
- unclassified evidence сохранено и не материализовано;
- unsupported reason совместим с extractor profile;
- никакие Gate 3 поля не появились;
- canonical fact создаётся только materializer.

## Как устраняется текущая регрессия

Текущая пара `decision_type=unknown_source_row` + непустые bindings schema-valid, но запрещена validator. В новой форме:

- если значение финансовое, но тип неизвестен — только `unclassified_fact`, bindings разрешены;
- если факта нет — только `no_fact`, bindings структурно пусты;
- если extractor не способен обработать — `unsupported`;
- `typed_fact` не может выбрать технический reason.

Противоречие перестаёт быть допустимым состоянием контракта.

## Отвергнутые варианты

- один плоский enum типов и reason codes — повторяет текущую ошибку;
- свободный Markdown — удобен человеку, но требует неоднозначного parser;
- полный canonical fact от модели — возвращает низкоуровневую сложность;
- prompt-only условные правила — не делают состояние непредставимым;
- fallback в non-strict JSON — ослабляет fail-closed boundary;
- второй model call только для исправления shape — дороже и не устраняет доменный конфликт.

## Acceptance

`FREE_FORM_FACT_TYPES: ZERO`  
`UNKNOWN_OVERLOAD: ZERO`  
`TYPED_UNCLASSIFIED_NO_FACT: SEPARATED`  
`CONTRADICTORY_SCHEMA_STATES: UNREPRESENTABLE_IN_CANONICAL_CONTRACT`  
`PROVIDER_CAPABILITY_LIMITS: DOCUMENTED`

