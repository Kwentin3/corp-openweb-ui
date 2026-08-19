# Broker Reports Metadata Context Visibility v1

Статус: `PROOF-ONLY / PARTIAL`
Goal: `G5.63`
Metadata contract: `1.0.0`
Context policy: `broker_reports_metadata_context_policy_v2`

## Назначение

Контракт проверяет только границу:

```text
Canonical -> metadata context visible to the unchanged LLM adapter
```

Он не меняет metadata meaning, prompt, instruction, proposal schema, validator,
provider/model, deterministic extractor, financial extraction, Gate 4 или
Gate 5.

## Frozen authority

- corpus: `pdf_002`, `pdf_024`, `holdout_a`, `holdout_b`;
- source-truth authority: неизменённый private oracle G5.62;
- oracle facts: `9 / 6 / 3 / 6`, всего `24`;
- Canonical loss: `0`;
- fact types: ровно 11 типов G5.60 `1.0.0`.

Oracle разрешён только после построения context package как измеритель
visibility. Selector не принимает oracle и не использует broker wording,
regex, synonyms или metadata fact types.

## Structural selection v2

Policy включает:

- каждый Canonical `TEXT` node целиком, по его собственным line boundaries;
- каждую structurally small `TABLE` целиком;
- все structural candidates без first-N, page-N, target-N и character slicing.

Pre-existing admission rule `SMALL_TABLE_NONEMPTY_CELLS_MAX = 64` сохранён как
граница между small descriptive table и large table. Новых числовых cutoffs не
добавлено. Large tables не попадают в metadata context; это структурное, а не
semantic решение.

Удалены как selectors:

- первые 24 непустые строки `TEXT_HEAD`;
- первые 16 строк small table;
- обрезка region до 3,000 chars;
- прекращение selection по 96 targets или 32,768 chars.

## Budget authority

Неизменённая модель `gemini-3.5-flash` имеет опубликованный input limit
`1,048,576` tokens. Для frozen replay максимальный фактический input одного
документа составил `63,101` tokens. Поэтому position-based char cutoff не был
технически нужен.

Официальная спецификация проверена 2026-08-15:
https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash

## Visibility proof

Каждый oracle fact считается visible только если после независимого selection:

- target ссылается на тот же Canonical node;
- exact Canonical literal присутствует в model-visible target content;
- для факта найден ровно один context target.

Provider запрещён, пока общий результат не равен `VISIBLE=24`, `INVISIBLE=0`.

## Replay contract

После полного visibility proof разрешён ровно один replay:

- один provider submission на документ;
- тот же model, instruction, contract, schema и validator;
- retry `0`;
- best-of-N `false`;
- manual/raw output repair `false`;
- source stores unchanged.

Rejected validator output остаётся rejected. Raw proposal можно только
диагностически квалифицировать против source и G5.62 oracle без повторного
provider call.

## Partial terminal

G5.63 не объявляет adapter proven, если context visible, но context target не
позволяет однозначную Canonical binding или validator отклоняет output.

Текущий proof локализовал такой gap для whole small-table target с повторёнными
literal values. Его запрещено скрывать output repair, validator weakening или
повторным replay в рамках этого GOAL.
