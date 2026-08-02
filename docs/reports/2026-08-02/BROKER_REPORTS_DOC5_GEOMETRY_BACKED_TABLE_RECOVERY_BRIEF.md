# Broker Reports DOC5 Geometry-Backed Table Recovery Brief

Status: `BLOCKED_DOC1_BODY_CELL_SPAN_UNREPRESENTABLE`

Effective date: 2026-08-02

DOC5 классифицировал все 22 table failures, но не может честно получить `PASSED` при неизменённом Managed Document v1.

Семь критических логических таблиц содержат body cells, покрывающие несколько колонок. PDF geometry это доказывает, а DOC1 умеет хранить span range только для header entries. В обычных rows/cell annotations покрытая позиция неотличима от `EMPTY`.

Первая recovery-попытка была отозвана после независимого review: два real-PDF counterexample дали неверные logical columns, header binding и prose boundary. После перехода к fail-closed blocker closure независимый verdict — `APPROVE`.

```text
EXPECTED_LOGICAL_TABLES_TOTAL = 28
BASELINE_VALIDATED_TABLE_BLOCKS_TOTAL = 6
FAILED_TABLES_CLASSIFIED_TOTAL = 22
UNCLASSIFIED_FAILED_TABLES_TOTAL = 0
DIRECT_DOC1_SPAN_BLOCKER_TABLES_TOTAL = 7
PDF_VS_VIEW_TABLE_SEMANTIC_PARITY = BLOCKED
DOC1_SCHEMA_CHANGED = FALSE
PRODUCT_ACTIVATION = NOT_STARTED
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
GOAL_STATUS = BLOCKED
```

Следующее действие требует нового явного разрешения: версионировать body-cell spans, `COVERED_BY_SPAN` и соответствующий DOC3 rendering. Текущий goal этого изменения не разрешает.
