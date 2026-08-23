# Broker Reports Issue #295 research and proof report

Status: `ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN`

Exact base `main`: `8df654f7070b8420be2d8db8f3516c9d7918daf6`

Scope: one inactive synthetic 2025 RUB ordinary-security purchase/disposal
control. This is not a real-PDF, cross-broker, legal-correctness, filing or
product-readiness proof.

## Research result

The historical G5.35 left side cannot replace the current Fact v2 path: it
enters through Gate 3 and `Gate4FinancialCaseRuntimeFactory.create`. Its
right-side assembly sequence, however, was genuine shared behavior. It has
therefore been extracted into
`Gate5DeclarationRightSideAssemblyRuntimeFactory.create` and is now used by
both G5.35 and Issue #295. Direct `income_group.taxpayer_status` and
`taxpayer.period_status` are rejected on both routes; the residency owner is
the only source of this classification.

The retained change is smaller than a new declaration framework:

- one thin coordinator that orders existing owners;
- one shared right-side assembly owner extracted from G5.35, delegating all
  component meaning to the established factories;
- one additive current-Fact entrypoint on the existing Scope factory;
- one additive current-Fact entrypoint on the existing Package factory;
- one category-owner typed operation/taxpayer-binding validator, with the
  Issue #293 bridge retaining a compatibility entrypoint;
- historical factory behavior remains covered and unchanged.

Rejected approaches were direct Category-to-semantic projection, a copied
right-side assembler, reconnecting historical Gate 3/SQL Gate 4, and resolving
partial acquisition commission by formula.

The ordinary-domain marriage is localized in the Issue #295 composition. It
constructs Gate 4 ordinary there, injects it into Scope, then injects Scope into
Package. Universal Scope and Package import neither the ordinary bridge nor
`Gate4OrdinaryTradeCandidateRuntimeFactory`; the bundle keeps its established
right-domain order.

## Clean visual and semantic accounting

| Stage | Exact controlled accounting |
| --- | --- |
| source-bound Fact v2 visual | one purchase, one disposal and two disposal-local transaction-charge facts; every row is rebuilt from the live Fact v2 role and includes its exact fact ID/hash, normalized value, source literal and source target |
| FIFO/source fact | consumed quantity `4`; recognized acquisition cost `40.00 RUB`; disposal proceeds `60.00 RUB`; direct disposal charge `3.00 RUB`; acquisition-commission fact IDs empty |
| operation Tax Model | related expenses `43.00 RUB`; allowable expenses `43.00 RUB`; no demand |
| Category Tax Model | gross `60.00 RUB`; related/allowable `43.00 RUB`; complete exact taxpayer/category/period binding |
| income-group Tax Base | explicit other income, non-taxable income, other expenses and deductions are source-tagged `0.00`; total/taxable income `60.00`; accepted expenses `43.00`; tax base `17.00 RUB` |
| Scope/Package | separate `operation_subject_ref=security-disposal-1` and `taxpayer_scope_ref=synthetic-taxpayer-control`; package `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE` |
| release | `44` released semantic leaves, all owner-bound |
| consumer target | `49` occurrences, `49` with known evidence/authority refs; identical XML bytes on repeat |
| official XSD | `NO_NDFL3_1_033_00_05_20_01.xsd`, SHA-256 `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484`, `xsd_valid=true` |

The safe receipt embeds the owner-produced artifacts needed for independent
replay. Exact hashes are run outputs, not hard-coded report claims.

## Material control

Adding an acquisition commission preserves the upstream demand exactly:

```text
partial_acquisition_commission_allocation
LEGAL_INTERPRETATION_REQUIRED
Gate5DeterministicSourceFactConsumptionRuntime
```

The Category model may remain numerically complete, but the coordinator emits
`BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN`; released values and target
receipt are both absent.

## Negative-control matrix

| Control | Primary owner/result |
| --- | --- |
| material acquisition commission | source-fact owner; original legal demand retained |
| missing/foreign taxpayer binding | Issue #293 bridge; `USER_CASE_FACT_MISSING` |
| absent/stale category completeness | category owner; typed incomplete/binding mismatch |
| absent/stale income-group completeness | income-group owner; missing or exact binding failure |
| missing organized-market status | operation Tax Model; `EXTERNAL_AUTHORITATIVE_FACT_MISSING` |
| missing residency or filing identity | residency/filing owner; `USER_CASE_FACT_MISSING` |
| direct income-group or filing taxpayer status | shared right-side owner rejects caller classification |
| missing source party | income-source owner; `SOURCE_EVIDENCE_INSUFFICIENT` |
| missing settlement or budget input | settlement/budget owner; typed missing input |
| changed Category with old group completeness | income-group owner rejects the stale binding |
| direct Category to semantic/XML bypass | semantic owner rejects non-Package input |
| historical G5.35/Gate 3/SQL fallback | monkeypatched traps remain uncalled on positive route |
| Package or released artifact changed, outer hashes recalculated | Package/release owner replay fails closed |
| target receipt/XSD or 44/49 accounting changed, outer hashes recalculated | projection owner replay or exact accounting fails closed |
| missing/extra/reordered receipt stage | exact stage-set validation fails closed |
| caller raw visual table | coordinator rejects an untrusted parallel source picture |

All material stops are machine-readable and produce no complete release or
XML receipt.

## Source delta

Changing only the disposal-proceeds source literal from `60.00` to
`64.00 RUB` changes the live Fact v2 visual row to `64.00` and changes exactly
these G5.45 target mapping IDs:

```text
budget-payable
total-income
taxable-income
tax-base
calculated-tax
tax-payable
source-income
securities-gross-income
```

All other target occurrence hashes remain identical.

## Local verification after independent review

- `32 passed`: active composition, source-bound delta, direct-status rejection,
  exact-stage validation and self-consistent artifact-mutation attacks;
- `73 passed`: Scope, Package, income-group, category and Issue #293 bridge
  owner suites;
- `21 passed`: bundle execution/parity and architecture stabilization;
- Ruff, Python compilation and `git diff --check`: passed.

The historical G5.35 file has one independent architecture/static test passing
locally. Its six source-execution tests still stop on this Windows checkout at
the pre-existing `gate5_e2e_gate2_canonical_missing`, before the shared
right-side owner is reached; this is reported separately and is not presented
as a green result.

## Uncomfortable questions

1. No demand disappears: the material commission demand is byte-for-byte
   retained in `demands` and blocks release.
2. Yes, Category can be numerically complete while declaration release must
   stop; the material control proves it.
3. No synthetic input becomes real evidence or a hidden zero. Every zero is an
   explicit source-tagged right-side fact and `real_user_fact=false`.
4. The coordinator copies no calculation or completeness meaning. G5.35 and
   #295 share one right-side assembly owner, which delegates to the existing
   calculation/component factories.
5. Taxpayer identity remains independent from the modeled disposal in the
   bridge, Scope receipt and Package validation.
6. One proceeds-cell change produces only the eight justified mapping deltas.
7. Old category/group evidence fails after mutation. A Package, released
   artifact, target receipt, XSD flag or 44/49 count also fails after an
   attacker recalculates every outer receipt hash, because validation replays
   the producing owners and exact stage inventory.
8. Projection remains representation-only; all 49 occurrences carry existing
   mapping evidence and XSD validation is separate.
9. The official XSD result is reached with Gate 3, historical SQL Gate 4 and
   prebuilt Tax Models all absent; executable traps enforce this.
10. The proof remains synthetic, one-profile, RUB-only, legally unresolved for
    partial acquisition commission, unpersisted, non-downloadable and inactive.
11. Scope and Package remain ordinary-domain agnostic: Gate 4 ordinary is
    constructed only by the #295 composition and passed through injection.

## KISS and stop

No Definition, Package, semantic-input, projection, taxonomy, DB, graph,
workflow, rules engine, LLM adapter or product route was added. The next
smallest step, if separately authorized, is review/qualification of the
inactive composition; activation and legal-gap resolution remain out of scope.
