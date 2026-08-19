# G5.62 — Canonical Metadata Preservation & Source-Truth Oracle Requalification

Дата: 2026-08-15
Статус: `CLOSED`

## Terminal

```text
METADATA_SOURCE_TRUTH_ORACLE_REQUALIFIED
CANONICAL_METADATA_PRESERVATION_PROVEN
FROZEN_CORPUS_CONTRACT_METADATA_CANONICAL_LOSS_ZERO
FALSE_ORACLE_BINDINGS_REMOVED
ORACLE_COVERAGE_REQUALIFIED
LLM_METADATA_ADAPTER_UNCHANGED
FINANCIAL_GENERALIZATION_PRESERVED
```

Четыре frozen PDF заново квалифицированы глазами только по 11 fact types
контракта G5.60 `1.0.0`. Новый private oracle построен из визуального source
truth и Canonical provenance, без authority старого oracle, extractor или LLM.
Provider calls и LLM replay: `0`.

## Итог source truth

| Case | Source assertions | Canonical-bound | Losses | Qualified pages |
|---|---:|---:|---:|---|
| `pdf_002` | 9 | 9 | 0 | 1, 4, 12, 17 |
| `pdf_024` | 6 | 6 | 0 | 1, 6 |
| `holdout_a` | 3 | 3 | 0 | 1 |
| `holdout_b` | 6 | 6 | 0 | 1 |
| **Total** | **24** | **24** | **0** | — |

Множественность сохранена: в `pdf_002` остались два независимых account
assertions и три period assertions; в `holdout_b` — три независимых account
assertions. Reconciliation и выбор «главного» значения не выполнялись.

На frozen corpus source действительно не подтвердил четыре типа:
`PERSON_BIRTH_DATE`, `TAXPAYER_TAX_IDENTIFIER`, `PERSON_CITIZENSHIP` и
`DOCUMENT_NUMBER`. Они не заполнены догадкой. Поля вне контракта игнорировались
oracle, даже если Canonical сохранял исходный текст.

## Переквалификация pdf_024

Предыдущая гипотеза `UPSTREAM_CANONICAL_METADATA_VALUE_LOSS` опровергнута
прямой проверкой. Period, client и agreement присутствуют на source page 1 и
присутствуют в том же page-bound Canonical `TEXT` node с exact literals.

Причина прежней невидимости локализована downstream: G5.61 `TEXT_HEAD`
выбирает первые 24 непустые строки, а порядок text extraction поместил эти
значения позже. Это `CONTEXT_SELECTION_VISIBILITY_LOSS`, не физическая потеря
Canonical. Поэтому Gate 2 fix не требовался и запрещённый G5.61 adapter/context
policy не изменялся.

## Старый oracle

Полный private ledger заново классифицирует каждую запись и каждое добавление:

- `18 CORRECT`;
- `3 FALSE_BINDING` — все в `pdf_024`;
- `6 MISSING_FROM_ORACLE`: один account в `pdf_002`, четыре assertions в
  `pdf_024` и party assertion в `holdout_b`.

Две отдельные negative qualifications сохранены как смысловые границы:

- signer на `pdf_024` page 6 не является автоматически subject party;
- client code в `holdout_a` не является автоматически account identifier.

Ни старый oracle, ни прежний LLM output не использовались для ремонта значений.
Приватный ledger, values, PDF, screenshots, source paths и document hashes не
попали в Git.

## Financial regression

Replay выполнен на private копиях stores через
`Gate4FinancialCaseRuntimeFactory.create().rebuild_case(...)`:

- `holdout_a`: `39` facts, exact frozen canonical JSON equality `true`;
- `holdout_b`: `129` facts, exact frozen canonical JSON equality `true`;
- оба status: `CASE_COMPLETE_FOR_CURRENT_INPUT_SET`;
- source stores не изменялись.

## Неизменность запрещённых owners

До и после G5.62 совпали SHA-256 для:

- LLM metadata adapter;
- G5.60 deterministic metadata extractor;
- Gate 2 model client, request builder и provider adapter.

Instruction, prompt, contract, context policy, proposal schema, model/provider,
validator semantics, financial pipeline, Gate 4 и Gate 5 не менялись. Новые
broker rules, fixed page/column rules, regex vocabulary и persistence: `0`.

## Verification

- новый sterile oracle guard: `4 passed`;
- Canonical, pipeline contract, G5.60 metadata, unchanged LLM adapter, Gate 4,
  cross-gate architecture и KT1 suite: `148 passed`, `0 failed`;
- пять forbidden-owner hashes: exact `true`;
- provider calls: `0`;
- LLM replay: `false`.

## KISS и STOP

Production code не менялся. Добавлены один offline requalification script, один
узкий guard test, один proof contract и safe closeout. Отдельный Canonical fix
не создан, потому что доказанного Canonical loss нет.

G5.62 закрыт. G5.63 не запускался и этим отчётом не разрешается автоматически.
