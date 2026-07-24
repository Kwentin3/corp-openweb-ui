# Broker Reports — Gate 2: археология текущего домена

Дата: 2026-07-23  
Статус: `GOAL_0_CURRENT_DOMAIN_ARCHAEOLOGY: COMPLETED`

## Краткий вывод

Gate 2 уже имеет строгий контур происхождения данных, материализации и валидации, но не имеет единого управляемого финансового словаря. Девять строковых идентификаторов одновременно используются как:

- домены маршрутизатора;
- идентификаторы extractor;
- разрешённые типы канонического факта;
- элементы model-facing enum;
- fallback и техническое состояние.

Из-за этого `unknown_source_row` означает сразу «fallback-маршрут», «тип факта» и «не удалось типизировать». `document_summary_evidence`, наоборот, является исходным доказательством, но находится в одном enum с финансовыми событиями и состояниями. Это не единая таксономия.

## Активные поверхности

| Поверхность | Фактическая роль | Создаёт | Валидирует | Потребляет | Класс |
|---|---|---|---|---|---|
| `FACT_TYPES` | девять допустимых строковых ID | код контракта | provider schema и canonical validator | router, extractors, stitcher, Gate 3 manifest | смешанный |
| `FACT_DOMAIN_ORDER` | порядок доменов маршрутизации | router factory | route validator | domain extractor orchestration | технический routing |
| `DOMAIN_EXTRACTOR_IDS` | ID исполнителя для каждого домена | router factory | domain runtime | orchestration | технический |
| `NO_FACT_REASON_VALUES` | причины отсутствия факта | selection schema | selection validator | materializer, coverage | технический disposition |
| `broker_reports_source_fact_selection_v3` | компактный ответ модели | модель | selection validator | materializer | decision transport |
| `broker_reports_source_facts_v0` | канонические source-local facts | materializer | canonical validator | stitcher, answer context, Gate 3 manifest | финансовый факт и evidence |
| domain wrappers | пакет фактов одного router-domain | domain runtime | domain validator | stitcher | transport package |
| stitching/ownership | покрытие refs и выбор владельца | deterministic stitcher | stitch validator | manifest/answer path | промежуточный artifact |
| answer-context projection | сокращённое представление фактов | context selector | context validator | ответный контур | projection |
| Gate 3 context manifest | граф артефактов и счётчики фактов | manifest factory | manifest validator | будущий Gate 3 | transport manifest |
| FNS 2-NDFL typed path | отдельные специализированные fact families | deterministic adapter | отдельный validator | parity/reporting | legacy parallel domain |

Основные определения находятся в:

- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_fact_contracts.py:38`;
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_domain_routing.py:15`;
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_fact_selection.py:21`;
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_fact_validation.py:414`;
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate2_source_fact_stitching.py:198`;
- `services/broker-reports-gate1-proof/broker_reports_gate1/gate3_context_manifest.py:571`.

## Текущие идентификаторы и их фактическая семантика

| ID | Финансовый смысл | Другие роли | Формальное определение | Управляемость |
|---|---|---|---|---|
| `trade_operation` | операция с инструментом | router domain, extractor ID base | набор минимальных полей и subtype candidates | ID стабилен, нормативное определение неполно |
| `income` | поступление дохода | router domain, extractor ID base | сумма обязательна | слишком широкий |
| `withholding_tax` | удержание налога | router domain, extractor ID base | сумма и валюта обязательны | тип факта, но методология Gate 3 отсутствует |
| `fee_commission` | комиссия или сбор | router domain, extractor ID base | сумма обязательна | несколько экономических видов объединены |
| `cash_movement` | движение денежных средств | router domain, extractor ID base | сумма обязательна | событие, направление хранится в subtype |
| `currency_fx` | валютная сумма, курс или конвертация | router domain, extractor ID base | сумма, курс или converted amount | смешивает событие и атрибут |
| `position_snapshot` | состояние позиции | router domain, extractor ID base | дата, количество, сумма или identifier | смешивает позиции клиента и statement balances |
| `document_summary_evidence` | напечатанный итог или summary evidence | router domain, extractor ID base, fact type | любое нормализованное значение | не является однородным финансовым типом |
| `unknown_source_row` | сохранение непокрытого source row | fallback domain, extractor, fact type, ownership status | bindings запрещены | перегружен и противоречив |

`FACT_DOMAIN_ORDER`, `DOMAIN_EXTRACTOR_IDS` и `DOMAIN_ALLOWED_FACT_TYPES` строятся из тех же строк (`gate2_domain_routing.py:17-33`). Поэтому разделить уровни настройкой prompt невозможно: смешение закреплено кодом и схемами.

## Model-facing контракт и конфликт

В `broker_reports_source_fact_selection_v3` одна строка `decision_type` выбирается из объединения разрешённых `FACT_TYPES` и `NO_FACT_REASON_VALUES`; рядом всегда присутствует массив `value_bindings` (`gate2_source_fact_selection.py:138-142`).

После schema-valid ответа deterministic validator накладывает правила, которых нет в структуре union:

- no-fact причины не допускают bindings;
- `unknown_source_row` не допускает bindings (`gate2_source_fact_selection.py:234-260`);
- остальные типы требуют собственный минимум значений;
- материализатор превращает decision в полный `broker_reports_source_facts_v0`.

Следовательно, schema-valid состояние может быть семантически недопустимым. Это подтверждено stage-контролем: строгая схема прошла во всех 41 вызовах, но 20 пакетов были отвергнуты; основные классы ошибок — bindings при `unknown_source_row` и bindings при no-fact decision.

## Канонический fact contract

Полный v0-контракт содержит provenance, original/normalized refs, extracted fields, дату, сумму, валюту, количество, инструмент, confidence, completeness, evidence, issues, downstream hints и audit. Deterministic validator:

- проверяет принадлежность source refs пакету;
- запрещает поля налогового расчёта Gate 3 (`gate2_source_fact_validation.py:49`);
- проверяет минимум значений по типу (`gate2_source_fact_validation.py:621`);
- создаёт стабильные fact IDs и integrity material;
- не разрешает модели публиковать факт напрямую.

Это сильная часть текущего решения и должна быть сохранена. Проблема находится до canonical validation: в словаре типов и decision contract.

## Provider schema reality

OpenAI adapter передаёт строгую схему без изменений. Gemini adapter рекурсивно сохраняет структуру, но снимает `const`, большинство динамических `enum`, форматы, диапазоны, длины и описания; небольшой список статических semantic enum сохраняется (`gate2_provider_adapters.py:397`, `gate2_provider_adapters.py:663-723`). Канонический validator затем повторно проверяет снятые ограничения.

Это означает:

- единая внутренняя декларация возможна;
- provider projection должна генерироваться фабрикой;
- нельзя считать provider-valid ответ каноническим фактом;
- нельзя вручную дублировать определения в prompt, schema и validator.

## Register-like поверхности

Ни один текущий output не является полноценным финансовым регистром:

- source facts — атомарные source-local утверждения;
- domain wrappers — транспорт;
- stitching — ownership и coverage;
- answer context — сокращённая проекция;
- Gate 3 manifest — граф ссылок и счётчики;
- `gate3_ledger_candidate` — только boolean hint в downstream metadata (`gate2_source_fact_contracts.py:419`).

Нет формального набора измерений, ресурсов, периодичности, correction/reversal semantics, replay и ledger posting rules. Предыдущие контракты также оставляют reconciliation и intermediate ledgers будущему Gate 3.

## Legacy и параллельные пути

FNS 2-NDFL adapter использует отдельную схему `broker_reports_fns_2ndfl_source_facts_v1` и отдельные families: identity, income row, deduction row, tax summary и metadata (`gate2_fns_2ndfl_contracts.py:12`, `gate2_fns_2ndfl_contracts.py:29`). Это детерминированный специализированный путь, а не часть общего девятиэлементного словаря.

Его нельзя молча объединять с новым registry: нужен явный compatibility mapping и отдельное решение о том, какие families являются source evidence, а какие — canonical facts.

## История формирования

Ключевая последовательность:

1. исходный Gate 2 pipeline;
2. provider factory и package-bound schemas;
3. domain context packages и gate isolation;
4. компактный selection contract;
5. deterministic materialization;
6. сокращение enum/schema complexity;
7. positional coverage и text labels;
8. semantic-selection revision.

Каждый шаг локально уменьшал техническую боль, но единого владельца финансовых определений не появилось. Смысл остался распределён между constants, prompts, schemas, binding profiles и validators.

## Findings

| Finding | Severity | Решение в blueprint |
|---|---|---|
| один ID используется как router domain, extractor domain и fact type | high | отдельные namespace и registry IDs |
| `unknown_source_row` объединяет три разных состояния | critical | `unclassified_fact`, `no_fact`, `unsupported` |
| source evidence включено в financial fact enum | high | отдельный evidence layer |
| decision schema допускает противоречивые комбинации | critical | структурные disposition variants |
| определения размножены по нескольким Functions | high | registry factory как source of truth |
| полноценного register layer нет | medium | честная projection-модель без преждевременного ledger |
| specialized FNS path живёт отдельно | medium | versioned compatibility adapter, без silent merge |

## Acceptance

`CURRENT_DOMAIN_SURFACES: FULLY_INVENTORIED`  
`MIXED_SEMANTIC_LEVELS: EXPLICITLY_IDENTIFIED`  
`FREE_FORM_TYPE_CREATION: ZERO_IN_SCHEMA_BUT_DEFINITIONS_DISTRIBUTED`  
`UNOWNED_DOMAIN_TERMS: IDENTIFIED`  
`LEGACY_AND_ACTIVE_PATHS: CLASSIFIED`

