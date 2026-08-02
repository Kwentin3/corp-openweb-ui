# Broker Reports DOC6 Logical-Row Table Recovery

Status: `PASSED_INACTIVE`

Effective date: 2026-08-03

## 1. Простыми словами

Grid-first подход пытался уложить любую таблицу в обязательную тетрадную сетку. Это удобно для регулярного прайс-листа, но ломает реальные PDF: заголовок группы может занимать всю ширину, у подытога меньше элементов, вложенная строка сдвинута, а одна таблица продолжается на следующей странице. Искусственные пустые клетки в такой ситуации уже не описывают документ, а придумывают его.

DOC6 считает таблицу упорядоченной последовательностью логически связанных строк. Это похоже на поезд: важны порядок вагонов, назначение каждого вагона и связи между ними; одинаковое число мест в каждом вагоне не требуется.

## 2. Каноническая модель

Managed Document v2 использует:

```text
TABLE
→ ordered_rows[]
→ role, nesting_level и parent_row_id каждой строки
→ ordered entries каждой строки
→ optional logical_columns[]
→ source_parts[], relations[] и issues[]
→ optional geometry/span evidence
```

`rows[][]`, обязательная прямоугольность и одинаковое число entries не являются источником истины. Managed Document v1 не изменён; v2 остаётся отдельным неактивным контуром.

## 3. Logical Row, роли, вложенность и entries

Logical Row имеет уникальный `row_id`, непрерывный `ordinal`, одну наблюдаемую роль, `nesting_level`, optional `parent_row_id`, ordered `entries`, source anchors, geometry evidence и явные issues. Поддержаны роли `TABLE_TITLE`, `COLUMN_HEADER`, `GROUP_HEADER`, `DATA`, `SUBTOTAL`, `TOTAL`, `NOTE`, `CONTINUATION_HEADER`, `UNKNOWN`.

Entry имеет свой ID и порядок, вид `LABEL`, `VALUE`, `UNIT`, `MARKER`, `NOTE` или `UNKNOWN`, исходный текст и optional привязку к logical column. Строки могут иметь разное число entries; фиктивные `EMPTY` для выравнивания не создаются.

Logical columns создаются только при повторяемо доказанном выравнивании или заголовке. Имена нейтральны или происходят из header path. Если связь не доказана, entry сохраняется с `logical_column_id = null` и issue, без финансовой догадки.

## 4. Geometry как evidence

Геометрия доказывает границы таблицы и row bands, порядок, отступ, baseline, X-выравнивание, ruled regions, широкие области и continuation. Она проверяет row/entry ownership и optional column bindings, но не является обязательным model-visible содержимым. Spans представлены только как optional coverage/relation evidence; они не порождают пустые координатные entries. LLM Document View v2 выводит строки, роли, уровни, parents, entries, columns и safe pointers, но не bbox, координаты или private traces.

## 5. Что взято из остановленного DOC5.1

Checkpoint сохранён в `feat/broker-reports-doc5-1-span-aware-table-recovery` на commit `80947692366b639f5f00056972373557e99ad197`. После review переиспользованы нейтральные наблюдения и механизмы: PDF renders/crops, transcripts, source hashes, words/bboxes, ruled-cell и physical-span evidence, exact-once ownership, overlap checks, continuation evidence, независимый visual-gold процесс, canonical JSON, integrity и privacy проверки.

Не перенесены отменённый schema contract, `rows[][]`, rectangular-grid-first owner, `cell_spans` как центральная модель, обязательный `COVERED_BY_SPAN`, фиктивные empty cells и cell/span-count parity. DOC5.1 implementation не merge-ился.

## 6. Реальный corpus

| Документ | Таблицы | Rows | Entries | Logical columns | Source parts | Результат |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `real_pdf_1` | 4/4 | 22 | 42 | 8 | 4 | `table_01`–`table_04` разделены, границы и порядок совпали |
| `real_pdf_2` | 0/0 | 0 | 0 | 0 | 0 | no-table/document-order control passed |
| `real_pdf_4` | 12/12 | 123 | 369 | 32 | 12 | все 12 таблиц совпали |
| `real_pdf_5` | 12/12 | 212 | 1927 | 108 | 14 | все 12 таблиц совпали с локальной noncritical uncertainty |

Итого: 28/28 таблиц, 357/357 rows, 2338/2338 entries, 148 logical columns и 30 source parts. Шесть исходных TABLE не регрессировали.

## 7. UNKNOWN, unresolved relations и continuation

Единственный `UNKNOWN` row role находится в `real_pdf_5_table_11`, row ordinal 4, safe pointer `sp:real_pdf_5_table_11:row:004`. Его порядок и entries сохранены. Единственный unresolved parent находится в следующей строке той же таблицы, ordinal 5, safe pointer `sp:real_pdf_5_table_11:row:005`. Он помечен `UNRESOLVED_ROW_PARENT`; parent не угадан.

Unresolved column bindings: 0. Visual gold содержит пять явно учтённых noncritical ambiguities и ни одного blocker.

`real_pdf_5_table_05` восстановлена как одна таблица из двух source parts и 45 rows; `real_pdf_5_table_06` — из двух source parts и 74 rows. Общий порядок сохранён, repeated material не создал новую таблицу. False/missing continuation: 0.

## 8. Ownership и source/value accounting

Все 11,396 source words разделены на 3,629 table words и 7,767 paragraph words. Unresolved table words, multiple entry owners, paragraph/table overlap и table text duplicated as paragraph равны нулю. Invented, dropped и duplicated source values также равны нулю.

## 9. Три parity и честное adjudication

Frozen precomparison gold остался byte-unchanged. Raw base-gold сравнения PDF→Managed и PDF→View имеют статус `FAILED`: 29 critical/source-value mismatches, из них 27 source-surface `ENTRY_TEXT` и две производные `HEADER_PATH` проверки.

Независимый post-comparison sealed errata содержит 27 записей: 27 resolved, 0 unresolved; original gold и evaluator не переписывались. Полный учёт: `29 = 27 entry surfaces + 2 header paths`.

После применения sealed source-authority adjudication:

```text
PDF → Managed Document v2 = PASSED
Managed Document v2 → LLM Document View v2 = PASSED
PDF → LLM Document View v2 = PASSED
```

Missing/extra rows, wrong row order/role/nesting/parent, wrong entry value/order/row/column binding, wrong headers, subtotal/total binding, false split/merge/continuation, source-pointer и alignment mismatches равны нулю. `PASSED` относится к sealed adjudicated authority, а не скрывает raw base-gold failure.

## 10. Tests и CI

```text
sealed real-corpus evaluator = PASSED (4 documents, 28 tables, pipeline errors 0)
full local service suite = 2716 passed, 5 pre-existing skipped, 6 warnings
focused DOC6/v1/architecture = 352 passed
recovery + PDF builder = 205 passed
independent targeted review = 239 passed
full Ruff on every changed Python file = passed
repository CI Ruff profile E9,F63,F7,F82 = passed
compileall = passed
10 generated-asset checks = passed
historical generated audit byte-exact = passed
three generated Function bundles exact, diff = 0
privacy guard = 3 passed
git diff --check = passed
implementation exact-head GitHub CI run 30770742050 = SUCCESS
evidence exact-head GitHub CI = reported in terminal response after the evidence commit
```

Repository-wide unrestricted `ruff check .` still reports 264 pre-existing errors outside DOC6. Они не скрыты и не исправлялись в этом goal; changed-file Ruff и реальный CI profile прошли.

## 11. Delivery и non-change

```text
base = 623801ce5c9d89db273f6e654a2501167b65342b
implementation commit = 85b238f751e01c4223a548fd9872638c6cf4d2ce
implementation PR = #263 MERGED
implementation merge = 4d1e6297a93893fefafc23fab3b8d8ed47b435e4
evidence PR = reported after PR creation
evidence merge = reported in terminal response due to merge self-reference
Managed Document v1 changes = 0
product route changes = 0
generated bundle diff = 0
provider calls = 0
production model qualification = NOT_STARTED
product activation = NOT_STARTED
```

Canonical safe results находятся в `docs/stage2/BROKER_REPORTS_DOC6_LOGICAL_ROW_RECOVERY_RESULTS.safe.json` и `docs/stage2/BROKER_REPORTS_DOC6_ROW_PARITY.safe.json`. Safe closure receipt: `BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.receipt.safe.json` рядом с этим отчётом. Private PDF, gold, Managed/View payloads, source values, geometry и traces в Git не добавлены.

## 12. Terminal status

```text
DOC6_LOGICAL_ROW_TABLE_MODEL = PASSED
EXPECTED_LOGICAL_TABLES_TOTAL = 28
REPRESENTED_LOGICAL_TABLES_TOTAL = 28
VISUAL_GOLD_ROWS_TOTAL = 357
MANAGED_DOCUMENT_ROWS_MATCHED_TOTAL = 357
VISUAL_GOLD_ENTRIES_TOTAL = 2338
MANAGED_DOCUMENT_ENTRIES_MATCHED_TOTAL = 2338
UNKNOWN_ROW_ROLES_TOTAL = 1
UNRESOLVED_COLUMN_BINDINGS_TOTAL = 0
CRITICAL_ROW_MISMATCHES_TOTAL = 0
CRITICAL_ENTRY_MISMATCHES_TOTAL = 0
INVENTED_SOURCE_VALUES_TOTAL = 0
DROPPED_SOURCE_VALUES_TOTAL = 0
DUPLICATED_SOURCE_VALUES_TOTAL = 0
PDF_TO_LLM_VIEW_V2_ROW_PARITY = PASSED
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
