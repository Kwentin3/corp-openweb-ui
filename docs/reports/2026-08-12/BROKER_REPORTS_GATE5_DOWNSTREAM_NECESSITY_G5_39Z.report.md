# Broker Reports Gate 5 — G5.39Z Downstream Necessity Audit

Date: 2026-08-12

Mode: exploratory research only

Product implementation: none

Provider/model calls: 0

## Terminal

```text
DISTRIBUTED_EVENT_ENTITY_NOT_JUSTIFIED
DERIVED_VALUES_BELONG_TO_TAX_MODEL
STRATEGIC_STOP: COST_BASIS_ALLOCATION_AUTHORITY_UNRESOLVED
```

Deleting the invented distributed event `C` does not make any audited
declaration or XML mapping impossible. The first real unmet demand is narrower:
the securities Tax Model needs an authoritative way to turn atomic acquisition
and fee facts into allowable expense inputs for the applicable operation
category, especially for multiple or partial lots.

The current checkout does not prove whether that general capability requires a
named relation, a deterministic tax-methodology allocation, an additional
source fact, or a user-verified input. Therefore this audit stops before design
or implementation.

## Scope and governing distinction

The audit kept these meanings separate:

- **source fact**: a typed financial fact with exact source provenance;
- **relation**: evidence that one fact belongs to another fact or calculation
  scope, without creating a new financial amount;
- **derived value**: a methodology result such as an eligible expense total,
  category total, tax base, or tax amount.

No new schema, Gate 4 type, relation database, graph, Tax Model, adapter,
reconciliation engine, or product path was created.

## Downstream demand matrix

| Candidate semantic | Concrete consumer | What is actually read | Can atoms supply it? | Named relation required? | Derived `C` required? | Status |
|---|---|---|---|---|---|---|
| `distributed securities event` containing purchase, fee and disposal | Conditional no-supplemental branch in `Gate5EndToEndFullTargetXmlRuntime._tax_models` | cost values plus expense eligibility evidence | only for the current exact whole-quantity special case | not proven as a declaration requirement | no | `UNKNOWN_REQUIREMENT` for general lots; current-code convenience only |
| purchase → transaction charge | `Gate5RelatedSecuritiesEventsRuntime` | same source target, date, currency and optional asset | yes when the source already supplies those exact bindings | may be derived locally; persistence is unjustified | no | `DERIVABLE_AT_CONSUMER` in the bounded exact case |
| acquisition lot → disposal quantity | securities operation Tax Model | acquisition cost attributable to disposed securities | exact whole-quantity case: yes; partial/multiple lots: not proven | possibly, but authority and granularity are unresolved | no | `UNKNOWN_REQUIREMENT` and strategic stopper |
| operation expense eligibility | securities operation Tax Model | `actually_incurred`, `documented`, `related_to_operation` per expense component | amount/document evidence may be atomic; tax relatedness is not a source amount | at least calculation-scope classification is required | no | `DERIVABLE_AT_CONSUMER` if governed by methodology; current owner is mixed |
| category gross/related/allowable totals | category aggregation, declaration semantic input, Appendix 8/XML | totals for an operation code/category and loss flag | from complete operation Tax Models | no | yes, but only as Tax Model output | `DERIVABLE_AT_CONSUMER` |
| dividend + withholding + accrual distributed event | no audited Gate 5 consumer | income-source consumer reads separate gross income and withheld tax; accrual is not read | bounded domestic case: typed facts plus source/scope completeness are sufficient | no event relation proven necessary | no | income/withholding: `ATOMS_SUFFICIENT`; accrual/event wrapper: `NOT_CONSUMED` |
| reconciled operation object | declaration semantic input and XML | neither relation IDs nor event membership; only semantic totals and source entries | downstream can consume Tax Model results | no | no stored entity | `NOT_CONSUMED` |
| arithmetic `A + B = C` consistency witness | validation only | equality/consistency result | yes | no | no | validation, not a domain entity |

## Backward consumer trace

### XML and declaration boundary

The full target XML definition reads securities category results:

```text
operation_category
category_gross_income
related_expenses
allowable_expenses
loss_treatment
```

It does not read a distributed event ID, purchase ID, charge ID, disposal ID,
or event-membership relation. The same definition reads taxable income-source
entries separately, including `gross_income` and `tax_agent.withheld_tax`.

Relevant repository anchors:

- `gate5_full_target_xml_projection.ru_3ndfl_2025.v0.json:238-246` — securities
  category result mapping;
- the same resource at `:222` — withheld tax is mapped from a separate income
  source entry;
- `gate5_declaration_semantic_input.py:503-508` — category values are copied
  into the target-independent semantic input;
- `gate5_declaration_income_sources.py:223-317` — source entries independently
  account gross, taxable and withheld totals.

### Category and Tax Model boundary

`Gate5TaxPeriodCategoryAggregationRuntime` consumes completed operation Tax
Models and deterministically aggregates their gross, related and allowable
expense values. It does not consume relation IDs and does not repeat expense
eligibility decisions.

`Gate5SecuritiesDisposalTaxModelRuntime.run_operation()` can run without the
related-event entrypoint. Its governed methodology nevertheless asks for
`acquisition_cost` and `transaction_expense` as requirements bound to a
`SECURITY_DISPOSAL` subject. In the current proof route those values are
supplied as supplemental facts.

`Gate5EndToEndFullTargetXmlRuntime._tax_models` makes the implementation history
explicit:

```text
supplemental facts present -> run_operation()
supplemental facts empty   -> run_operation_from_related_events()
```

The primary supplied-case resource contains both supplemental amounts. Thus the
related-event path is an alternative input-acquisition mechanism, not a
declaration-mandated semantic entity.

### Current related-event owner

`Gate5RelatedSecuritiesEventsRuntime.resolve()` currently combines three
responsibilities:

1. select one disposal and one matching whole-quantity purchase;
2. associate a charge through exact source target/date/currency/asset checks;
3. publish gross income, acquisition cost, transaction expense, and three
   positive expense-evidence flags.

That result mixes relation evidence with methodology-facing derived inputs. Its
name and existence are not evidence that the tax domain requires the composite
entity.

## Official declaration demand

The official FNS filling procedure for the 2025 3-NDFL form, Appendix 8,
paragraphs 97-98 requires rows by operation code and then:

- total income over the aggregate of performed operations;
- total expenses connected with acquisition, disposal, holding and redemption;
- total expenses accepted in reduction of income over that aggregate.

The audited official document does not require a purchase/fee/disposal event
object in the declaration. It establishes category/operation-code totals, but
it does not by itself settle the lot-level allocation rule needed to compute
those totals from arbitrary broker atoms.

Official artifact verified on 2026-08-12:

- FNS Order ED-7-11/913@ page:
  `https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/`;
- Appendix 2 filling procedure:
  `https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx`;
- downloaded bytes: `106008`;
- SHA-256:
  `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc`.

This hash matches the repository's trusted methodology evidence.

## Atom-only replay

### Intended replay

The read-only replay supplied Gate 4 with typed purchase, disposal, dividend,
transaction-charge and tax-withheld facts, with no synthetic distributed
entity and no supplemental expense facts. It then invoked the existing Gate 4
and Gate 5 factories.

### Observed first runtime blocker

The replay did not reach the financial-semantic decision. In two diagnostic
attempts the current dirty checkout produced:

```text
Gate 4 status: CASE_INCOMPLETE
first runtime error: gate4_cache_missing
```

The focused test run confirmed the same root failure. Its first assertion was:

```text
expected: CASE_COMPLETE_FOR_CURRENT_INPUT_SET
actual:   CASE_INCOMPLETE
```

Downstream failures then shared `gate4_cache_missing`. This is an infrastructure
or fixture-initialization failure, not proof for or against relation necessity.
No tests, fixtures, or runtime code were changed to make the run green.

Focused verification from PowerShell in
`services/broker-reports-gate1-proof`:

- related-event bounded behavior: `5 passed in 0.85s`;
- broad downstream selection: `18 passed, 30 failed in 12.52s`;
- declaration projection selection: `17 passed, 2 failed in 4.85s`;
- all reported failures that reached the shared path were downstream of the
  Gate 4 incomplete/cache condition.

The green relation tests show only that the exact whole-quantity special case
behaves as implemented. They do not establish general lot allocation or tax
necessity.

## Ownership matrix

| Meaning | Owner supported by evidence | Boundary |
|---|---|---|
| typed amount/date/currency/asset/quantity and exact source refs | `SOURCE` / Gate 3-4 financial fact | immutable source-bound facts; no reconciliation |
| source-explicit same-row or same-target association | `RELATION` evidence | retain only if source-authored or deterministically exact |
| acquisition-cost selection for disposed quantity | `TAX METHODOLOGY` by default | general rule/authority unresolved; do not move upstream |
| fee eligibility and allocation to operation category | `TAX METHODOLOGY` by default | requires authoritative rule and evidence policy |
| category totals and loss treatment | `TAX METHODOLOGY` | existing operation/category Tax Models |
| declaration semantic fields and XML names/codes | `DECLARATION` | projection/definition authorities |
| distributed purchase/fee/disposal or dividend event object | no justified owner | remove from required problem space unless a future consumer proves demand |

## Research scars

The previous loop treated the following as targets before proving their
consumer demand:

- a composite purchase + charge event;
- purchase/holding/disposal alignment as a reusable financial entity;
- a distributed dividend + withholding + accrual event;
- a source-verifiable event-membership witness for those composites;
- a generic reconciled operation object.

The useful residue is smaller: exact source-bound atoms, explicit source
relations where they truly exist, and a now-localized methodology question.
The failed event-binding research was not wasted, but the composite entity is
not a justified product contract.

## Minimal required semantic set

Between Gate 3 and the audited Gate 5 declaration path, the evidence supports
only:

1. source-bound typed financial facts with exact literals and refs;
2. complete taxpayer/tax-period/category scope evidence;
3. resolved tax applicability properties;
4. methodology-owned expense eligibility and any required lot/fee allocation;
5. operation and category Tax Model results;
6. separate income-source facts, including withheld/foreign tax when relevant;
7. declaration semantic input and deterministic XML projection.

It does not support a stored distributed financial event as a mandatory layer.

## Strategic stopper and next boundary

The concrete unresolved statement is:

```text
SECURITIES TAX MODEL
REQUIRES AN AUTHORITATIVE COST-BASIS AND FEE-ALLOCATION SEMANTIC
BECAUSE CATEGORY EXPENSE TOTALS CANNOT BE COMPUTED FOR MULTIPLE OR PARTIAL LOTS
FROM UNCLASSIFIED ATOMIC PURCHASE/CHARGE FACTS ALONE.
```

What remains unknown is the exact authority, granularity and algorithm. That is
the only justified next research boundary. It must begin from official tax
methodology and representative lot cases, not from another LLM event-linking
experiment.

No next GOAL, G5.40, implementation, activation, push, PR, or product mutation
is authorized by this report.

## KISS check

- one missing capability, not a generic relation engine;
- no new upstream derived fact;
- no persistence or graph;
- existing Tax Model/category/declaration owners remain the only downstream
  owners;
- exact source relations may remain evidence, but cannot become a universal
  event identity claim.
