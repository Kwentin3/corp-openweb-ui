# G5.87 — exhaustive KISS table contract microstand

Дата: 2026-08-17
Режим: inactive qualification-only microstand
Terminal: `KISS_TABLE_CONTRACT_QUALIFICATION_INCOMPLETE_LOCAL_VALIDATOR_ABORT`

## Outcome

Узкий KISS-контракт реализован и локально доказан, но semantic reliability
текущей модели в этом GOAL **не установлена**. Первый development response был
получен, после чего inactive harness остановился в детерминированной role-binding
валидации на `gate3_role_target_text_empty`. Raw semantic response не был записан
до исключения. Повтор таблицы запрещён no-semantic-retry правилом, поэтому
оставшиеся development calls и holdout не выполнялись.

Это не semantic fail модели и не green verdict. Результат — незавершённая
квалификация из-за локального validator orchestration defect.

## Context Bootstrap

- Domain: inactive Gate 3 source-semantic qualification.
- Existing projection owner: `Gate3StructuralChunkFactory.create` и его
  pre-existing Canonical Markdown, row aliases и cell aliases.
- Existing ontology owners:
  `Gate3FinancialLabelDictionaryFactory.create` и
  `Gate3FinancialRolePackFactory.create`.
- Existing provider transport owner:
  `Gate2StructuredModelClientFactory` с Google Gemini profile и
  `models/gemini-3.5-flash`.
- Existing typed target:
  `broker_reports_financial_annotations_v2` и deterministic canonical role-value
  resolver.
- No new product authority, projection, dictionary, role pack, persistence owner,
  SQL schema or runtime bundle was introduced.

## Frozen contract

Один call получает ровно одну существующую Canonical Markdown table-unit и
возвращает каждую pre-existing row alias ровно один раз:

- `CLASSIFIED` — 1..N explicit assertions;
- `NONE` — structural/nonfinancial row, assertions пуст;
- `UNMAPPED` — explicit financial assertion вне текущего словаря, assertions
  пуст.

Model output содержит только `financial_type` и `role -> cell_id`. Literals,
canonical refs, normalized values и пояснения запрещены. Validator детерминированно
проверяет exact row coverage, unknown/duplicate/missing rows, unknown types,
duplicate assertions, allowed roles, unknown cells и same-row binding. Принятые
aliases восстанавливаются в текущую V2-форму; missing roles остаются missing. Второй
role LLM отсутствует.

До первого provider submission были заморожены instruction, dynamic JSON schemas,
exact Markdown requests, aliases, model/profile и корпус:

| Control | Frozen rows |
| --- | ---: |
| explicit wrong tax rows | 105 |
| true dividend rows | 25 |
| existing correct tax rows | 114 |
| structural `NONE` | 12 |
| purchase/disposal/commission/transaction-charge cross-type | 6 |
| untouched other-layout fee-table holdout | 7 |

Другие документы присутствуют в isolated store, но current chunk owner не выдаёт
из них отдельную table-unit без нового projection/partition owner. Поэтому holdout
честно заморожен как другая table family/layout того же документа. Новый owner ради
этого GOAL не создавался.

## Execution accounting

Первая v1 preflight завершилась локальным
`gate2_model_request_invalid`: Google transport shim ожидал старое
`$defs.annotation.target_alias`. Provider submissions: `0`. Семантика, corpus и
instruction не менялись; в v2 добавлен только неиспользуемый compatibility
definition с тем же bare-alias grammar. Fake-completion seam после этого прошёл.

В frozen v2 development run удалённый redacted runtime log подтвердил ровно один
`POST /api/chat/completions` с HTTP `200`. Значит получен один semantic response,
без operational retry. До сохранения raw outcome deterministic resolver обнаружил
binding на пустую canonical cell и поднял
`gate3_role_target_text_empty`.

После abort:

- semantic retry: `0`;
- prompt/schema variants по ответу модели: `0`;
- оставшиеся development calls: `0`;
- holdout calls: `0`;
- VLM calls: `0`;
- active pointer / ArtifactStore mutations: `0`;
- Gate 4 / Gate 5: не запускались.

Validator исправлен в соответствии с frozen правилом `reject binding`: empty-source
binding теперь локально отклоняется и восстанавливается как `missing`. Исправление
покрыто focused test, но не использовалось для rerun в этом GOAL.

## Comparison with current two-pass path

Current two-pass baseline остаётся известным: 105 explicit-tax rows содержали
неверный `DIVIDEND_INCOME`; G5.86 instruction-only replay оставил неверными 79/105
и регрессировал часть tax controls.

KISS candidate нельзя честно сравнить по semantic accuracy: scored outputs `0`,
поскольку единственный response потерян до evidence write. Поэтому не заявляются
ни `105/105 TAX_WITHHELD`, ни preservation controls, ни holdout generalization.

## Verification

- focused contract/validator tests: `11 passed`;
- focused plus adjacent Gate2/Gate3 owner tests: `102 passed`;
- Ruff: passed;
- Python compileall: passed;
- fake canonical provider seam: one request, one terminal semantic response;
- deterministic store tree before/after: exact unchanged;
- product runtime files and generated runtime bundles: unchanged.

## KISS check

Сохранено здравое зерно: один exhaustive JSON на table-unit действительно убирает
provider-owned target discovery и второй role pass. Реализация остаётся двумя
inactive scripts и focused tests, повторно использует существующие owners и не
создаёт framework, parser, schema migration или production route.

## Stop and next allowed GOAL

GOAL закрыт на infrastructure qualification boundary. Следующий допустимый GOAL —
только отдельно разрешённый новый clean run уже исправленного inactive validator:
снова preregister/freeze до provider, один development pass, и только при exact
development success — один untouched holdout pass. Автоматически он не начат.

Safe receipts:

- `BROKER_REPORTS_KISS_TABLE_CONTRACT_G5_87.safe.json`
- `BROKER_REPORTS_KISS_TABLE_CONTRACT_G5_87.closeout.safe.json`

Private exact inputs, aliases, source tables, raw runtime evidence and abort receipt
остаются вне Git в `broker-reports-g5.87-20260817-v2`.
