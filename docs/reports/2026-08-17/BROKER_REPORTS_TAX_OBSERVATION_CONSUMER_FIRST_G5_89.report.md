# Broker Reports G5.89 — tax observation consumer-first admission

Status: `METHODOLOGY_INPUT_CONTRACT_GAP_PROVEN`

Date: 2026-08-17

Scope: architecture and current-contract audit only. No provider call, source
relabeling, Gate 3/4 schema change, tax calculation, product activation or
private source material is included.

## Architecture bootstrap

The current authority chain was read before the observed tax rows:

```text
Pipeline Gates -> current domain contract -> public factory/runtime
-> versioned methodology -> guide -> dated report
```

The maintained model is one-way:

```text
source -> literal source -> broker-stated meaning -> proved source facts
--- methodology boundary ---
methodology -> declaration semantics -> release -> projection
```

Gate 3 owns source meaning, Gate 4 owns normalized source facts, and Gate 5
alone may derive tax consequences from reviewed methodology. G5.x reports are
evidence, not normative owners.

## Consumer test

| Question | Result |
| --- | --- |
| Candidate source meaning | broker-authored tax correction/refund/reversal observation; not a tax conclusion |
| Current owner | Gate 3 Dictionary/Role Pack if admitted; Gate 4 Fact v2 only transports an admitted meaning |
| Current contract can represent it? | `PARTIALLY`: Canonical preserves the literal row, but the current Gate 3 Dictionary deliberately excludes refund from `TAX_WITHHELD` and has no reversal/refund type |
| Named downstream consumer | `NONE` in the current executable source-fact-to-methodology path |
| Why consumer needs this distinction | not established by any current consumer contract |
| What methodology derives from it | nothing current; foreign-tax-credit requirements do not define reversal/refund/netting input semantics |
| Why `UNMAPPED` is not sufficient | no such reason is proven; faithful unmapped retention is sufficient until reviewed methodology names the required factual distinction |

Admission verdict: `NO_NEW_SOURCE_TYPE`. In particular, a literal such as
`US Tax credit` does not prove `TAX_REVERSAL`.

## Docs -> implementation -> factory -> behavior

| Boundary | Current evidence | Verdict |
| --- | --- | --- |
| Gate 3 | Dictionary 2.0.1 defines `TAX_WITHHELD` as explicitly withheld tax and excludes refunds; Role Pack 3.0.0 has no direction/reversal role | source-semantic ceiling is enforced |
| Gate 4 | Financial Case Fact v2 carries exact admitted type/roles/provenance through `Gate4FinancialCaseRuntimeFactory.create` | no methodology or tax reinterpretation |
| Gate 5 source consumption | `Gate5DeterministicSourceFactConsumptionRuntimeFactory.create` exposes withheld detail/aggregate assertions without reconciliation | no reversal/refund consumer |
| Gate 5 methodology | trusted source-fact methodology `2026.6-interpretation-contract` preserves independent withheld assertions; declaration-input methodology requires explicit foreign-tax-credit evidence; settlement accepts already-derived facts | required factual input contract is absent |

No contract/runtime contradiction was found in this chain, so
`CONTRACT_IMPLEMENTATION_DRIFT_PROVEN` does not apply. The gap is semantic and
belongs to methodology input design, not to a hidden runtime implementation.

## Decision and bounded refinement

`BROKER_REPORTS_PIPELINE_GATES.v1.md` now makes consumer-first source-meaning
admission executable as a navigation invariant:

```text
SOURCE_MEANING_ADMISSION = NAMED_CONSUMER + REQUIRED_FACTUAL_DISTINCTION + VERSIONED_METHODOLOGY_INPUT
NO_NAMED_CONSUMER = RETAIN_AS_UNMAPPED_SOURCE_CONTENT
```

No Gate 3 enum, Gate 4 field, Gate 5 Canonical/PDF reader, relation graph,
Human Adapter conclusion, projection repair or parallel architecture was
added. A future Goal must first define and review the methodology factual input
needed for reversal/refund/netting. Only then may it rerun the consumer test and
consider the smallest source-contract extension.

## Verification

- focused pre-change baseline: `61 passed`;
- architecture navigation test pins the two admission invariants and terminal;
- post-change focused verification: `61 passed` plus `24 passed` across the
  Gate 4 fact, source-domain, real-tax-case and declaration-preparation seams.
