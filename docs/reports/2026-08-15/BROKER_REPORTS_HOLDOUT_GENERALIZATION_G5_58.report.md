# G5.58 — Holdout Broker Report Generalization Proof

## Terminal

```text
HOLDOUT_GENERALIZATION_PARTIAL

SMALL_DOCUMENT_FINANCIAL_GENERALIZATION_PROVEN
LARGE_DOCUMENT_FINANCIAL_GENERALIZATION_PROVEN
SOURCE_TO_GATE4_FINANCIAL_GENERALIZATION_PROVEN
NO_HOLDOUT_SPECIFIC_SEMANTIC_HACKS

GENERAL_PIPELINE_GAP_LOCALIZED=
Gate3MetadataSourceFactRuntime._metadata_facts / adjacent table label-value pairs
```

Оба заранее замороженных holdout прошли финальный raw PDF → Canonical → Adaptive Context → Gate 3 → Gate 4 replay без retry, best-of-N или ручного ремонта. Финансовый source-fact слой обобщился на обоих документах. Полный terminal не заявлен: существующий consumer-driven metadata owner вернул `0` typed facts для обоих документов, хотя source явно содержит поддерживаемые metadata assertions.

## Freeze и границы экзамена

- Выбор двух source-документов был зафиксирован вне Git до первого pipeline execution.
- Holdout A — компактный 14-page report; Holdout B — большой 49-page report.
- Оба отсутствовали в semantic tuning/debug fixtures; объективная замена не потребовалась.
- Baseline выполнен неизменённым pipeline до первого code change.
- Source проверен визуально на всех страницах; повышенное разрешение использовалось для transaction, commission и corporate-action sections.
- Private source bytes, значения, provider traces, SHA и локальные пути остались вне Git.
- Ни push, ни PR, ни product activation не выполнялись.

## Baseline

| Проверка | Holdout A | Holdout B |
|---|---:|---:|
| Canonical TABLE nodes | 0 | 49 |
| Adaptive contexts | 1 whole-document | 54 structural |
| Gate 4 facts | 14 | 107 |
| Minimum source-present financial assertions lost | 25 | 22 |
| Invented facts | 0 | 0 |
| Unsupported relations | 0 | 0 |

Baseline A потерял 12 физически обнаруженных таблиц до Canonical. Baseline B сохранил таблицы, но объявлял первую data row каждой continuation page заголовком; в semantic результате потерялись 22 явно указанные transaction charges.

## Exact owners и общие fixes

1. `PdfLayoutUnitBuilder`: частично пересекающая границу таблицы line больше не уничтожает весь table candidate; ownership остаётся уникальным и coverage exact.
2. PDF page-text reconciliation: layout partition допускается только для двух узких механических причин при полном layout inventory; остальные partial states fail closed.
3. `NormalizedTableProjection`: reconstructed PDF row признаётся header только при физическом text→typed-value contrast. Native CSV/HTML/XLSX path не изменён.
4. `Gate3StructuralChunkFactory`: header доказанной первой таблицы передаётся continuation tables как context-only; data rows не перекрываются.
5. Type instruction `1.0.2`: один exact target может содержать несколько независимых allowed assertions; detail и aggregate total не reconcile.
6. Dictionary `2.0.1`: общий fee при выплате дохода явно остаётся `COMMISSION` без inferred relation. `2.0.0` сохранён immutable; managed Skill/Tool/manifest пересобраны из owner.

Ни одно исправление не содержит broker name, source hash, account identifier, layout-specific semantic branch или hidden retry.

## Финальный source ↔ machine audit

### Holdout A — compact / whole-document

| Метрика | Результат |
|---|---:|
| Canonical tables | 12 |
| Contexts / max chars | 1 / 17,342 |
| Provider submissions | 2 |
| Gate 4 facts | 39 |
| Purchases / disposals | 9 / 9 |
| Transaction charges | 12 |
| Commission detail / total | 4 / 1 |
| Coupon / dividend assertions | 2 / 2 |
| Financial source-present facts lost | 0 |
| Invented / wrong type / wrong role | 0 / 0 / 0 |
| Duplicate assertions / unsupported relations | 0 / 0 |

`34` facts имеют `role_incomplete`, и это правильный fail-closed результат: source заменяет trade/income dates на grouped marker и не сообщает instrument для aggregate income. Все source-present roles — asset, quantity, unit price, amount и currency — визуально сверены с правильными columns. Missing source values не были придуманы.

Detail commission rows, agent-fee rows и commission total сохранены как независимые source assertions. Trade charges не распределялись и не сверялись с total.

### Holdout B — large / structural chunks

| Метрика | Результат |
|---|---:|
| Canonical tables | 49 |
| Contexts / max chars | 54 / 7,123 |
| Provider submissions | 59 |
| Gate 4 facts / role-complete | 129 / 129 |
| Security purchases / disposals | 35 / 18 |
| Transaction charges | 51 |
| Coupon / dividend assertions | 12 / 12 |
| Commission total | 1 |
| Financial source-present facts lost | 0 |
| Invented / wrong type / wrong role | 0 / 0 / 0 |
| Duplicate assertions / unsupported relations | 0 / 0 |

Canonical дополнительно сохраняет 10 source rows вне текущей ontology: option expirations и FX operations. Они не были ошибочно превращены в security purchases/disposals. REPO rows также не получили inferred security relations. Это не financial fact loss: named consumer для этих source meanings отсутствует.

## Metadata gap

Visual source truth содержит поддерживаемые metadata assertions:

- A: client name, client identifier, statement period;
- B: account identifier, statement period.

`Gate3MetadataSourceFactRuntimeFactory.create().collect(...)` вернул `0` typed metadata facts для A и B. Canonical значения сохранил, но `_metadata_facts` применяет regex к каждой table cell отдельно. Label и value в соседних ячейках поэтому никогда не образуют один доказанный assertion.

Класс расхождения: consumer-owned metadata extraction gap после корректного Canonical, не financial labeling и не Gate 4 tax logic. Исправление не выполнено: пять разрешённых loops исчерпаны, а новый metadata binding contract требует отдельного узкого proof.

## Architecture и KISS

- Gate 2 остаётся owner source structure.
- Gate 3 остаётся owner source meaning.
- Gate 4 материализует normalized source facts и не вызывает provider.
- Gate 5 не читает Canonical и не вызывает source-semantic provider.
- Projection changes: `0`.
- Gate 4 provider calls: `0`.
- Gate 5 Canonical reads: `0`.
- Gate 5 source-semantic provider calls: `0`.
- Visual inspection остался qualification-only и не стал runtime dependency.
- `FULL_REPROCESSING_RICH_CANONICAL_COST` оставлен вне scope.

## Verification

- Generated OpenWebUI pipe bundles: passed.
- Managed financial assets exact check: passed.
- Targeted Gate 2/Adaptive/Gate 3/Gate 4/architecture regression: `214 passed`.
- Полный service suite не получил terminal за 15 минут: global timeout завершился при stdout flush, без зафиксированного assertion failure. Это не считается PASS.
- Более широкий 63-file Gate 2→4/PDF/Canonical/architecture shard также не получил terminal за 10 минут по той же bounded границе. Это не считается PASS.

Green targeted tests не подменяют source audit; terminal основан на финальных single-attempt holdout runs и визуальной сверке.

## Следующий разрешённый GOAL

Только отдельный узкий `NARROW_METADATA_LABEL_VALUE_ROW_BINDING_PROOF`: научить существующий metadata owner доказанно читать adjacent label/value cells без generic extraction, broker-specific правил или semantic inference; затем replay обоих holdout и metadata regressions.

Safe receipt: `BROKER_REPORTS_HOLDOUT_GENERALIZATION_G5_58.receipt.safe.json`.
