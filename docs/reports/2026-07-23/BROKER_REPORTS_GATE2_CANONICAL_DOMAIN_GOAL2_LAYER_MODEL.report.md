# Broker Reports — Gate 2: доменная слоистая модель

Дата: 2026-07-23  
Статус: `GOAL_2_DOMAIN_LAYER_MODEL: COMPLETED`

## Решение

Минимальная модель Gate 2 состоит из шести разделённых слоёв и отдельного downstream mapping. Модель не строит универсальную бухгалтерскую онтологию: она только превращает source evidence в проверяемые source-local финансовые факты и ограниченные проекции.

```text
Gate 1 source evidence
        ↓
Gate 2 decision/disposition
        ↓
Canonical fact registry → deterministic materialization
        ↓
Canonical fact instances
        ↓
Registry projection layer
        ↓
Printed/calculated aggregates

Gate 3 relevance mapping — отдельные metadata, не часть fact identity
```

## 1. Source evidence

Владелец: Gate 1.  
Содержит: source refs, labels, values, rows, tables, page/context refs, provenance, literal document summary.

Инварианты:

- финансовая квалификация отсутствует;
- исходный label не становится canonical ID;
- значения остаются привязаны к source refs;
- evidence может быть неоднозначным или неполным.

`document_summary_evidence` должен быть перемещён сюда как `source_evidence_kind`, а не оставаться типом финансового факта.

## 2. Decision/disposition

Владелец: Gate 2 extraction decision contract.  
Содержит ровно одно состояние на decision unit:

- `typed_fact`;
- `unclassified_fact`;
- `no_fact`;
- `unsupported`.

Это техническая классификация результата, не финансовая сущность. Слой отвечает на вопрос «можно ли материализовать факт?», но не хранит сам полный факт.

Инварианты:

- `typed_fact` выбирает только ID из package-bound registry snapshot;
- `unclassified_fact` сохраняет evidence bindings, но не создаёт canonical fact;
- `no_fact` не содержит value bindings;
- `unsupported` фиксирует безопасную техническую причину;
- `unknown` как единое состояние отсутствует.

## 3. Canonical financial fact registry

Владелец: Gate 2 domain registry.  
Содержит immutable определения допустимых event/state/aggregate/attribute facts, роли значений, sign/aggregation/deduplication semantics и lifecycle.

Registry не содержит customer data и не является output модели. Из него фабрики строят:

- package-bound enum и provider schema;
- model-facing descriptions;
- deterministic validation profile;
- materialization profile;
- projection metadata;
- compatibility mapping.

## 4. Canonical fact instance

Владелец: deterministic Gate 2 materializer и canonical validator.  
Это source-local утверждение, созданное только после принятого `typed_fact`.

Минимальная сущность:

- `fact_id`;
- `fact_type_id` и registry version;
- source evidence bindings;
- нормализованные role values;
- date/period, unit/currency и scope;
- confidence/completeness;
- issue/restriction refs;
- deduplication identity material;
- integrity hash.

Модель не создаёт `fact_id`, audit metadata, restrictions или register entries. Код берёт их из validated package, registry declaration и source refs.

## 5. Accounting/register projection

Владелец: Gate 2 projection factory, декларации принадлежат registry или отдельному versioned projection catalog.

Проекция отвечает на вопрос «в каком узком представлении показать уже принятый факт». Это не второй источник финансовой истины.

Допустимые начальные profiles:

- `statement_line_item_view_v1`;
- `balance_snapshot_view_v1`;
- `movement_schedule_view_v1`;
- `printed_metric_view_v1`.

Каждая запись проекции ссылается на canonical `fact_id`; она не переопределяет его тип и не создаёт double-entry posting. Если для одного факта допустимо несколько представлений, mapping версионируется независимо.

## 6. Aggregate/metric

Владелец зависит от происхождения:

- `printed` aggregate — source-local canonical fact с прямым evidence;
- `calculated` aggregate — deterministic projection/aggregation artifact;
- tax/P&L aggregate — Gate 3, если требует методологии.

Обязательные различия:

| Вид | Источник истины | Можно пересчитать | Deduplication |
|---|---|---|---|
| printed total | документ | нет; можно только сверить | source scope + label/context + period |
| calculated total | набор accepted facts + rule version | да | rule version + ordered inputs |
| reconciliation difference | два сравниваемых результата | да | comparison contract + inputs |

Printed и calculated суммы не сливаются даже при равенстве значений.

## Отдельный Gate 3 mapping

`gate3_relevance` — metadata:

- возможные downstream потребители;
- требуемые methodology decisions;
- запрещённые до методологии выводы;
- версия mapping.

Он не участвует в `fact_type_id` и не позволяет Gate 2 создавать cost basis, P/L, tax base, calculated tax или declaration mapping. Эти поля уже запрещены current canonical validator и остаются запрещёнными.

## Пространства имён

| Namespace | Пример | Может ли совпадать с другим namespace |
|---|---|---|
| evidence kind | `document_summary` | строка может быть похожа, identity отдельна |
| router domain | `statement_balance_domain_v1` | нет автоматического равенства fact type |
| extractor ID | `statement_balance_extractor_v1` | технический ID |
| disposition | `unclassified_fact` | никогда не fact type |
| fact type | `cash_balance_snapshot_v1` | immutable canonical ID |
| projection profile | `balance_snapshot_view_v1` | отдельная версия |
| aggregate rule | `sum_same_currency_scope_v1` | отдельная версия |
| Gate 3 mapping | `gate3_relevance_mapping_v1` | downstream metadata |

## Ownership contracts

| Компонент | Владеет | Не владеет |
|---|---|---|
| registry loader/factory | declarations, lifecycle, schema generation | corpus extraction |
| decision schema factory | package-bound provider contract | canonical definitions |
| decision validator | disposition shape и allowed IDs/roles | normalization semantics |
| materializer | deterministic fact construction | свободная классификация |
| canonical validator | provenance, registry rules, integrity | provider heuristics |
| projection factory | versioned views | financial fact identity |
| Gate 3 consumer | methodology и downstream calculations | изменение Gate 2 facts |

## Сквозные инварианты

1. Один semantic level — один namespace.
2. Canonical ID никогда не рождается из source label.
3. Provider-valid output не равен accepted fact.
4. Неизвестное финансовое содержание сохраняется без фиктивного fact type.
5. Любой aggregate указывает, printed он или calculated.
6. Любая проекция сохраняет lineage до canonical fact и source evidence.
7. Gate 3 mapping не изменяет Gate 2 identity.
8. Registry additions проходят corpus evidence и lifecycle review.

## Почему модель минимальна

Не создаются:

- chart of accounts;
- double-entry journal;
- universal instrument ontology;
- tax ontology;
- отдельный микросервис;
- новый VLM path.

Нужны только декларативный registry package, небольшие фабрики projection/schema/validation и compatibility adapter. Это заменяет распределённые constants, а не добавляет параллельную платформу.

## Acceptance

`SOURCE_EVIDENCE_LAYER: DEFINED`  
`CANONICAL_FACT_LAYER: DEFINED`  
`REGISTER_PROJECTION_LAYER: DEFINED`  
`AGGREGATE_LAYER: DEFINED`  
`TECHNICAL_DISPOSITION_LAYER: DEFINED`  
`GATE3_MAPPING_LAYER: SEPARATE`

