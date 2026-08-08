# Broker Reports — G4.4 Relation Necessity Research

Date: `2026-08-08`

Goal type: `RESEARCH_ONLY`

Goal status: `G4.4_RESEARCH_CLOSED`

## Verdict

```text
A. NO_RELATION_LAYER_NEEDED_YET
minimal relation set = ∅
```

Ни одна проверенная связь не удовлетворяет одновременно всем пяти критериям
необходимости persisted semantic relation. Удаление всех предполагаемых
relation objects не лишает текущего или уже определённого следующего
потребителя доказанной возможности: facts можно читать, фильтровать,
группировать и прослеживать до источника без relation layer.

G4.5 не имеет предмета реализации без нового evidence. Следующий допустимый
GOAL — `G4.6 Gate 4 Read Model`, без relation operations. Это не утверждение,
что relations никогда не понадобятся; это отказ строить их до появления
конкретного потребителя и неустранимого query-разрыва.

## Evidence boundary

Проверены current authority и contracts:

- [Pipeline Gates v1](../../stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md);
- [Gate 4 Financial Case Fact v1](../../stage2/contracts/BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v1.md);
- [G4.2 SQL Materialization v1](../../stage2/contracts/BROKER_REPORTS_GATE4_SQL_MATERIALIZATION.v1.md);
- [G4.3 Case Assembly v1](../../stage2/contracts/BROKER_REPORTS_GATE4_CASE_ASSEMBLY.v1.md);
- current nine-type Gate 3 dictionary and Role Pack used by the runtime.

Проверены реальные/representative proof-срезы:

- [real NDFL corpus evidence](../2026-08-07/BROKER_REPORTS_GATE3_NDFL_CORPUS_EVIDENCE_G3_3V.report.md);
- [dictionary corpus validation](../2026-08-07/BROKER_REPORTS_GATE3_NDFL_DICTIONARY_CORPUS_VALIDATION_G3_3V.report.md);
- [representative semantic quality](../2026-08-07/BROKER_REPORTS_GATE3_REPRESENTATIVE_SEMANTIC_QUALITY_G3_7B.report.md);
- [Gate 3 role-labeling closure](BROKER_REPORTS_GATE3_ROLE_LABELING_CLOSURE.report.md);
- [G4.3 multi-document closure](BROKER_REPORTS_GATE4_CASE_ASSEMBLY_G4_3_CLOSURE.report.md).

Проверка не запускала provider, LLM или большой pipeline и не делает claim о
полноте всех финансовых фактов в документах.

## Что уже доступно обычному коду

Каждый `Gate4FinancialCaseFactV1` содержит стабильный `fact_id`,
`financial_type`, exact Gate 3/canonical bindings, typed role values, исходные
literal/target bindings и status полноты ролей. Для текущих девяти типов:

| Financial type | Доступные роли после Gate 3/G4 | Достаточно для поиска без интерпретации документа |
| --- | --- | --- |
| `SECURITY_PURCHASE` | date, asset, quantity, amount, currency; optional unit_price | да |
| `SECURITY_DISPOSAL` | date, asset, quantity, amount, currency; optional unit_price | да |
| `DIVIDEND_INCOME` | date, amount, currency; optional asset | да |
| `COUPON_INCOME` | date, amount, currency; optional asset | да |
| `INTEREST_INCOME` | date, amount, currency | да |
| `SECURITIES_LENDING_INCOME` | date, amount, currency; optional asset | да |
| `ACCRUED_COUPON_COMPONENT` | amount, currency | частично: provenance доступен, но date/asset не входят в профиль |
| `TRANSACTION_CHARGE` | date, amount, currency; optional asset | да |
| `TAX_WITHHELD` | date, amount, currency; optional asset | да |

Текущий cache/read boundary напрямую поддерживает поиск по type, asset, period
и fact ID, а `read_case` возвращает полные fact JSON. Поэтому amount, currency и
source/provenance доступны обычному коду даже без отдельных SQL-индексов.
Если масштабу позже понадобится прямой фильтр по amount или source, это
небольшое расширение read/query boundary, а не новое финансовое утверждение.

## Queryable association не равна semantic relation

```text
queryable association:
рядом по type / asset / date / amount / source

semantic relation:
fact A действительно относится к fact B
```

Первое помогает найти кандидатов и уже доступно из Financial Case. Второе
влияет на downstream-решения и требует отдельного доказательства. Совпадение
полей само по себе не доказывает отношение.

## Матрица кандидатов

| Candidate | Реальная downstream-задача | Достаточно ли facts/query | Persisted relation | Граница | Почему |
| --- | --- | --- | --- | --- | --- |
| `TRANSACTION_CHARGE ↔ purchase/disposal` | найти расходы рядом со сделками; возможно позже учесть расход | да для поиска и группировки; exact allocation не доказан как текущая задача | нет | query сейчас; tax allocation — Gate 5 | corpus содержит и комиссии в строке/операции, и агрегаты по нескольким сделкам; единичная связь часто была бы ложной |
| `TAX_WITHHELD ↔ income` | показать удержания рядом с доходами; позже решить налоговый зачёт/атрибуцию | да для поиска по дате, валюте, активу и provenance | нет | query сейчас; налоговая атрибуция — Gate 5 | withholding встречается как на одной строке с доходом, так и на уровне income section; unique link не является общим source fact |
| `ACCRUED_COUPON_COMPONENT ↔ purchase/disposal` | показать НКД как компонент суммы сделки | corpus допускает локальный source context, но текущий Role Pack даёт только amount/currency | нет пока | возможный будущий Gate 4 кандидат только при доказанном consumer | это самый сильный data gap, но representative final-product proof не измерил положительный accrued-coupon fact и нет потребителя, теряющего возможность без сохранённой связи |
| `purchase ↔ disposal` | определить, какая покупка образует расход конкретной продажи | нет, если нужен точный lot allocation | нет в Gate 4 | Gate 5 | matching зависит от FIFO/cost basis, частичных количеств, налогового периода и методологии; это расчёт, а не неизменяемая история источника |
| `duplicate / same_event / confirms` | убрать двойной счёт или выбрать подтверждающий источник | query находит похожие facts; оба сохраняются с разным ID/provenance | нет | premature reconciliation | похожие значения не доказывают один event; current G4.3 намеренно сохраняет оба факта, а consumer и authority rule не заданы |
| `CONFLICTS_WITH` | заметить разные значения и выбрать/эскалировать результат | query может найти кандидатов; решение требует сначала доказать same event | нет | downstream-specific reconciliation | `10 000 != 12 000` ещё не конфликт без общей event identity; persisted relation преждевременно закрепила бы недоказанное сопоставление |

## Проверка пяти обязательных критериев

| Candidate | Почему не проходит обязательный набор |
| --- | --- |
| charge ↔ transaction | нет конкретного consumer для exact assertion; query достаточен для текущего использования; налоговый расход относится к Gate 5; сохранённого дорогого решения пока нет |
| tax ↔ income | exact attribution не доказана текущему consumer и в налоговом смысле принадлежит Gate 5; corpus не гарантирует unique pair; сохраняемого решения нет |
| accrued coupon ↔ transaction | потенциальный query gap есть, но нет representative positive current fact, конкретного consumer и доказательства дорогого повторяемого решения |
| purchase ↔ disposal | нарушает критерий «не Gate 5»: relation является lot/cost-basis policy result |
| duplicate-like | query достаточен для candidate discovery; semantic sameness и downstream authority не определены; решения для повторного сохранения нет |
| conflict | сначала нужен недоказанный same-event assertion; текущий consumer и дорогая semantic decision отсутствуют |

Для каждого кандидата нарушен хотя бы один критерий; обычно несколько.

## Что сознательно не нужно

- `BELONGS_TO_TRANSACTION` для каждой комиссии: aggregate charges не имеют
  одного корректного endpoint.
- `WITHHELD_FROM_INCOME` как обязательная Gate 4 relation: поиск уже возможен,
  а налоговая атрибуция должна появиться только в конкретной задаче Gate 5.
- `MATCHED_PURCHASE` / `MATCHED_DISPOSAL`: это FIFO/cost basis, не факт отчёта.
- `SAME_EVENT`, `DUPLICATE_OF`, `CONFIRMS`: без consumer и source-authority
  правила это premature reconciliation.
- `CONFLICTS_WITH`: отличие значений ещё не доказывает общую сущность.
- relation для любого совпадения type/date/asset/amount/source: это query
  association.
- generic graph, Relation Pack, relation schema/table, matching engine,
  confidence/scoring и LLM workflow: нет доказанного relation domain.

## Revisit triggers

Решение следует пересмотреть только если появится всё необходимое:

1. назван конкретный downstream consumer и exact assertion, без которого он
   действительно не работает;
2. показан representative current `FinancialAnnotationsV2`/Gate 4 fact case,
   где fact/query недостаточны;
3. доказано, что assertion не является Gate 5 tax policy;
4. request-time deterministic computation небезопасно или невозможно;
5. rebuild иначе повторяет дорогое semantic decision.

Первый приоритет для такого evidence — реальный role-complete
`ACCRUED_COUPON_COMPONENT` рядом с purchase/disposal: текущие positive
final-product measurements для этого типа отсутствуют. Это evidence gap, а не
разрешение заранее создать relation.

## KISS check

- Без relation layer текущие facts остаются полностью читаемыми и traceable.
- Обычный query уже решает candidate discovery и соседние выборки.
- Purchase/disposal allocation и налоговая атрибуция не переносятся из Gate 5.
- Инфраструктура вокруг недоказанной гипотезы не создаётся.

```text
G4.4_RESEARCH_CLOSED
NO_RELATION_LAYER_NEEDED_YET
minimal relation set = ∅
G4.5 = NOT_APPLICABLE_WITHOUT_NEW_EVIDENCE
NEXT_ALLOWED_GOAL = G4.6_GATE4_READ_MODEL
```
