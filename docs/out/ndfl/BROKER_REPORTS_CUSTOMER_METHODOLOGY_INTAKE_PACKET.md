# Broker Reports Customer Methodology Intake Packet

Status: Customer methodology intake packet draft
Date: 2026-07-04
Scope: Stage 2 Broker Reports / XLS NDFL

## 1. Customer Explanation

Мы не просим финальную налоговую консультацию.

Нам нужно понять, как специалист заказчика сейчас трактует брокерские документы, какие поля считает обязательными, какие промежуточные таблицы проверяет и какие спорные случаи выносит на ручную проверку.

Цель этого пакета - не заменить специалиста, а не дать LLM придумать методологию. После ответов мы сможем подготовить проверяемый workflow:

```text
document taxonomy
-> document inventory
-> source facts schema
-> intermediate ledgers
-> declaration-oriented model
-> specialist review state
```

Результат остается `ready_for_specialist_review`, а не финальной декларацией, не налоговой консультацией и не отправкой в ФНС.

## 2. First-Priority Questions

Эти вопросы нужны до synthetic proof и staging proof.

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-P1-001` | Какие налоговые годы входят в pilot scope? | Выбирает `official_source_set_id`; форма 2025 не является универсальной для всех лет. | yes | list of tax years | `period_applicability.tax_year` |
| `METH-P1-002` | Какие брокеры, страны и источники документов входят в scope? | Определяет document taxonomy, source jurisdiction и будущие source documents. | yes | broker/country/source list | `document_inventory_refs[]` |
| `METH-P1-003` | Какие типы доходов входят в scope: продажи бумаг, дивиденды, купоны, прочие доходы? | Определяет набор `income_events` и expected assertions. | yes | controlled list | `source_fact_events.income_events[]` |
| `METH-P1-004` | ИИС и не-ИИС счета обрабатываются в одном workflow или раздельно? | Влияет на candidate code signals и Appendix 8-related review. | yes | policy choice | `accounts[].account_type`, `tax_base_items[]` |
| `METH-P1-005` | Какие документы считаются полным пакетом для проверки? | Задает missing-data rules и source document plan. | yes | required document checklist | `document_manifest[]` |
| `METH-P1-006` | Какие коды или категории доходов специалист использует для каждого типа дохода? | Candidate signals из official registry нельзя повышать до правил без методологии. | yes | mapping table | `income_categories[]` |
| `METH-P1-007` | Как учитываются комиссии брокера и какие из них только source facts? | Fee facts не становятся declaration-eligible автоматически. | yes | rule table | `fee_events[]`, `fees_and_expenses[]` |
| `METH-P1-008` | Как разделяются дивиденды, купоны и прочие выплаты? | Нужна корректная классификация `income_events` и withholding links. | yes | classification rule | `income_events[]`, `dividends_and_withholding[]` |
| `METH-P1-009` | Как обрабатывается удержанный иностранный налог до проверки специалистом? | Запрещает LLM самостоятельно решать treatment/credit. | yes | review rule | `withholding_events[]` |
| `METH-P1-010` | Как выбирается курс и дата курса для foreign-currency событий? | Currency conversion является calculation gap без rate/date methodology. | yes | rate/date policy | `currency_events[]`, `currency_context[]` |
| `METH-P1-011` | Что делать, если summary total отличается от detailed rows? | Определяет conflict precedence. | yes | precedence rule | `review_state.conflicts[]` |
| `METH-P1-012` | Какая детализация source reference достаточна: документ, страница, таблица, строка, ячейка? | Нужна для source facts schema и acceptance. | yes | granularity threshold | `source_granularity` |
| `METH-P1-013` | Какие intermediate ledgers специалист хочет видеть? | Определяет review output и synthetic assertions. | yes | ledger list | `income_events`, `securities_operation_events`, `fee_events`, `withholding_events`, `currency_events` |
| `METH-P1-014` | Что означает `ready_for_specialist_review`? | Финальный readiness gate не должен стать tax correctness claim. | yes | readiness criteria | `review_state.readiness` |
| `METH-P1-015` | Какие expected outputs нужны для приемки первого proof? | Определяет semantic assertions вместо full JSON snapshot equality. | yes | artifact list | `expected_review_state_assertions[]` |

## 3. Technical Appendix

### 3.1. Scope

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-SCOPE-001` | Какие налоговые годы входят в pilot scope? | Выбирает period-aware official source set. | yes | list of years | `period_applicability.tax_year` |
| `METH-SCOPE-002` | Какие брокеры, страны и source systems входят в scope? | Определяет document classes and country/source handling. | yes | broker/country/source list | `document_inventory_refs[]` |
| `METH-SCOPE-003` | Какие account types входят в scope, включая ИИС и не-ИИС? | Влияет на Appendix 8 и candidate code review. | yes | account type list | `accounts[]` |
| `METH-SCOPE-004` | Какие income types входят в scope: sales, dividends, coupons, securities operations, other income? | Определяет source fact event coverage. | yes | income type list | `source_fact_events.income_events[]` |
| `METH-SCOPE-005` | Какие document types обязательны для complete package? | Определяет missing-data rules. | yes | document checklist | `document_manifest[]` |

### 3.2. Income Categories And Codes

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-CODE-001` | Какие income group/type codes используются для каждого in-scope income type? | Candidate official codes cannot be promoted without approval. | yes | code mapping table | `income_categories[]` |
| `METH-CODE-002` | Candidate code signals 2025 можно использовать только для 2025 или нужно отдельно проверять каждый год? | Prevents cross-period assumptions. | yes | period policy | `official_requirement_refs[]` |
| `METH-CODE-003` | Как split/flag mixed income rows? | Prevents invalid grouping. | yes | splitting rule | `income_events[]` |
| `METH-CODE-004` | Какой source имеет приоритет при конфликте broker summary и detailed rows? | Controls conflict resolution. | yes | precedence matrix | `review_state.conflicts[]` |

### 3.3. Securities Operations

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-SEC-001` | Какие operation types должны попадать в securities operation ledger? | Определяет expected source fact events. | yes | operation type list | `securities_operation_events[]` |
| `METH-SEC-002` | Какие fields обязательны для buy/sell rows? | Позволяет отличить missing field от optional gap. | yes | required fields list | `securities_operation_events[]` |
| `METH-SEC-003` | Как обрабатывать corporate actions: split, merger, redemption, spin-off, cancellation, reclassification? | Prevents unsupported operation treatment. | yes | treatment matrix | `securities_operation_events[]`, `review_state.questions_to_specialist[]` |
| `METH-SEC-004` | Как связать buy row с sell row для review, если broker report не дает явную связь? | Определяет calculation gap и source granularity. | yes | linking rule | `tax_base_items[].source_fact_schema_refs` |

### 3.4. Fees And Expenses

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-EXP-001` | Какие broker fees/commissions являются только source facts, а какие могут идти в declaration review? | Avoids treating every fee as eligible. | yes | fee policy table | `fee_events[]`, `fees_and_expenses[]` |
| `METH-EXP-002` | Какие expense categories требуют Appendix 8 review? | Connects fee events to official requirement refs. | yes | category mapping | `official_requirement_refs[]` |
| `METH-EXP-003` | Какая source granularity достаточна для securities operation rows: summary, table row, cell, statement section? | Sets evidence requirements. | yes | granularity threshold | `source_granularity` |
| `METH-EXP-004` | Какие intermediate ledgers специалист ожидает видеть: income, securities operations, fees, withholding, currency, declaration assertions? | Defines review output. | yes | ledger list | `source_fact_events` |

### 3.5. Dividends, Coupons And Withholding

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-WH-001` | Как отделять dividends и coupons от other income rows? | Defines income event classification. | yes | classification rule | `income_events[]` |
| `METH-WH-002` | Какой source authoritative для withholding facts? | Defines evidence precedence. | yes | source precedence rule | `withholding_events[]` |
| `METH-WH-003` | Как представлять foreign tax paid before specialist review? | Prevents final treatment claims. | yes | review representation | `withholding_events[]`, `dividends_and_withholding[]` |
| `METH-WH-004` | Какие evidence fields нужны для country/source attribution? | Supports Appendix 1/2 candidate mapping. | yes | required fields list | `income_events[].income_country` |

### 3.6. Currency Handling

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-CUR-001` | Какой exchange-rate source и rate-date rule используются для каждого event type? | Required before currency calculations. | yes | rate policy | `currency_events[]` |
| `METH-CUR-002` | Сохранять ли converted values from source documents как source facts или игнорировать до deterministic calculation? | Defines currency event handling. | yes | preservation rule | `currency_events[].converted_amount` |
| `METH-CUR-003` | Как обрабатывать missing currency labels or mixed-currency summaries? | Defines missing/uncertain states. | yes | missing/uncertain rule | `review_state.uncertain[]` |

### 3.7. Readiness And Acceptance

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-READY-001` | Какие conditions делают результат `ready_for_specialist_review`? | Defines readiness gate. | yes | readiness criteria | `review_state.readiness` |
| `METH-READY-002` | Какие official requirement refs должны быть present for acceptance? | Connects registry to model. | yes | requirement list | `official_requirement_refs[]` |
| `METH-READY-003` | Какие expected outputs нужны для acceptance: event ledgers, declaration candidates, questions, conflict report, synthetic assertions? | Defines proof artifacts. | yes | artifact list | `expected_review_state_assertions[]` |
| `METH-READY-004` | Какие unresolved issues допустимы как warnings, а какие block next step? | Defines severity. | yes | severity matrix | `review_state.missing[]`, `review_state.conflicts[]` |
| `METH-READY-005` | Что приоритетнее дальше: `synthetic_case_001` design или methodology intake completion? | Selects delivery path. | no | priority choice | `next_step` |

### 3.8. Expected Outputs

| question_id | question | why_it_matters | blocking | expected_answer_type | related_model_path |
| --- | --- | --- | --- | --- | --- |
| `METH-OUT-001` | Нужен ли отдельный income event ledger в output? | Fixes prompt expected output shape. | yes | yes/no plus format | `source_fact_events.income_events[]` |
| `METH-OUT-002` | Нужен ли separate conflict report? | Makes summary/detail mismatches visible. | yes | yes/no plus format | `review_state.conflicts[]` |
| `METH-OUT-003` | Нужен ли questions-to-specialist block grouped by data/methodology/calculation? | Prevents mixed blocker lists. | yes | grouping rule | `questions_to_specialist[]` |
| `METH-OUT-004` | Нужны ли declaration-oriented candidates in the same output or as separate artifact? | Keeps source facts separate from declaration mapping. | yes | output packaging rule | `declaration_model` |

## 4. Status

```text
CUSTOMER_METHODOLOGY_INTAKE_PACKET_READY
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_CUSTOMER_SESSION
```
