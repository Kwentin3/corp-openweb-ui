# Broker Reports — Gate 2: blueprint канонического Fact Registry

Дата: 2026-07-23  
Статус: `GOAL_3_FACT_REGISTRY_BLUEPRINT: COMPLETED`

## Назначение

`Gate2FactRegistryFactory` должен стать единственным исполняемым источником правды о поддерживаемых Gate 2 financial fact types. Prompt, provider schema, materializer и validator получают данные из одного immutable registry snapshot.

Registry — versioned code-owned data, а не база customer facts и не prompt-файл.

## Предлагаемая структура

Минимальная будущая граница:

```text
broker_reports_gate2/
  registry/
    schema.py
    declarations/
      statement_facts_v1.py
      schedule_facts_v1.py
    factory.py
    validation.py
    compatibility.py
  decision_contract/
    factory.py
    validation.py
  materialization/
    factory.py
  projections/
    factory.py
```

Это не обязательные точные пути. Существенно разделение ответственности: registry declaration не должна зависеть от provider client, orchestration или artifact store.

## Registry snapshot

Snapshot имеет:

- `registry_id`;
- `registry_version`;
- `lifecycle_status`;
- ordered declarations;
- compatibility mappings;
- projection catalog revision;
- canonical content hash.

Любой extraction package фиксирует snapshot version/hash. Изменение declarations создаёт новую registry version; оно не меняет смысл ранее сохранённых facts.

## Декларация факта

| Поле | Обязательность | Назначение |
|---|---|---|
| `fact_type_id` | required | immutable ID с major semantic version |
| `title` | required | безопасное человекочитаемое имя |
| `definition` | required | нормативный экономический смысл |
| `semantic_category` | required | `event`, `state`, `aggregate`, `attribute` |
| `lifecycle` | required | `experimental`, `active`, `deprecated`, `retired` |
| `evidence_basis` | required | safe corpus count/family и review ref |
| `required_roles` | required | роли, без которых факт не материализуется |
| `optional_roles` | required | допустимые дополнительные роли |
| `forbidden_roles` | required | явно несовместимые роли |
| `role_specs` | required | value type, cardinality, normalization source |
| `date_period_policy` | required | event date, as-of date, period или schedule bucket |
| `unit_currency_policy` | required | required/optional/forbidden и совместимость |
| `sign_policy` | required | source sign, normalized sign, отсутствие предположений |
| `aggregation_policy` | required | allowed, dimensions, forbidden combinations |
| `identity_policy` | required | deduplication material |
| `source_families` | required | совместимые evidence families, не labels |
| `examples` | required | только synthetic/safe semantic examples |
| `counterexamples` | required | близкие, но несовместимые понятия |
| `projection_mappings` | required | versioned target profiles либо пусто |
| `gate3_relevance` | required | metadata и methodology blockers |
| `compatibility` | required | legacy aliases/mappings и migration status |

Пустые списки обязательны: отсутствие поля не должно означать неявное разрешение.

## Роли значений

Registry оперирует semantic roles, а не конкретными JSON paths:

- `amount`;
- `currency`;
- `unit`;
- `event_date`;
- `as_of_date`;
- `period_start`;
- `period_end`;
- `schedule_bucket`;
- `quantity`;
- `instrument_ref`;
- `account_ref`;
- `statement_scope_ref`;
- `component_kind`;
- `printed_label_evidence_ref`.

Каждый role spec задаёт cardinality, allowed primitive/value object types и source-ref requirement. Provider получает только роли, разрешённые текущему package; canonical validator проверяет полный профиль.

## Lifecycle и версия ID

Правила:

1. Исправление описания без изменения смысла меняет registry patch version, но не `fact_type_id`.
2. Изменение required roles, sign или aggregation semantics создаёт новый `fact_type_id` major version.
3. `experimental` разрешён только в qualification/shadow path.
4. `active` требует corpus evidence, deterministic tests и accepted migration decision.
5. `deprecated` остаётся читаемым и материализуемым только по compatibility policy.
6. `retired` читается для replay, но не включается в новые provider snapshots.
7. Alias используется для matching/migration, но никогда не становится canonical identity.

## Factory API

Предлагаемые узкие операции:

```python
snapshot = Gate2FactRegistryFactory.create(version="v1")
snapshot.get(fact_type_id)
snapshot.allowed_for(package_profile)
snapshot.build_decision_schema(package_profile, provider_profile)
snapshot.build_materialization_profile(fact_type_id)
snapshot.build_validation_profile(fact_type_id)
snapshot.build_projection_profile(fact_type_id, projection_id)
snapshot.resolve_legacy_id(legacy_id, artifact_version)
```

Factory должна быть pure/deterministic для одинаковых declarations и config. Она не читает customer corpus, сеть, prompt store или ArtifactStore.

## Генерация provider contract

Из snapshot строятся:

- ordered `fact_type_id` enum;
- bounded descriptions;
- disposition variants;
- разрешённые roles и source candidate refs;
- package-bound schema hash;
- provider-specific projection.

OpenAI projection сохраняет поддерживаемые строгие constraints. Gemini projection может снять часть динамических ограничений в соответствии с adapter profile, но не меняет canonical snapshot и validation profile.

## Генерация validator/materializer

Материализатор получает:

- validated decision;
- exact registry declaration;
- allowed source candidate map;
- deterministic package metadata.

Он сам:

- назначает canonical schema/version;
- нормализует bindings;
- проверяет required/optional/forbidden roles;
- создаёт fact ID и identity material;
- добавляет restrictions/audit;
- рассчитывает projection candidates.

Модель не возвращает полный внутренний fact JSON.

## Consistency validation

Registry build блокируется, если:

- повторяется `fact_type_id`;
- ID изменил semantic fingerprint без новой версии;
- одна роль одновременно required и forbidden;
- required role не имеет role spec;
- aggregation dimensions не определены в role specs;
- state не имеет `as_of`/period policy;
- event не имеет event/period policy;
- currency-required type допускает amount без currency policy;
- projection ссылается на неизвестный profile;
- active type не имеет evidence basis, examples, counterexamples и tests;
- alias образует цикл или неоднозначно ведёт к нескольким IDs;
- legacy mapping не ограничен artifact version;
- retired type попал в model-facing snapshot.

Отдельные golden tests должны фиксировать snapshot hash и generated schema hashes.

## Compatibility

Persisted artifacts сохраняются как есть. Compatibility adapter:

- читает `schema_version` и legacy `fact_type`;
- возвращает `legacy_identity`, optional canonical candidate и migration status;
- не переписывает stored artifact;
- не повышает неоднозначное соответствие до accepted canonical fact;
- позволяет replay старого validator по pinned revision.

Особенно важно:

- `document_summary_evidence` маппится в evidence kind, а не новый fact type;
- `unknown_source_row` маппится в legacy technical disposition;
- широкие legacy transaction IDs получают только explicit candidate mapping после corpus qualification;
- FNS specialized families сохраняют собственную schema family до отдельного migration decision.

## Управление изменениями

Добавление типа — отдельный небольшой PR с:

- safe evidence receipt;
- declaration;
- examples/counterexamples;
- schema/materializer/validator tests;
- projection decision;
- migration impact;
- registry hash change;
- reviewer от Gate 2 domain owner.

Изменение provider prompt само по себе не может добавить или изменить тип.

## Отвергнутые варианты

- definitions только в prompt: невалидируемо и дрейфует;
- enum constants в нескольких Functions: уже привело к смешению уровней;
- свободный model-generated type: нарушает deterministic consumption;
- одна гигантская JSON Schema на все типы: упирается в provider complexity и ухудшает выбор;
- новый registry service: преждевременная операционная сложность;
- universal accounting ontology: не подтверждена корпусом и Gate 3.

## Acceptance

`FACT_REGISTRY_FACTORY: DESIGNED`  
`IMMUTABLE_CANONICAL_IDS: REQUIRED`  
`VERSIONING_AND_LIFECYCLE: DEFINED`  
`REQUIRED_OPTIONAL_FORBIDDEN_ROLES: DEFINED`  
`PROMPT_AND_SCHEMA_GENERATION: REGISTRY_DRIVEN`  
`REGISTER_MAPPING: REGISTRY_DRIVEN_OR_EXPLICIT`  
`CONSISTENCY_VALIDATION: DEFINED`

