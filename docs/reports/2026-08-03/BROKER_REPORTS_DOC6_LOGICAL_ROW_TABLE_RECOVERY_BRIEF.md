# Broker Reports DOC6 Logical-Row Table Recovery Brief

Status: `PASSED_INACTIVE`

Effective date: 2026-08-03

DOC6 заменил обязательную прямоугольную сетку канонической моделью `TABLE = ordered logical rows`. У каждой строки есть порядок, роль, вложенность, optional parent и ordered entries; logical columns и geometry добавляются только там, где они доказаны.

```text
tables = 28/28
rows = 357/357
entries = 2338/2338
continued tables = 2
UNKNOWN row roles = 1 noncritical
unresolved column bindings = 0
unresolved row parents = 1 noncritical
terminal critical mismatches = 0
raw base-gold mismatches = 29 = 27 entry surfaces + 2 header paths
sealed errata = 27 resolved, 0 unresolved
PDF → Managed v2 = PASSED after adjudication
Managed v2 → View v2 = PASSED
PDF → View v2 = PASSED after adjudication
```

Managed Document v1, product route и generated bundles не изменены. Provider calls: 0. Production model qualification и product activation не начинались.

```text
PRODUCTION_MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```

Полный отчёт: [BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.report.md](BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.report.md).

Safe receipt: [BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.receipt.safe.json](BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.receipt.safe.json).
