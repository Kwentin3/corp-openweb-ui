# Broker Reports Gate 3 Financial Label Dictionary v2

Status: `CURRENT CONTRACT`

Goal: `G5.40C`

Date: 2026-08-12

## Authority

The sole current label-meaning resource is
[`gate3_financial_label_dictionary.v2.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v2.json),
loaded only through
[`Gate3FinancialLabelDictionaryFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.py).
Its immutable identity is:

```text
dictionary_id: broker-reports-financial-labels
semantic_version: 2.0.0
status: PUBLISHED
file_sha256: a43e20351a83d19e6f12efdcde48a90e5c70fb995c37459d446d10c399109a87
```

Dictionary `1.0.0` remains explicitly loadable historical evidence. It is not
the default current model view.

## Source-fact scope

Version 2.0 contains twelve labels. It keeps the nine v1 identifiers and adds:

- `COMMISSION` for an explicitly stated commission without a concrete
  transaction relation;
- `COMMISSION_TOTAL` for an explicitly stated aggregate commission;
- `TAX_WITHHELD_TOTAL` for an explicitly stated aggregate withholding amount.

`TRANSACTION_CHARGE` is narrowed to a charge explicitly present in the same
accepted source transaction target. That source context is not itself a tax
eligibility decision. `TAX_WITHHELD` is a detail observation and no longer
also denotes an aggregate total.

The exact resource wording is normative. In particular, the dictionary
forbids deriving relations from date, asset, amount, order or proximity and
forbids detail-total sum, reconciliation, replacement or allocation.

## Runtime and lifecycle

Current Gate 3 labeling, managed binding and CLI rendering default to version
2.0. A caller may load historical version 1.0 only by exact semantic version.
All resources are bundled into the standalone OpenWebUI pipe; package or bundle
absence and hash mismatch fail closed.

Draft, validation, approval and publication retain the v1 lifecycle: a draft
never becomes current until a separately reviewed immutable resource and hash
pin exist. Provider output, generated Markdown, Skills, Tools and prompts are
projections, not meaning authorities.

## Boundary

The dictionary chooses only source-observation type. Role values remain owned
by the current Role Pack; normalized values remain Gate 4; calculation,
reconciliation, relation eligibility and declaration meaning remain Gate 5.
See [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md).
