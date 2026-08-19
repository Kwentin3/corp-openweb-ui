# Broker Reports Minimal Person & Document Metadata Contract v1

Status: `FROZEN_FOR_G5_60_PROOF`

## Purpose

Этот contract определяет минимальную source-backed карточку человека и документа. Поле разрешено только при наличии named consumer: налоговый консультант, налоговый runtime или контроль комплекта документов.

Canonical сохраняет прочий source content без типизации. Отсутствие source evidence не заполняется default, inference или synthetic support.

## Closed field set

### PERSON

| Contract field | Published fact type | Meaning | Cardinality |
|---|---|---|---|
| `FULL_NAME` | `PARTY_NAME` | явно названное source лицо, о котором документ | multiple allowed, role must be explicit |
| `BIRTH_DATE` | `PERSON_BIRTH_DATE` | дата рождения этого лица | multiple allowed, role must be explicit |
| `TAX_IDENTIFIER / INN` | `TAXPAYER_TAX_IDENTIFIER` | ИНН/налоговый идентификатор этого лица | multiple allowed, person role must be explicit |
| `CITIZENSHIP` | `PERSON_CITIZENSHIP` | явно заявленное гражданство этого лица | multiple allowed, person role must be explicit |

`TAX_RESIDENCY` отсутствует в contract. Citizenship и source declarations не создают методологический вывод о налоговом резидентстве.

### DOCUMENT

| Contract field | Published fact type | Meaning | Cardinality |
|---|---|---|---|
| `DOCUMENT_TYPE` | `DOCUMENT_TYPE` | явно названный тип текущего документа | one or multiple source assertions |
| `DOCUMENT_NUMBER` | `DOCUMENT_NUMBER` | явно названный номер текущего документа | multiple allowed |
| `DOCUMENT_DATE` | `DOCUMENT_DATE` | явно названная дата текущего документа | multiple allowed |
| `STATEMENT_PERIOD` | `STATEMENT_PERIOD` | явно названный период, за который сообщает текущий документ | multiple allowed; range remains structured |

Operation dates and years never become document date or statement period. A year-only source assertion remains year-only until a separately versioned representation contract exists; concrete boundary dates are not invented.

### SOURCE

| Contract field | Published fact type | Meaning | Cardinality |
|---|---|---|---|
| `ISSUER / BROKER` | `BROKER_LEGAL_NAME` | source-authored issuer or broker identity | multiple allowed; no filename/layout inference |

### ACCOUNT

| Contract field | Published fact type | Meaning | Cardinality |
|---|---|---|---|
| `ACCOUNT_IDENTIFIER` | `ACCOUNT_IDENTIFIER` | source explicitly calls the value an account identifier | multiple allowed |
| `CONTRACT_IDENTIFIER` | `ACCOUNT_CONTRACT_IDENTIFIER` | source explicitly calls the value a contract identifier | multiple allowed |

No arbitrary identifier is promoted to account or contract identity. Multiple identifiers remain multiple independent source facts; runtime never selects one as canonical.

## Allowed source structures

Production support requires a visually qualified real source example and preserved Canonical structure.

1. `ADJACENT_TABLE_LABEL_VALUE` — G5.59 fail-closed two-cell same-row binding.
2. `EXPLICIT_HEADER_TEXT` — one Canonical TEXT node contains an explicit field assertion and its source-backed value. No transaction-derived period/date.
3. `EXPLICIT_COLUMN_HEADER_VALUES` — a recognized field header owns explicit values below it in the same Canonical table; every value remains an independent fact and ambiguous headers fail closed.

These are bounded contracts, not a generic metadata extractor. A structure is inactive for a fact type until a real source example is visually qualified during G5.60.

## Owner and route

```text
source
→ Gate 2 Canonical structure
→ existing Gate3MetadataSourceFactRuntime
→ existing downstream evidence-intake composition
```

Gate 5 must not read source or Canonical. Gate 4 financial materialization remains separate. No unified metadata framework, new persistence layer or document-deduplication behavior is authorized.

## Validation law

- Type comes from explicit source language/context, never value shape.
- Every fact binds to Canonical node/field paths and source refs.
- Person and organization identifiers remain distinct.
- Person birth date and document date remain distinct.
- Unsupported metadata remains in Canonical and creates no typed fact.
- Missing or ambiguous evidence returns no fact.
- `NO_REAL_SOURCE_EXAMPLE` forbids production implementation on synthetic fixtures.

## G5.60 stop

No new metadata field may be added after this proof without a new user story, named consumer and separately authorized contract version.
