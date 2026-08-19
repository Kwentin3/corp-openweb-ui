# G5.60 — Minimal Person & Document Identity Contract

## Terminal

```text
MINIMAL_PERSON_DOCUMENT_METADATA_CONTRACT_PROVEN
MINIMAL_METADATA_CONTRACT_PROVEN_WITH_SOURCE_ABSENCE

PERSON_IDENTITY_SOURCE_FACTS_PROVEN_FOR_AVAILABLE_SOURCE
DOCUMENT_IDENTITY_SOURCE_FACTS_PROVEN_FOR_AVAILABLE_SOURCE
DOCUMENT_PERIOD_SOURCE_FACT_PROVEN
ISSUER_SOURCE_FACT_PROVEN
ACCOUNT_IDENTITY_SOURCE_FACTS_PROVEN

TAX_RESIDENCY_BOUNDARY_PRESERVED
NO_GENERIC_METADATA_EXTRACTION
NO_SYNTHETIC_SUPPORT_ADDED
FINANCIAL_GENERALIZATION_PRESERVED
```

G5.60 закрыт разрешённым source-absence terminal. Минимальная карточка заморожена до coding в `BROKER_REPORTS_MINIMAL_PERSON_DOCUMENT_METADATA.v1.md`; после proof metadata-направление остановлено до новой user story и named consumer.

## Замороженный contract и source accounting

Дешёвый corpus scan проверил 31 физический PDF / 29 уникальных документов. LLM для поиска или metadata extraction не вызывался. Реальные примеры квалифицированы глазами; customer values, source bytes, изображения, локальные пути и private hashes в Git не попали.

| Contract field | Physical fact type | Corpus result | Production support |
|---|---|---|---|
| `FULL_NAME` | `PARTY_NAME` | `REAL_SOURCE_EXAMPLE` | да: explicit label/value |
| `BIRTH_DATE` | `PERSON_BIRTH_DATE` | `NO_REAL_SOURCE_EXAMPLE` | нет |
| `TAX_IDENTIFIER / INN` | `TAXPAYER_TAX_IDENTIFIER` | `NO_REAL_SOURCE_EXAMPLE` для человека | нет; ИНН организаций не повышается до person identity |
| `CITIZENSHIP` | `PERSON_CITIZENSHIP` | `NO_REAL_SOURCE_EXAMPLE` | нет |
| `DOCUMENT_TYPE` | `DOCUMENT_TYPE` | `REAL_SOURCE_EXAMPLE` | да: явный document title |
| `DOCUMENT_NUMBER` | `DOCUMENT_NUMBER` | `NO_REAL_SOURCE_EXAMPLE` текущего документа | нет; номера паспорта, договора и операций не подменяют его |
| `DOCUMENT_DATE` | `DOCUMENT_DATE` | `REAL_SOURCE_EXAMPLE` | да: явная дата формирования/создания/составления отчёта |
| `STATEMENT_PERIOD` | `STATEMENT_PERIOD` | `REAL_SOURCE_EXAMPLE` | да: обе source-backed границы |
| `ISSUER / BROKER` | `BROKER_LEGAL_NAME` | `REAL_SOURCE_EXAMPLE` | да: только явное `Брокер:` / `Broker:` |
| `ACCOUNT_IDENTIFIER` | `ACCOUNT_IDENTIFIER` | `REAL_SOURCE_EXAMPLE` | да: label/value и unambiguous header→values |
| `CONTRACT_IDENTIFIER` | `ACCOUNT_CONTRACT_IDENTIFIER` | `REAL_SOURCE_EXAMPLE` | да: явный договор/генеральное соглашение |

Для четырёх source-absence fields production patterns не добавлены. Синтетические fixtures только доказывают negative boundary; они не создают фиктивную production support.

## Visual и Canonical qualification

Safe aliases реальных representative examples:

| Alias | Source truth | Canonical result | Использование |
|---|---|---|---|
| `pdf_002` | тип, issuer label, client label, account label, document date, три самостоятельных section periods | явные TEXT assertions сохранены; спорная разорванная строка периода не использована | Structure B |
| `pdf_024` | тип, client, account, contract, document date | явные TEXT assertions сохранены | Structure B |
| G5.58 holdout A | client label/value и header period | связь client label/value и header text сохранена | Structures A/B |
| G5.58 holdout B | account column с тремя независимыми identifiers и header period | header, все три values и period text сохранены | Structures B/C |

Один дополнительный candidate (`pdf_016`) завершился Canonical build failure `artifact_blocked`. Он не использован как положительное доказательство и не ремонтировался вручную.

## Реализованный минимальный slice

Изменён существующий owner `Gate3MetadataSourceFactRuntime`; новый extractor, persistence layer, framework или parallel vocabulary не создавались.

- Contract version: `1.0.0`; fact/collection schemas versioned to `v2`.
- Активный vocabulary содержит только семь типов с реальным source example.
- Structure A сохраняет G5.59 two-cell fail-closed binding.
- Structure B читает только явные source assertions внутри Canonical TEXT; transaction dates и year-only значения не используются.
- Structure C активна только для `ACCOUNT_IDENTIFIER`: structural header должен быть единственным однозначным candidate, merged/duplicate coordinates fail closed, публикуются все distinct values.
- Semantic duplicate key: canonical document/version + fact type + normalized value. Первый source binding сохраняется, повторное утверждение не публикуется второй раз.
- ISO и day-first dates нормализуются детерминированно. Source timestamp в явном period сохраняет source dates без изобретения границ.
- Заголовок `Брокерский отчёт ...` не используется для угадывания issuer; нужен явный issuer label.

Gate 5 продолжает получать metadata через существующую Gate 3 factory composition и financial facts через Gate 4 factory. Source-reading logic в Gate 5 не добавлена.

## Real replay

| Проверка | `pdf_002` | `pdf_024` | Holdout A | Holdout B |
|---|---:|---:|---:|---:|
| Typed metadata facts | 8 | 5 | 3 | 5 |
| Distinct account identifiers | 1 | 1 | 0 | 3 |
| Duplicate metadata assertions | 0 | 0 | 0 | 0 |
| Gate 4 financial facts | n/a | n/a | 39 | 129 |
| Exact frozen G5.58 financial result | n/a | n/a | yes | yes |

`pdf_002` содержит три независимых source-authored section periods; множественность сохранена и не сведена к одному «главному» периоду. Holdout B сохраняет все три account identifiers, не выбирая первый.

Первый диагностический financial replay над `baseline-r1` stores вернул `0/0`: эти stores содержали ранние annotations, не финальные G5.58 artifacts. Этот прогон отброшен как неверно выбранный evidence input и не засчитан ни как PASS, ни как regression. Повторный replay выполнен на копиях именно `final-r5` frozen stores и дал `39/129` с полным структурным равенством frozen Gate 4 JSON.

## Negative proof

Observable-output tests доказывают:

- неизвестная метка и похожее значение не создают fact;
- operation date и operation year не становятся document date/period;
- unlabelled person text не становится `PARTY_NAME`;
- broker/entity INN не становится person INN;
- source-absence fields не получают production pattern;
- несколько account identifiers сохраняются, semantic repeats deduplicate;
- ambiguous или merged account columns fail closed;
- citizenship не создаёт `TAX_RESIDENCY`;
- transaction contract header не становится document contract;
- person name и document date остаются разными fact types;
- unsupported email/language metadata остаётся неизменным в Canonical input и не типизируется.

Invented metadata facts: `0`. Wrong bindings: `0`. Duplicate metadata assertions: `0`. Value-shape inference: `0`. Broker/page/fixed-column branches: `0`.

## Verification

- focused post-format slice: `41 passed`;
- Canonical + Gate 3 persistence + Gate 4 SQL + Gate 5 intake/residency + architecture union: `116 passed`;
- final real metadata replay: `pdf_002=8`, `pdf_024=5`, holdout `A=3`, `B=5`;
- final financial replay: holdout `A=39`, `B=129`, both exact to frozen G5.58 results;
- scoped `git diff --check`: passed;
- provider/LLM calls for G5.60 metadata: `0`.

## KISS и stop

- один существующий metadata owner;
- три bounded source structures;
- один closed versioned vocabulary;
- отсутствующие четыре fields не реализованы;
- Gate 2, financial labeling/materialization и projection не менялись ради G5.60;
- visual inspection остаётся qualification-only;
- document deduplication, generic metadata extraction и unified Gate 3/4 artifact не добавлены.

Следующий metadata GOAL не разрешён. Новый field требует новой user story, named consumer и отдельной версии contract.

Safe receipt: `BROKER_REPORTS_MINIMAL_PERSON_DOCUMENT_METADATA_G5_60.receipt.safe.json`.
