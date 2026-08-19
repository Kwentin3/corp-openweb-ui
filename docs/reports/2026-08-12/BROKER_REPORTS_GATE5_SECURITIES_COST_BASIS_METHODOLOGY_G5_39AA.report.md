# G5.39AA — Securities Cost Basis & Expense Methodology Research

Verified on: 2026-08-12

Mode: consumer-first, official-authority research only. No code, test, Gate 3,
relation-engine, product activation, commit, push, or PR change is authorized.

## Terminal

```text
COST_BASIS_METHOD_PROVEN_FOR_PURCHASE_PRICE
CATEGORY_LEVEL_EXPENSES_SUFFICIENT_FOR_SHARED_FEES
LEGAL_AUTHORITY_AMBIGUOUS_FOR_PARTIAL_ACQUISITION_COMMISSION
STRATEGIC_STOP: ACQUISITION_COMMISSION_PARTIAL_ALLOCATION_AUTHORITY_UNRESOLVED
```

The current Tax Code directly proves FIFO for acquisition price. It also proves
the expense eligibility boundary, direct sale-fee treatment, and an
income-type/category allocation for expenses that cannot be directly attributed.
It does **not** supply an exact rule for allocating a ticket-level acquisition
commission when only part of that acquisition is sold. The G5.39AA exploration
stop condition is therefore not met and a frozen confirmatory implementation
proof is not recommended yet.

This is methodology research, not individual tax or legal advice.

## 1. Consumer-first question

The existing declaration path needs category totals, not a distributed financial
event entity:

```text
category gross income
related expenses
allowable expenses
financial result / declaration projection
```

The missing transformation is narrower:

```text
source-authored acquisition/disposal/fee atoms
  -> tax classification
  -> tax allocation
  -> operation/category derived values
```

The current operation runtime accepts already resolved `gross_income`,
`acquisition_cost`, and `transaction_expense`; it does not own acquisition lots
or FIFO. See
`gate5_securities_disposal_tax_model.py:109,195-221,806-820` and
`gate5_tax_methodology.ru_ndfl_securities_operation_tax_model_proof.v0.json:10-35`.
The current category runtime aggregates member operation totals and explicitly
does not classify expense allowability at aggregate level; see
`gate5_tax_period_category_aggregation.py:50-57,465-480`.

## 2. Authority hierarchy and map

Only current statutory text and official tax-authority material determined the
result. Search results concerning corporate profit tax and Tax Code article 280
were rejected because G5.39AA concerns individual NDFL under chapter 23.

| ID | Rank | Current authority | Methodology consequence |
|---|---:|---|---|
| A1 | 1 | [Tax Code article 214.1, paragraph 10](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/) | An expense must be documented, actually incurred, and connected with acquisition, disposal, storage, or redemption. Listed examples include professional-participant services, exchange fees, and registrar services. |
| A2 | 1 | [Tax Code article 214.1, paragraph 12](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/) | Financial result is income less corresponding paragraph-10 expenses. Expenses not directly attributable to an income type are allocated proportionally to each income type's share. No disposal-level allocation is stated. |
| A3 | 1 | [Tax Code article 214.1, paragraph 13](https://nalog.garant.ru/fns/nk/67db01bcbcd5bd5643515ba89437b4c0/) | On disposal, acquisition-price expense is recognized by first-in-first-out. This is direct cost-basis authority, independent of a holding-period deduction. |
| A4 | 1 | [Tax Code article 210, paragraph 5](https://nalog.garant.ru/fns/nk/6a3eaa02cea3fe2db1e9b04e275d1439/) | Foreign-currency income uses the rate on the actual income date; a deductible expense uses the rate on the actual expense date. |
| A5 | 1 | [Tax Code article 226.1, paragraph 4](https://nalog.garant.ru/fns/nk/6cd8d3f6905f78365f70b64fb5f0a8a7/) | A tax agent may recognize acquisition/storage expenses incurred outside that agent only from an application plus supporting transaction, title, payment, and amount documents. |
| A6 | 3 | [FNS securities-sale explanation, 2025](https://www.nalog.gov.ru/rn11/news/smi/15956801/) | Corroborates acquisition, disposal, storage, and redemption as the relevant expense boundary. |
| A7 | 3 | [FNS foreign-securities explanation, 2022](https://www.nalog.gov.ru/rn78/ifns/imns78_07/info/11815510/) | Corroborates expense categories, operation/category results, and currency dates. The page is explicitly archived, so A1-A5 control. |

The [FNS investment-deduction page](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/nalog_vichet/inv_vichet/)
was retained only as a negative-control scar. Its FIFO statement is scoped to
the ownership period for the investment deduction. It was not used to prove
cost basis; A3 supplies that proof directly.

## 3. Expense decision table

Eligibility and allocation are different decisions. An eligible expense is not
automatically an operation-level amount.

| Expense atom | Eligibility | Tax owner/scope | Proven allocation |
|---|---|---|---|
| purchase price | `ELIGIBLE` when documented and actually paid | acquisition lot | FIFO; selected quantity uses the source-authored unit price or exact purchase-price arithmetic |
| acquisition broker commission | `ELIGIBLE_IF_DOCUMENTED_INCURRED_AND_LINKED` | acquisition | full-disposal use is unproblematic; partial-disposal split is unresolved |
| sale broker commission | `ELIGIBLE_IF_DOCUMENTED_INCURRED_AND_LINKED` | disposal | direct to that disposal when the source establishes the link |
| exchange fee | expressly eligible when documented and incurred | direct transaction or shared scope supplied by source | direct if linked; otherwise A2 income-type allocation |
| depositary/custody fee | eligible when connected with storage/professional service and documented/incurred | direct security scope or shared income-type/category scope | direct if linked; otherwise A2 income-type allocation |
| monthly broker fee | not eligible merely because the broker charged it | conditional on service nature and connection to securities operations | fail closed until direct/shared scope is proven |
| combined or other broker charge | `CONDITIONAL` | unknown until component/service facts exist | no invented allocation |
| undocumented, unpaid, or unrelated charge | `NOT_ELIGIBLE` | none | none |

## 4. Cost-basis and allocation rule

### 4.1 Purchase price

For one homogeneous security within the bounded case:

1. order acquisitions by actual acquisition sequence;
2. consume quantity from the earliest open acquisition first;
3. recognize only the purchase price of the consumed quantity;
4. retain the unconsumed quantity and its remaining purchase price;
5. do not treat the consumption relation as a source fact or Gate 3 relation.

For `100 @ P1`, then `100 @ P2`, then sale of `120`, the recognized purchase
price is `100 × P1 + 20 × P2`; 80 units remain from the second acquisition.
This is the direct consequence of A3 when the source supplies quantity and unit
price.

For one acquisition of 100 units with purchase price 10,000 and a sale of 40,
the bounded exact result is 4,000 recognized and 6,000 remaining, provided the
10,000 atom is solely purchase price and division is exact. This is arithmetic
inside the FIFO-selected lot, not a taxpayer-selected accounting method. If the
source amount mixes fees, units have non-uniform rights, or rounding is
material, the result must fail closed.

### 4.2 Direct disposal expense

A documented and paid sale commission that the source directly binds to one
sale is a corresponding paragraph-10 expense of that disposal. No lot split is
needed.

### 4.3 Shared expense

When a documented expense cannot be directly attributed to an income type, A2
allocates it by each income type's share. The rule is category/income-type level;
it does not require inventing a relation to a particular disposal. If the
expense is 120 and income-type shares are 80% and 20%, the allocations are 96
and 24.

### 4.4 Acquisition commission stopper

A1 proves that a broker/professional-participant commission connected with an
acquisition can be an allowable expense. A3 says FIFO for acquisition **price**.
Neither A1-A5 nor the official FNS explanations inspected in this loop prescribe
how to split one acquisition-ticket commission between 40 disposed units and 60
remaining units.

Therefore this research does not apply `100 × 40 / 100`, does not fold the
commission into per-unit purchase price, and does not consume the full
commission on the first partial sale. The missing rule is
`METHODOLOGY_FACT_REQUIRED`, not a source-document relation problem.

## 5. Synthetic methodology corpus M1-M7

The frozen safe corpus is
`BROKER_REPORTS_GATE5_SECURITIES_COST_BASIS_METHODOLOGY_G5_39AA.corpus.safe.json`.
All numeric cases are synthetic RUB cases; no broker/customer corpus was used.

| Case | Deterministic result | Verdict |
|---|---|---|
| M1: one buy, full sale | 10,000 acquisition price; 12,000 proceeds; result 2,000 | `PROVEN` |
| M2: two buys, full sale | 10,000 + 15,000 acquisition price; 32,000 proceeds; result 7,000 | `PROVEN` |
| M3: two buys, sell 120 | FIFO consumes 100 from lot 1 and 20 from lot 2; acquisition price 13,000; 80/12,000 remain; result 5,000 | `PROVEN_BOUNDED` |
| M4: one buy + 100 acquisition commission, sell 40 | 4,000 purchase-price portion proven; commission portion unresolved | `LEGAL_AUTHORITY_AMBIGUOUS` |
| M5: multiple buys + commissions, sell 120 | 13,000 purchase-price portion proven; commission portions unresolved | `LEGAL_AUTHORITY_AMBIGUOUS` |
| M6: direct 50 sale commission | 4,000 acquisition price + 50 sale fee; 5,000 proceeds; result 950 | `PROVEN` |
| M7: shared 120 custody fee, 80/20 income shares | category allocations 96 and 24; no disposal-level relation | `CATEGORY_LEVEL_EXPENSES_SUFFICIENT` |

## 6. Ownership boundary

| Owner | Values | Gate 3? |
|---|---|---:|
| `SOURCE FACT` | security identity, acquisition/disposal timestamps or sequence, quantities, prices, fee amount/type text, currency, payment/receipt date, document refs, source-authored fee scope | only source-authored facts may originate upstream |
| `TAX CLASSIFICATION` | operation/income category, eligibility, direct/shared expense scope | no |
| `TAX ALLOCATION` | FIFO consumption, partial purchase-price amount, A2 shared-expense allocation | no |
| `TAX DERIVED VALUE` | recognized acquisition price, allowable expense total, financial result | no |

The FIFO lot-consumption relation is a Tax Allocation result. It does not
justify a distributed financial event entity or a new Gate 3 relation owner.

## 7. Minimal atomic input contract

The minimum bounded input is:

```text
calculation scope:
  taxpayer ref
  tax period
  operation/income category facts
  broker/agreement or account scope when legally relevant

security key:
  issuer/instrument/type/class identity sufficient to establish homogeneous units

acquisition[]:
  stable source ref
  actual sequence/date-time
  quantity
  purchase price total and/or exact unit price
  currency
  actual expense date
  document/payment evidence refs

disposal:
  stable source ref
  actual sequence/date-time
  quantity
  gross proceeds
  currency
  actual income date
  document/receipt evidence refs

expense[]:
  stable source ref
  source-authored charge description
  amount and currency
  actual expense date
  payment/document evidence refs
  direct acquisition/disposal/security link when source-authored

shared-expense context:
  complete income-type totals for the allocation scope

external reference:
  Bank of Russia rate for each required actual income/expense date
```

No upstream field may assert `eligible`, `FIFO consumed`, `allowable`, or
`financial result` as a source fact.

## 8. Missing-input classification

| Missing fact | Failure class |
|---|---|
| transaction report, purchase/sale contract, fee invoice, payment evidence, title/quantity evidence | `SOURCE_DOCUMENT_REQUIRED` |
| taxpayer/tax-period/account facts unavailable from governed sources | `USER_FACT_REQUIRED` |
| Bank of Russia rate or official market/category reference | `EXTERNAL_REFERENCE_REQUIRED` |
| partial acquisition-commission allocation rule; legally material rounding rule if non-exact | `METHODOLOGY_FACT_REQUIRED` |

## 9. Currency boundary

Currency is applied after the lot/expense owner is known:

1. identify the FIFO-consumed acquisition quantity;
2. classify the relevant income or expense atom;
3. convert each foreign-currency income at its actual receipt date and each
   deductible expense at its actual expense date under A4;
4. then aggregate RUB-derived values in the proper operation/category scope.

Do not apply the disposal-date rate to historical purchase expense. This loop
does not prove a rounding/precision convention, so non-exact currency cases need
a separate methodology fact before implementation.

## 10. Existing consumer compatibility

The existing consumer is directionally correct but too flat for this method:

- it already keeps gross, related, and allowable amounts separate;
- it already has one factory-routed trusted methodology owner;
- it accepts `acquisition_cost` and `transaction_expense` only after those
  values have been resolved;
- it cannot derive FIFO from ordered acquisition atoms;
- it cannot represent a shared category expense unless it is first forced into
  an operation, which A2 does not require;
- its three evidence flags do not encode expense type, direct/shared scope,
  actual expense date, or the legal allocation basis.

No replacement pipeline is justified. A future authorized design should extend
the existing Tax Methodology/Tax Model seam and leave category aggregation as
the sole consumer of complete operation/category values. This report does not
authorize that design or implementation.

## 11. Deterministic behavior contract

```text
IF purchase-price evidence is missing or not actually incurred:
  SOURCE_DOCUMENT_REQUIRED

ELSE IF homogeneous security identity or acquisition order is incomplete:
  SOURCE_INPUT_GAP_IDENTIFIED

ELSE:
  consume purchase-price lots FIFO by quantity

IF a sale fee is source-linked, documented, and paid:
  classify as direct disposal expense

IF a fee is documented and paid but not directly attributable to an income type:
  require complete income-type scope
  allocate at income-type/category scope under article 214.1 paragraph 12

IF an acquisition fee must be split across a partial disposal:
  LEGAL_AUTHORITY_AMBIGUOUS
  do not derive a partial fee amount

IF foreign currency is present:
  require actual income/expense dates and official rates
  otherwise EXTERNAL_REFERENCE_REQUIRED
```

## 12. Research scars and unknowns

- FIFO found in the investment-deduction guidance was rejected as cost-basis
  authority until current article 214.1 paragraph 13 was inspected.
- Corporate profit-tax rules and article 280 were rejected as the wrong tax
  chapter even when search snippets contained superficially useful commission
  wording.
- The archived 2022 FNS page is corroboration only; current Code text controls.
- No official source inspected prescribed a partial-lot acquisition-commission
  formula.
- Article 214.1 paragraph 12 proves income-type proportional allocation, not a
  disposal-level allocation for shared charges.
- Multi-broker transfers, corporate actions, gifts/inheritance, splits, mergers,
  REPO, shorts, securities lending, derivatives, and non-uniform units remain
  outside this bounded result.
- A legally material decimal/rounding convention was not proven.

## 13. KISS check and stop

The healthy core is small: ordered acquisition atoms, one statutory FIFO rule,
direct expense classification, one category allocation rule, and separate
currency conversion. No relation engine, event graph, parallel methodology
owner, mutable registry, or declaration rewrite is needed.

G5.39AA stops at the first genuine authority gap. The next admissible work
inside this same research goal is a binding official clarification or directly
applicable court/agency authority for partial acquisition-commission allocation.
Until that exists, no frozen confirmatory proof and no implementation should be
started.
