# Broker Reports Gate 5 Evidence Interpretation Contracts v1

Status: `CURRENT SUPPORTING CONTRACT`

Goal: `G5.44`

This contract narrows four interpretation boundaries left implicit after
G5.43. It does not close the four external legal-methodology gaps, activate a
filing path, or make source observations tax conclusions.

## Ownership

| Meaning | Producer | Deterministic owner | Consumer boundary | Forbidden shortcut |
| --- | --- | --- | --- | --- |
| presence/absence intervals and reasons | authenticated human answer through the strict proposal validator | `Gate5ResidencyEvidenceRuntimeFactory.create` | Tax Model and Income Group Base receive only a `methodology_derived_result` classification | direct user `resident` / `non-resident` claim |
| commission detail and aggregate assertions | Gate 4 independent `normalized_source_fact` observations | `Gate5DeterministicSourceFactConsumptionRuntime.select_commission_evidence` under the SHA-pinned source-fact methodology | downstream receives one selected representation and the preserved unselected assertions | sum comparison, reconciliation, double counting, aggregate allocation |
| acquisition-basis quantity coverage | Gate 4 purchase/disposal observations | `Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` | evidence review receives `ACQUISITION_BASIS_COVERAGE_GAP`; current methodology makes its own blocking decision | purchase/disposal relation, pair creation, zero-cost basis |
| same-row transaction charge | exact canonical-row source context | deterministic source-fact consumer; tax eligibility remains with the existing Tax Model evidence rules | Tax Model receives an amount plus `NOT_EVALUATED` deductibility semantics | same-row implies deductible |

Projection consumes already validated semantic results. It must not classify
residency, select commission evidence, turn an uncovered acquisition quantity
into taxable gross proceeds, or decide charge deductibility.

## Residency evidence

The adapter proposal contains only tax period, full-year window,
presence/absence intervals, reported absence reasons and evidence references.
Every proposed date and reason must be literally supported by the authenticated
human answer. The raw answer is not retained in the normalized evidence.

The owned classifier resolves
`ru-3ndfl-2025-declaration-input-contract@2026.0-audited` and rule
`taxpayer-residency-article-207-v1`. It returns `RESIDENT`, `NON_RESIDENT`, or
`INSUFFICIENT_EVIDENCE`. Only the first two can be bound downstream as
`methodology_derived_result`; a user-authored status is rejected.

## Commission evidence selection

Detail and aggregate facts remain independent source assertions. Selection is:

1. details, only when exact required-scope detail coverage is proven;
2. otherwise one aggregate, only when exact matching aggregate scope is proven;
3. otherwise `FAIL_CLOSED`.

Both representations remain visible. The selector does not compare their
values, reconcile them, allocate an aggregate, or decide tax eligibility.

## Acquisition-basis coverage

`ACQUISITION_BASIS_COVERAGE_GAP` is a quantity-level evidence statement:

```text
disposed quantity
supported acquisition-basis quantity
uncovered quantity = disposed - supported
```

It asserts no financial-event relation and assigns no synthetic zero cost.
Evidence review may explain why additional documents can help the client, but
must state `tax_conclusion = NOT_MADE`. Whether the gap blocks a calculation is
a separate, versioned methodology decision.

## Direct transaction charge

Same canonical transaction row proves source context only. The source consumer
returns `TRANSACTION_CHARGE_EVIDENCE` with
`tax_deductibility_status = NOT_EVALUATED`. The existing Tax Model separately
requires `actually_incurred`, `documented`, and `related_to_operation`
evidence; an unproven flag keeps the charge out of allowable expenses.

## Black-box acceptance

The mandatory A-I matrix covers: natural-language residency evidence; detail
only; aggregate only; both representations; uncertain detail coverage with a
matching aggregate; uncertain detail coverage without aggregate; 70/100/30
acquisition coverage; one lot covering ten disposals without stored pairs; and
same-row charge without automatic deductibility.

Successful G5.44 terminals are:

```text
EVIDENCE_INTERPRETATION_CONTRACTS_PROVEN
COMMISSION_SELECTION_CONTRACT_PROVEN
ACQUISITION_BASIS_COVERAGE_CONTRACT_PROVEN
RESIDENCY_EVIDENCE_BOUNDARY_PROVEN
CROSS_DOMAIN_REFACTOR_CONSISTENCY_PROVEN
```

## Scope stop

These remain unresolved and fail closed:

```text
ambiguous_security_disposal_source_classification
partial_acquisition_commission_allocation
non_rub_intermediate_precision_and_rounding
treaty_specific_foreign_tax_credit_limit
```

No product activation, declaration release, XML/PDF emission, commit, push or
PR is authorized by this contract.
