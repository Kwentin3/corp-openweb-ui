# Broker Reports DOC5 Geometry-Backed Table Recovery Decision v1

Дата решения: 2026-08-02
Статус: `BLOCKED`, inactive/offline only

## Простыми словами

PDF похож на бумажную таблицу с объединёнными клетками. В исходной геометрии видно, что одна итоговая ячейка занимает несколько колонок. Но текущий DOC1 умеет записать только прямоугольный массив `value/null` и состояние обычной клетки. Он не умеет сказать: «эта позиция не пустая — её покрывает объединённая ячейка слева».

Если записать покрытые позиции как `EMPTY`, получится ложь. Если отбросить span, потеряется связь значения с диапазоном колонок. DOC5 §15 требует в такой ситуации остановиться и предложить минимальное изменение контракта. Поэтому экспериментальный `PASSED` отозван, а recovery-код не доставляется.

## Последняя доказанная стадия

```text
LAST_PROVEN_STAGE = FAILURE_CLASSIFICATION_REUSE_AUDIT_AND_DOC1_EXPRESSIVENESS_CHECK
AFFECTED_TABLES = real_pdf_5_table_01, 03, 04, 05, 06, 07, 11
FIRST_FAILURE_POINT = DOC1_TABLE_MATERIALIZATION
AVAILABLE_GEOMETRY = words, bboxes, ruled cells, row order, column boundaries, physical spans
MISSING_EVIDENCE = DOC1 body-cell span relation and covered-coordinate state
WHY_LOGICAL_GRID_CANNOT_BE_PROVEN = EMPTY and covered-by-span collapse to the same null cell
NEXT_OPERATOR_ACTION = authorize a separate DOC1 contract revision goal
```

## Failure taxonomy и матрица

Все 22 исходных отказа классифицированы; `UNCLASSIFIED_FAILED_TABLES_TOTAL = 0`. Матрица находится в `BROKER_REPORTS_DOC5_TABLE_FAILURE_MATRIX.safe.json`.

Основные классы:

- неверный или отсутствующий table region;
- over/under-segmented repeated-X grid;
- sparse rows и row groups;
- многоуровневые headers;
- merged body cells;
- empty versus covered coordinate;
- continuation и repeated header;
- numeric prose, ошибочно захваченный как TABLE;
- currency/header tokens, ошибочно разделённые на самостоятельные колонки.

Семь логических таблиц имеют прямой DOC1 blocker. Шесть входят в frozen failure matrix; `real_pdf_5_table_05` дополнительно выявлена как неполная baseline-таблица: её принятый первый фрагмент имеет продолжение на следующей странице, где итоговая строка содержит body span.

## Проверенные старые механизмы и reuse

Проверены и признаны пригодными как proposal/evidence layers:

- `pdf_layout.py` и `pdf_text_layer.py` — words, lines, bbox и parser cells;
- `broker_pdf_neutral_tables.py` — идея global boundaries и physical spans;
- `pdf_hybrid_compaction.py` — exact source-word ownership invariants;
- `pdf_continuation_discovery.py` — adjacent-page geometry proposal;
- `table_projection.py` — существующий fail-closed normalized projection validator;
- `ManagedDocumentBlockMaterializer` — порядок блоков и защита от paragraph duplication.

Ни один из них не добавляет отсутствующую публичную семантику body span в DOC1. История не содержит готового неизменяющего DOC1 решения. Provider/VLM route отвергнут как запрещённый источник истины.

## Что показал независимый review

Независимый агент вернул `REQUEST_CHANGES` и доказал, что первый экспериментальный proof был круговым:

- `real_pdf_4_table_10`: экспериментальная сетка стала 14x9 вместо 7 логических колонок; три строки последующего prose попали внутрь TABLE; header hierarchy неполна;
- `real_pdf_4_table_12`: экспериментальная сетка стала 24x8 вместо 5 логических колонок; `Level 1/2/3` и currency signs были разорваны на отдельные колонки;
- spanning physical cell одновременно сопровождалась synthetic `EMPTY` cells в покрытом диапазоне;
- общий body span исчезал при materialization в DOC1;
- независимого per-table PDF gold не было: прежний gold повторял размеры parser output.

Поэтому отозваны DOC5 post-recovery утверждения `337/337`, `2794/2794`, strict table-binding recheck `444/444` и `critical mismatches = 0`. Закрытый DOC4 baseline `SOURCE_LITERAL_MEANINGS_PRESERVED = 444/444` остаётся доказанным и не переоткрывается. Экспериментальные код и tests удалены до PR.

## Доказанный span blocker

Структурный аудит 14 ruled fragments реального `real_pdf_5` показал body spans в семи логических таблицах. Это не только визуальные шапки:

- итоговые строки занимают несколько колонок;
- групповые строки занимают диапазон колонок;
- один многостраничный фрагмент завершается итоговой spanning cell;
- continuation-фрагменты сохраняют разные page anchors.

DOC1 `header_hierarchy` умеет хранить `column_start/column_end` только для header entries. `rows`, `row_groups`, `row_markers` и `cell_annotations` не имеют общего body-cell span identifier или covered-coordinate relation. Следовательно, блокер конкретный и относится к разрешённому DOC5 §37 пункту 3.

## Минимальное предложение изменения контракта

Отдельный будущий goal должен предложить, проверить и версионировать минимум:

1. `TABLE.cell_spans[]` с `span_id`, `row_start`, `row_end`, `column_start`, `column_end`, value-cell coordinates, `origin` и source anchors.
2. Для покрытых прямоугольных placeholders — состояние `COVERED_BY_SPAN` и `span_id`; оно не равно `EMPTY`.
3. Инвариант: каждый logical coordinate принадлежит ровно одной обычной клетке или одному span; пересечения запрещены.
4. DOC3 renderer должен явно выводить диапазон span, не превращая покрытые координаты в пустые значения.
5. Миграционные и negative tests для headers, body totals, row spans, column spans, EMPTY, UNREADABLE и overlap.

Это предложение не применяется в DOC5: `DOC1_SCHEMA_CHANGED = FALSE`.

## Текущий corpus result

```text
EXPECTED_LOGICAL_TABLES_TOTAL = 28
BASELINE_VALIDATED_TABLE_BLOCKS_TOTAL = 6
FAILED_TABLES_CLASSIFIED_TOTAL = 22
UNCLASSIFIED_FAILED_TABLES_TOTAL = 0
DIRECT_DOC1_SPAN_BLOCKER_TABLES_TOTAL = 7
PDF_VS_VIEW_TABLE_SEMANTIC_PARITY = BLOCKED
DOC5_GEOMETRY_BACKED_TABLE_RECOVERY = BLOCKED
```

Надёжные totals rows/cells/empties не публикуются: независимый review опроверг parser-derived gold, а DOC5 запрещает заменять неизвестное нулём.

## Non-change proof

- DOC1 schema change total: 0.
- DOC3 renderer change total: 0.
- Recovery implementation delivered total: 0.
- Generated bundle diff: 0.
- Semantic Pack changes total: 0.
- Gate 2/3/4 product route changes total: 0.
- Provider calls total: 0.
- Prompt, valve и admission changes total: 0.
- Product activation: not started.
- Production model qualification: not started.
- Live changes total: 0.

## Решение

`DOC5_GEOMETRY_BACKED_TABLE_RECOVERY = BLOCKED`.

Блокер нельзя обходить synthetic EMPTY, ложным TABLE или скрытием loss ledger. Возобновление возможно только после явного нового решения о версии DOC1/DOC3; текущий goal такого разрешения не даёт.
