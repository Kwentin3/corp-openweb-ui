# Broker Reports DOC5 Geometry-Backed Table Recovery

Status: `BLOCKED_DOC1_BODY_CELL_SPAN_UNREPRESENTABLE`

Effective date: 2026-08-02

## 1. Простыми словами

В PDF есть клетки, которые занимают сразу несколько колонок. Исходная геометрия это показывает, но текущий Managed Document v1 записывает только обычную прямоугольную строку значений и `EMPTY/UNREADABLE/UNKNOWN` для отдельной позиции.

Поэтому он не умеет отличить настоящую пустую клетку от места, которое покрыто большой итоговой клеткой слева. Назвать такое место `EMPTY` означало бы придумать структуру. DOC5 прямо требует в этой ситуации остановиться.

## 2. Failure taxonomy и матрица

Frozen corpus содержит 28 ожидаемых логических таблиц, 6 текущих TABLE blocks и 22 отказа. Все 22 отказа классифицированы; unclassified равен нулю.

Использованы только категории DOC5: region, word ownership, row/column bands, over/under-segmented grid, sparse/empty/unreadable, merged cells, multi-level headers, row groups, continuation, dropped structure и validator dispositions. Safe matrix находится в `docs/stage2/BROKER_REPORTS_DOC5_TABLE_FAILURE_MATRIX.safe.json`.

## 3. Reuse audit

Проверены существующие owners:

- PDF words/lines/bboxes и parser cell inventories;
- neutral-table global boundaries и physical spans;
- exact source-word ownership invariants;
- continuation geometry proposal;
- normalized table projection validator;
- Managed Document block ordering и paragraph de-duplication.

Ни один existing owner не добавляет body-cell span semantics в публичный DOC1. Provider/VLM authority не использовалась.

## 4. Экспериментальная repair и независимый review

Первая локальная repair попыталась нормализовать ruled grids и восстановить repeated-X tables. Независимый агент нашёл два blocking counterexample:

- `real_pdf_4_table_10`: 14x9 вместо 7 логических колонок, неполная header hierarchy и три строки следующего prose внутри TABLE;
- `real_pdf_4_table_12`: 24x8 вместо 5 логических колонок, разорванные `Level 1/2/3` и currency/amount columns.

Он также доказал, что spanning cell сопровождалась synthetic EMPTY placeholders, а общий span затем терялся при materialization в DOC1. Parser-derived gold и связанные DOC5 totals отозваны; экспериментальный код и tests не вошли в Git.

После исправления blocker closure тот же независимый агент дал `APPROVE`.

## 5. Empty, unreadable и merged cells

`EMPTY` и `UNREADABLE` уже являются разными состояниями DOC1. Не хватает третьей независимой связи: coordinate covered by a neighboring span.

Аудит 14 ruled fragments показал 33 physical span cells и минимум 23 body spans в семи логических таблицах:

```text
real_pdf_5_table_01
real_pdf_5_table_03
real_pdf_5_table_04
real_pdf_5_table_05
real_pdf_5_table_06
real_pdf_5_table_07
real_pdf_5_table_11
```

Это headers, group/total rows и continuation fragments. `header_hierarchy.column_start/column_end` покрывает только headers; общего body span поля нет.

## 6. Continuations

Геометрические признаки продолжения доступны: соседние страницы, page edges, одинаковая column model, repeated headers и anchors. Но multi-page таблицы 05 и 06 включают body spans. Создание одной continuation relation не исправляет потерянную cell coverage, поэтому continuation recovery не была повышена до TABLE truth.

## 7. Baseline и все 28 таблиц

Шесть существующих TABLE blocks не изменены и не регрессировали. Все 22 исходных отказа имеют terminal `BLOCKED_UNRECOVERABLE_CRITICAL_TABLE` в рамках текущего goal; семь таблиц имеют прямой DOC1 expressiveness blocker.

Надёжные aggregate rows/cells/empties не публикуются. Предыдущие `337/337` и `2794/2794` повторяли ошибочный parser-derived gold. Закрытый DOC4 content-retention baseline `444/444` остаётся доказанным и не переоткрывается; блокирована только строгая DOC5 table-binding parity.

## 8. UNKNOWN, critical tables и parity

```text
EXPECTED_LOGICAL_TABLES_TOTAL = 28
BASELINE_VALIDATED_TABLE_BLOCKS_TOTAL = 6
FAILED_TABLES_CLASSIFIED_TOTAL = 22
UNCLASSIFIED_FAILED_TABLES_TOTAL = 0
CRITICAL_FINANCIAL_TABLES_WITHOUT_VALIDATED_GRID_TOTAL = 22
DIRECT_DOC1_SPAN_BLOCKER_TABLES_TOTAL = 7
PDF_VS_VIEW_TABLE_SEMANTIC_PARITY = BLOCKED
```

Ни один UNKNOWN не превращён в TABLE ради счётчика. Confirmed experimental mismatches сохранены как safe IDs; invented/dropped totals остаются `null`, потому что независимый full gold не завершён.

## 9. Минимальное изменение следующего контракта

Отдельный operator-authorized goal должен версионировать:

1. `TABLE.cell_spans[]` с row/column ranges, value-cell coordinates, origin и anchors;
2. `COVERED_BY_SPAN` плюс `span_id` для covered placeholders;
3. validator для coverage, overlap, ownership, EMPTY/UNREADABLE и spans;
4. явный DOC3 rendering span semantics;
5. migration, positive и negative tests.

DOC5 не применяет это предложение: `DOC1_SCHEMA_CHANGED = FALSE`.

## 10. Tests и CI

```text
independent review = APPROVE
full local service suite = 2411 passed, 5 pre-existing skipped
new skips = 0
privacy guard = 3 passed
generated bundle exact rebuild = passed
proof schema branch semantics = passed
safe JSON canonical integrity = passed
compileall = passed
git diff --check = passed
GitHub broker-reports-ci run 30737092413 = passed
```

## 11. Delivery и non-change proof

```text
diagnostic implementation commit = 512cd07cb425fda32ef1272d0b4d2e5c10b71f93
diagnostic implementation PR = #261 MERGED
diagnostic implementation merge = feac6765f5acd4b402d312f2efdd68ea93358c08
DOC1 schema changes = 0
DOC3 renderer changes = 0
generated bundle diff = 0
provider calls = 0
product activation = NOT_STARTED
production model qualification = NOT_STARTED
live changes = 0
```

## 12. Terminal blocker

```text
GOAL_STATUS = BLOCKED
LAST_PROVEN_STAGE = FAILURE_CLASSIFICATION_REUSE_AUDIT_AND_DOC1_EXPRESSIVENESS_CHECK
FIRST_FAILURE_POINT = DOC1_TABLE_MATERIALIZATION
AVAILABLE_GEOMETRY = words, bboxes, ruled cells, row order, column boundaries, physical spans
MISSING_EVIDENCE = DOC1 body-cell span relation and covered-coordinate state
WHY_LOGICAL_GRID_CANNOT_BE_PROVEN = EMPTY and covered-by-span collapse to the same null coordinate
MINIMAL_REQUIRED_CONTRACT_CHANGE = versioned body spans plus COVERED_BY_SPAN and DOC3 rendering
NEXT_OPERATOR_ACTION = explicitly authorize a separate DOC1/DOC3 contract revision goal
```
