# Broker Reports G5.90 — Foreign Tax Adjustment Methodology Input Contract

Status: `FOREIGN_TAX_ADJUSTMENT_METHODOLOGY_GAP_LOCALIZED`

Strategic stop: `METHODOLOGY_LEGAL_INTERPRETATION_REVIEW_REQUIRED`

Date: 2026-08-17

Scope: Gate 5 methodology research and maintained-contract refinement only.
Gate 3/4 ontology, source rows, parser/VLM, relation graph, settlement
arithmetic, Projection and product activation are unchanged.

## Architecture and executable consumer

The maintained route remains:

```text
Gate 4 proved source facts
-> versioned Gate 5 methodology inputs
-> methodology-derived foreign_tax_credit
-> Gate5DeclarationTaxSettlementRuntimeFactory.create
-> Declaration Semantics
```

The current settlement runtime consumes `foreign_tax_credit` as an already
derived settlement fact. The current trusted declaration-input methodology
requires income/year, tax amount/payment date, supporting document,
translation, residency and treaty, and fails as `METHODOLOGY_UNRESOLVED` when
these are insufficient. It contains no refund, reversal, adjustment or netting
operation. Documentation and runtime agree; no
`METHODOLOGY_CONTRACT_IMPLEMENTATION_DRIFT_PROVEN` terminal applies.

## Official authority findings

### Explicit official rules

1. [Tax Code Article 232](https://nalog.garant.ru/fns/nk/5d22100e7a48445f5abd8c902bfc7cb7/)
   limits the credit question to tax actually paid by a Russian tax resident
   on foreign income, subject to the applicable treaty. The claim is made by
   declaration after the tax period and can be made within three years after
   the income period.
2. Article 232 requires evidence of income kind, amount and calendar year plus
   foreign tax amount and payment date. Withholding requires a document from
   the income source with monthly income and withholding amounts. A translation
   is required.
3. The [current FNS Order ED-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/)
   applies to the 2025 declaration. Its
   [official form](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf)
   requires country/source, income currency/date/amount, tax-payment date,
   CBR rate on that date, foreign tax amount and the calculated Russian credit.
4. [Tax Code Article 81](https://nalog.garant.ru/fns/nk/646cd7e8cf19279b078cdec8fcd89ce4/)
   generally requires a corrected declaration when discovered errors cause an
   understatement of tax.

### Methodology interpretation, not an explicit rule

- A later foreign-tax refund or reversal may change the amount that remains
  “actually paid”, but the reviewed official sources do not define the exact
  operation for a broker adjustment row.
- The sources do not directly determine whether a late adjustment belongs to
  the income period, payment date, adjustment date or correction filing state.
- Article 81 may become relevant if a reviewed adjustment makes a filed return
  understate Russian tax, but that causal conclusion itself requires legal
  review.
- No official source reviewed here authorizes pairing or netting by value,
  date, adjacency, instrument or same-document placement.

## Consumer-first decisions

| Candidate distinction | Named consumer decision | Coarser fact sufficient? | Verdict |
| --- | --- | --- | --- |
| payment/withholding evidence vs adjustment observation | may foreign-tax-credit derivation proceed? | no: an adjustment cannot be counted as paid tax | distinction required at methodology input; no Gate 3 type yet |
| refund vs reversal vs other adjustment | exact tax effect | yes for current behavior: every variant remains unresolved | do not add separate taxonomy |
| adjustment-to-income/payment association | may a reviewed adjustment affect this claim? | no if a calculation is attempted | require explicit documentary evidence; never infer |
| adjustment date/period | which declaration/correction is affected? | no, but official operation is missing | legal review gap |

## Minimum review factual envelope

| Input | Owner |
| --- | --- |
| foreign income kind, amount, currency, receipt date/year, source and jurisdiction | `SOURCE` |
| foreign tax amount, currency, payment/withholding date and authoritative document | `SOURCE` or supplied authoritative evidence |
| literal adjustment wording, source-stated direction/kind if present, amount, currency, date, issuer and provenance | `SOURCE`; `UNMAPPED` remains valid |
| explicit association evidence to the income/tax claim | `SOURCE` or authoritative evidence |
| treaty/effective state and exact CBR rate/nominal | `EXTERNAL` |
| tax period, filing/correction instance and evidence cutoff | `USER/CASE` |

This envelope is sufficient to review a rule and to fail closed. It is not yet
an executable netting contract. The current source contract is therefore
`PARTIALLY` sufficient: it preserves withholding and literal unmapped evidence,
but does not provide an admitted adjustment distinction or proved association.

## Result

```text
FOREIGN_TAX_ADJUSTMENT_METHODOLOGY_GAP_LOCALIZED
METHODOLOGY_LEGAL_INTERPRETATION_REVIEW_REQUIRED
FOREIGN_TAX_WITHHOLDING_VS_ADJUSTMENT_REQUIREMENT_PROVEN
MINIMAL_REVIEW_FACTUAL_ENVELOPE_PROVEN
SOURCE_USER_EXTERNAL_OWNERSHIP_PROVEN
TAX_CONCLUSION_REMAINS_AFTER_GATE4
NO_INFERRED_NETTING_OR_RELATIONS
```

Not claimed:

```text
FOREIGN_TAX_ADJUSTMENT_METHODOLOGY_INPUT_CONTRACT_PROVEN
MINIMAL_FACTUAL_INPUT_SET_PROVEN
READY_TO_REEVALUATE_MINIMAL_SOURCE_CONTRACT
```

The next Goal belongs to reviewed legal methodology: establish the exact
effect and period/correction treatment of an authoritative foreign-tax refund,
reversal or adjustment, including treaty-specific limits. Only after that
review may the source-contract admission test be rerun.

## Verification

- pre-change factory/runtime baseline: `53 passed`;
- the trusted-factory proof asserts the exact current Article 232 inputs and
  absence of adjustment/reversal/netting behavior;
- post-change verification: `54 passed` for methodology/consumer seams plus
  `55 passed` for Gate isolation, source-fact consumption and preparation.
