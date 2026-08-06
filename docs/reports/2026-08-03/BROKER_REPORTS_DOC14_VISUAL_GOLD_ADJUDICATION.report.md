# DOC14 — post-hoc visual-gold adjudication

Дата: 2026-08-03  
Статус: дополнение к frozen raw result; исходный verdict не переименован

## Вывод

- Исходный заранее заданный gate: **`NOT_CONFIRMED`**.
- После отдельной проверки только спорных значений по заранее sealed visual gold: **`PROMISING`**.
- Дешёвый кандидат: **`google_flash_lite`**.
- Референсный кандидат: **`anthropic_opus`**.

Raw scorer считал «invented» любое значение, отсутствующее в parser text. Для каждой модели таких значений было 5; все 5/5 подтверждены visual gold, реально неподтверждённых — 0. Это не меняет остальные метрики и не стирает исходный raw verdict.

| Модель | Raw source-text gap | Есть в visual gold | Нет в обоих источниках | Adjudicated gate | Причина FAIL |
|---|---:|---:|---:|---|---|
| gpt-5.4-mini-2026-03-17 | 5 | 5 | 0 | FAIL | ROW_ASSOCIATION_BELOW_95_PERCENT, EXACT_TABLE_RATE_BELOW_50_PERCENT |
| models/gemini-3.5-flash-lite | 5 | 5 | 0 | PASS | — |
| claude-haiku-4-5-20251001 | 5 | 5 | 0 | FAIL | CRITICAL_VALUE_RECALL_BELOW_99_PERCENT, ROW_ASSOCIATION_BELOW_95_PERCENT, COLUMN_ASSOCIATION_BELOW_95_PERCENT, EXACT_TABLE_RATE_BELOW_50_PERCENT |
| claude-opus-5 | 5 | 5 | 0 | PASS | — |

## Граница утверждения

Adjudication выполнена после вызовов и потому публикуется отдельно. Она исправляет семантику одного diagnostic counter, но не является новым независимым holdout и не активирует product pipeline.
