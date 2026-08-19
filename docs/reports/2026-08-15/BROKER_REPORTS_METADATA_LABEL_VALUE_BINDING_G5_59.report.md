# G5.59 — Metadata Label→Value Binding Proof

## Terminal

```text
METADATA_LABEL_VALUE_BINDING_PARTIAL

ADJACENT_TWO_CELL_BINDING_PROVEN
INVENTED_METADATA_FACTS_ZERO
WRONG_METADATA_BINDINGS_ZERO
DUPLICATE_METADATA_ASSERTIONS_ZERO
FINANCIAL_HOLDOUT_GENERALIZATION_PRESERVED

NOT PROVEN:
HOLDOUT_A_SUPPORTED_METADATA_COMPLETE
HOLDOUT_B_SUPPORTED_METADATA_COMPLETE
SOURCE_TO_GATE4_GENERALIZATION_PROVEN
```

Минимальный fail-closed binding реализован и доказан, но полный ожидаемый terminal не заявлен. Обязательная визуальная проверка показала, что четыре из пяти ранее ожидавшихся assertions не являются поддерживаемыми соседними `LABEL | VALUE` cells по замороженному контракту G5.59.

## Source truth и Canonical

Source pages открыты и проверены глазами; customer literals, private paths, hashes и изображения остались вне Git.

| Safe assertion alias | Source structure | Canonical structure | Current vocabulary | Result |
|---|---|---|---|---|
| A / client name | two cells, same row | two cells, same row | label literal unsupported | no fact |
| A / client identifier | two cells, same row | two cells, same row | supported | one typed fact |
| A / statement period | page text header | one TEXT node, not table cells | type exists, required table structure absent | no fact |
| B / account identifier | column header plus three data rows | four-column TABLE, not same-row label/value | type exists, required table structure absent | no fact |
| B / statement period | page text header | one TEXT node, not table cells | required table structure absent | no fact |

Gate 2 сохранил source structure корректно. `SOURCE_STRUCTURE_LOSS` не обнаружен; Gate 2 не менялся.

Первый неправильный owner для единственной доказанной adjacent pair до исправления: `Gate3MetadataSourceFactRuntime._metadata_facts`, который перебирал TABLE cells по одной.

## Реализованный contract

Binding добавлен в существующий metadata owner, без нового extractor или vocabulary:

- та же таблица и та же row;
- ровно две structural cells в row;
- соседние column coordinates;
- обе cells непустые;
- merged cells и duplicate coordinates fail closed;
- type определяется только существующим `_PATTERNS` vocabulary;
- match обязан начаться в label cell, а value group — в соседней value cell;
- source binding хранит отдельные label/value field paths и объединённые Canonical source refs.

Реализация: `gate3_metadata_source_facts.py:225`, `:282`, `:338`. Factory route сохранён: `Gate3MetadataSourceFactRuntimeFactory.create` (`:138`).

Не добавлялись broker name, page number, fixed column, source hash, customer literal, value-shape inference или vertical header→row semantics.

## Holdout replay

Replay выполнен через существующие factories над замороженными G5.58 Canonical/store artifacts, без provider call, retry, best-of-N или ручного ремонта.

| Проверка | Holdout A | Holdout B |
|---|---:|---:|
| Typed metadata facts | 1 | 0 |
| Supported adjacent pairs missed | 0 | 0 |
| Invented facts | 0 | 0 |
| Wrong bindings | 0 | 0 |
| Duplicate assertions | 0 | 0 |
| Gate 4 financial facts | 39 | 129 |
| Financial fact set exact to frozen G5.58 result | yes | yes |

Опубликованный A fact проведён до конкретных label cell, value cell, table node и source refs. B корректно остаётся пустым: разрешённой adjacent pair в source нет.

## Architecture boundary

Текущая штатная композиция в `gate5_evidence_intake.py:23-26,60-64` читает metadata через Gate 3 metadata factory и financial facts через Gate 4 financial factory. Gate 4 не является owner metadata materialization. Поэтому finish item «Gate 4 получает typed metadata» нельзя честно объявить выполненным без отдельного изменения архитектурного контракта; G5.59 такого изменения не разрешает.

Gate 5 не получил `LABEL | VALUE` logic. Финансовый owner, Gate 4 materialization и projection не менялись.

## Negative proof

Новые tests проверяют observable output самого `_metadata_facts`, без mock системной логики:

- supported label + adjacent value;
- значение, похожее на period/account, без supported label;
- empty label/value и запрет перехода в следующую row;
- ambiguous three-cell row;
- merged row;
- multi-column account/financial table;
- запрет брать value из самой label cell для adjacent binding.

Test isolation: каждый test создаёт новый in-memory Canonical artifact dictionary. Необратимая boundary отсутствует; replay и tests read-only, terminal outcome — возвращённый typed fact set.

## Verification

PowerShell, explicit `$env:PYTHONPATH='.'`:

- metadata + cross-gate: `23 passed`;
- Canonical/Gate 2 + Gate 3/4 + intake + architecture: `103 passed`;
- G5.58 financial regression slice + metadata: `148 passed`;
- post-format union of all listed slices: `233 passed`;
- scoped trailing-whitespace check over all four G5.59 files: passed;
- assertion failures: none; runners executed tests and reached terminal.

Global suite не запускался: scoped regressions и exact holdout financial hashes дали terminal evidence; глобальный timeout G5.58 не объявляется PASS задним числом.

## KISS и stop

- Новый engine/module/schema/dictionary: `0`.
- Изменён один существующий metadata owner и добавлен один focused test file.
- Vocabulary expansion: `0`.
- Broker-specific branches: `0`.
- Gate 2/financial/Gate 4/Gate 5 changes: `0`.
- Visual inspection в runtime: `0`.

Полное закрытие «raw broker document → normalized source artifact» на пяти заявленных metadata assertions не доказано. Продолжать extraction без нового контракта запрещено.

## Следующий разрешённый шаг

Только явное решение владельца требований: либо принять current consumer contract, где G5.59 adjacent metadata coverage равна `A=1, B=0`, либо отдельно авторизовать versioned расширение поддерживаемых source structures/vocabulary для page-header period, vertical header→rows account identifiers и отсутствующей client-name label. Это не входит в G5.59.

Safe receipt: `BROKER_REPORTS_METADATA_LABEL_VALUE_BINDING_G5_59.receipt.safe.json`.
