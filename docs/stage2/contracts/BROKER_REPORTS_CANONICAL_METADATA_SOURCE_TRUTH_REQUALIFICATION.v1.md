# Broker Reports Canonical Metadata Source-Truth Requalification v1

Статус: `PROOF-ONLY`
Goal: `G5.62`
Metadata contract: `1.0.0`

## Назначение

Контракт фиксирует стерильную проверку границы `source PDF -> Canonical` для
metadata-контракта G5.60. Он не меняет product runtime и не назначает новый
metadata owner.

Источник истины для этого proof:

```text
визуально квалифицированный source
+ точная Canonical provenance
```

Старый oracle, deterministic extractor и LLM output являются только
diagnostic inputs и не могут подтверждать факт друг через друга.

## Frozen scope

- corpus: `pdf_002`, `pdf_024`, `holdout_a`, `holdout_b`;
- contract version: `1.0.0`;
- fact types: `PARTY_NAME`, `PERSON_BIRTH_DATE`,
  `TAXPAYER_TAX_IDENTIFIER`, `PERSON_CITIZENSHIP`, `DOCUMENT_TYPE`,
  `DOCUMENT_NUMBER`, `DOCUMENT_DATE`, `STATEMENT_PERIOD`,
  `BROKER_LEGAL_NAME`, `ACCOUNT_IDENTIFIER`,
  `ACCOUNT_CONTRACT_IDENTIFIER`;
- новые fact types запрещены;
- provider/model calls: `0`.

## Source-truth assertion

Каждый факт обязан иметь:

- case alias и contract fact type;
- точную видимую source literal;
- source page и визуально подтверждённый region/bbox;
- описание структурного представления;
- Canonical version, node, field path и source refs;
- exact literal внутри Canonical node с provenance на ту же страницу.

Приватные значения, исходные пути, PDF, изображения и полный oracle хранятся
только во внешнем private evidence root. В Git допускаются только агрегаты,
типы, aliases и номера страниц.

## Семантические ограничения

- множественные accounts и periods остаются независимыми assertions;
- signer не становится `PARTY_NAME` субъекта отчёта без явной source semantics;
- client code не становится `ACCOUNT_IDENTIFIER` без явной source semantics;
- похожий текст без доказанной роли даёт `NO FACT`;
- tax residency и иные поля вне frozen contract не добавляются;
- отсутствующий в source contract field не заполняется выводом или default.

## Canonical preservation decision

`CANONICAL_PRESENT` допустим только при одновременном наличии exact source
literal, визуального source binding, exact Canonical literal и page-bound
Canonical provenance.

`CANONICAL_LOSS` означает, что доказанное source assertion не представлено в
Canonical. Тогда разрешён только минимальный общий fix первого владельца
потери. Broker, document, page, column, coordinate и literal-specific rules
запрещены.

Если literal присутствует в Canonical, но не был выбран downstream context
policy, это `CONTEXT_SELECTION_VISIBILITY_LOSS`, а не Canonical loss.

## Oracle requalification

Приватный ledger классифицирует прежние entries как `CORRECT` или
`FALSE_BINDING`, а доказанные новые entries как `MISSING_FROM_ORACLE`.
`SOURCE_ABSENT` фиксируется на уровне отсутствующих contract fact types.
Ошибочные LLM roles фиксируются отдельно как negative qualifications и не
исправляются в G5.62.

## Запрещённые изменения

G5.62 не меняет LLM instruction/prompt, context policy, proposal schema,
model/provider, validator semantics, G5.60 deterministic extractor,
financial pipeline, Gate 4 или Gate 5. LLM replay, retry, best-of-N, manual
repair, prompt tuning и product activation запрещены.

## Acceptance

- все четыре source PDF визуально квалифицированы;
- каждый source-present contract fact имеет Canonical binding;
- Canonical loss count равен `0` после последней проверки;
- старый oracle полностью разложен на `18 CORRECT`, `3 FALSE_BINDING` и
  `6 MISSING_FROM_ORACLE`;
- multiple values не схлопнуты;
- negative role examples сохранены;
- financial replay даёт `39 / 129` и exact frozen equality;
- forbidden owners побайтно неизменны;
- architecture guards green;
- после oracle build выполняется STOP до отдельного G5.63.
