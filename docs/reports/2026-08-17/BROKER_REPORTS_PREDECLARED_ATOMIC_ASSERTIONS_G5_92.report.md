# G5.92 — Predeclared Atomic Source Assertions

Date: 2026-08-17
Terminal: `PREDECLARED_ASSERTION_SEMANTIC_RELIABILITY_INSUFFICIENT`
Activation: `0`

## Outcome

Гипотеза отвергнута. Deterministic enumeration действительно полностью
убрала выбор source target со стороны модели, но semantic fidelity не выросла:
candidate распознал только `26/105` tax-adjustment rows против `53/105` у
current whole-table pass. Остальные `79/105` candidate снова назвал
`DIVIDEND_INCOME`.

При этом соседние классы не регрессировали: ordinary withholding `113/113`,
true dividends `25/25`, structural/unmapped `12/12`, purchase/disposal plus
transaction-charge controls `4/4`. Значит first divergence находится не в
Gate 2 refs, enumeration, target restoration или validator, а в semantic
classification заранее указанного row assertion.

## Architecture bootstrap

Maintained authorities прочитаны в порядке Pipeline Gates -> Architecture
Authorities -> Gate 3 contracts -> Dictionary/Role Pack -> Gate 4 Fact v2.
Current pass-1 owner — `Gate3BoundedLabelingFactory`; structural targets и
aliases принадлежат `Gate3ProjectionFactory` / `Gate3StructuralChunkFactory`;
provider route — `Gate2StructuredModelClientFactory`. Candidate добавлен как
один inactive метод того же pass-1 owner, а не как второй classifier.

Current production defaults не изменены:

- Dictionary `2.0.1`;
- Role Pack `3.0.0`;
- current chunk-batch/role/persistence workflow;
- Gate 4/5 consumers.

Generated OpenWebUI bundles были только локально детерминированно пересобраны
для closed-world parity с maintained source/resources; stage deployment,
runtime publication и product activation не выполнялись.

Dictionary `2.1.0` с минимальным `TAX_ADJUSTMENT` использован только по exact
explicit version в qualification. `source_wording` не добавлялась: отдельного
consumer для неё в этом GOAL нет.

## Exact candidate

Код перечисляет все существующие `table_row` targets одного frozen chunk.
Existing bare alias одновременно служит `assertion_id` и
`source_target_ref`; новый locator не появляется. Модель получает batch из
exact local row text плюс shared structural context и возвращает только
financial types или `UNMAPPED` для каждого заранее объявленного ID.

Strict validation требует exact ordered coverage. Development доказал:

- assertions `303/303`;
- unknown IDs `0`;
- duplicate IDs `0`;
- invented source objects `0`;
- inferred relations `0`;
- role/value extraction `0`;
- tax calculation `0`.

Массив labels на одном assertion сохранён только ради уже существующей Gate 3
семантики, где один exact row может прямо сообщать purchase/disposal и
transaction charge. Это не возвращает target discovery и не затрагивает role
pass.

## Frozen execution

До первого semantic response были заморожены 7 development batches / 303
assertions и отдельный holdout batch / 10 assertions. Instruction, Dictionary,
model, provider, response schema и exact request hashes были зафиксированы.

Первый infrastructure cycle сделал 7 submissions, но получил 7 одинаковых
pre-semantic `gate2_model_schema_response_format_rejected`. Raw semantic output
не существовал. Исправлена только provider-compatible запись JSON Schema до
уже доказанной Gate 3 формы; instruction, assertions, Dictionary, model и
semantic hypothesis остались прежними. Failed plan/replay сохранены по SHA.

Второй cycle получил 7/7 terminal responses и 7/7 strict-valid batches:

| Measure | Whole-table baseline | Predeclared assertions |
| --- | ---: | ---: |
| tax adjustment correct | 53/105 | 26/105 |
| wrong tax -> dividend | 52 | 79 |
| ordinary withholding | 113/113 | 113/113 |
| true dividends | 25/25 | 25/25 |
| structural/unmapped | 12/12 | 12/12 |
| cross-type | not in G5.91 replay | 4/4 |
| provider calls | 6 | 7 |
| total tokens | 92,570 | 105,151 |
| summed latency | 196,500 ms | 182,280 ms |

Первый semantic divergence агрегированно однозначен: все 79 failures —
`DIVIDEND_INCOME`; они сосредоточены в four frozen chunks, тогда как exact
target accounting остаётся зелёным. Literal/broker rules из результата не
выводились, original PDF не использовался для production repair.

## Holdout and stop

Holdout был заранее заморожен, но не открыт. Его policy разрешала единственный
вызов только после полного development proof. Development gate не прошёл,
поэтому запуск holdout дал бы новый semantic sample после уже отрицательного
verdict и нарушил бы fail-fast/untouched intent. Holdout provider calls: `0`.

Никаких prompt variants, другой модели, best-of-N, semantic retry, manual
repair или literal-specific rule не применялось. Infrastructure resubmission
не содержал semantic response и не менял semantic payload.

## KISS and final verdict

Candidate проще current pass-1 по ownership цели: runtime перечисляет targets,
LLM только классифицирует их. Но operationally он требует полный ответ для
каждой строки, использует 7 вместо 6 calls и 105,151 вместо 92,570 tokens, а
главную ошибку увеличивает с 52 до 79. Упрощение target selection не устраняет
semantic ambiguity и не оправдывает новую active branch.

Terminal:

```text
PREDECLARED_ASSERTION_SEMANTIC_RELIABILITY_INSUFFICIENT
```

Candidate не активировать и не развивать внутри G5.92. Следующий GOAL не
следует автоматически: нужна отдельная новая гипотеза о semantic evidence,
если пользователь решит продолжить. Gate 2, role machinery, Gate 4, Gate 5,
Projection, tax ontology и production route остаются без изменений.

Safe receipts:

- `BROKER_REPORTS_PREDECLARED_ATOMIC_ASSERTIONS_G5_92.DEVELOPMENT.safe.json`;
- `BROKER_REPORTS_PREDECLARED_ATOMIC_ASSERTIONS_G5_92.REJECTED.safe.json`.

## Verification

- focused + adjacent Gate 3/provider/architecture/bundle suite: `118 passed`;
- initial adjacent run: `115 passed, 1 failed` на stale generated-bundle
  parity; после deterministic rebuild тот же boundary зелёный;
- new candidate focused seam: `27 passed`;
- Ruff and `py_compile`: passed;
- exact package/contract schema bytes and SHA-256: passed;
- current Dictionary/Role Pack defaults: `2.0.1` / `3.0.0`;
- holdout replay absent; private/customer bytes remain outside Git.
