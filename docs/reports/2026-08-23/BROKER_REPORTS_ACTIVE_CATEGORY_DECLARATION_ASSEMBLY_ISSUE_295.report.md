# Broker Reports Issue #295 research and proof report

Status: `ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN`

Exact base `main`: `8df654f7070b8420be2d8db8f3516c9d7918daf6`

Scope: one inactive synthetic 2025 RUB ordinary-security purchase/disposal
control. This is not a real-PDF, cross-broker, legal-correctness, filing or
product-readiness proof.

## Research result

The historical G5.35 tail could not be reused: it enters through Gate 3 and
`Gate4FinancialCaseRuntimeFactory.create`, and its Scope/Package checks equated
the SECURITY_DISPOSAL subject with taxpayer scope. Reusing it would have
violated the current Fact v2 boundary and Issue #293 identity contract.

The retained change is smaller than a new declaration framework:

- one coordinator that calls only existing owners;
- one additive current-Fact entrypoint on the existing Scope factory;
- one additive current-Fact entrypoint on the existing Package factory;
- reuse of the Issue #293 typed taxpayer-binding validator;
- historical factory behavior remains covered and unchanged.

Rejected approaches were direct Category-to-semantic projection, a copied
right-side assembler, calling private G5.35 helpers, reconnecting historical
Gate 3/SQL Gate 4, and resolving partial acquisition commission by formula.

## Clean visual and semantic accounting

| Stage | Exact controlled accounting |
| --- | --- |
| raw ordinary table | purchase `10 @ 10.00 = 100.00 RUB`, no purchase charge; disposal `4 @ 15.00 = 60.00 RUB`; disposal charges `1.00 + 2.00 RUB` |
| current Fact v2 | one purchase, one disposal and two disposal-local transaction-charge facts; exact case binding retained |
| FIFO/source fact | consumed quantity `4`; recognized acquisition cost `40.00 RUB`; disposal proceeds `60.00 RUB`; direct disposal charge `3.00 RUB`; acquisition-commission fact IDs empty |
| operation Tax Model | related expenses `43.00 RUB`; allowable expenses `43.00 RUB`; no demand |
| Category Tax Model | gross `60.00 RUB`; related/allowable `43.00 RUB`; complete exact taxpayer/category/period binding |
| income-group Tax Base | explicit other income, non-taxable income, other expenses and deductions are source-tagged `0.00`; total/taxable income `60.00`; accepted expenses `43.00`; tax base `17.00 RUB` |
| Scope/Package | separate `operation_subject_ref=security-disposal-1` and `taxpayer_scope_ref=synthetic-taxpayer-control`; package `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE` |
| release | `44` released semantic leaves, all owner-bound |
| consumer target | `49` occurrences, `49` with known evidence/authority refs; identical XML bytes on repeat |
| official XSD | `NO_NDFL3_1_033_00_05_20_01.xsd`, SHA-256 `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484`, `xsd_valid=true` |

Representative exact synthetic receipt:

```text
operation_tax_model  22eb0946f140ad45276c1a3ee649f703725d85bf2a5805d91fb96e298a734241
category_tax_model   e6cde089eed8e901c05faac84128f3a09a886750f518cbaeae81053270fca2f8
income_group         82a4249ae279fb805e30757eb33adf1927c548b34fcb5316194d9ed46c58810f
scope_receipt        9c4630511c1e0f4820f86ae47e5f23e3767ac04cb11c79afad7f1e54b2031b17
component_set        90b92e1f3414ba4530a67fa1f7cc9411502a9a0c8d77e78420a0c6316b184c6c
package              171224c94fc071bf3f9ef06cbcbe07aaec4fda412f3940e708a1c7c50c2911e6
semantic_value       7bf0bad3ffda1e0b9d8a53616da572fd2b18b4e379af5981c46eeef42b9156f8
release_receipt      b54a5fbe58229427a00aca19bbbe7e70ab83674d52ea2d3d98fa85015f563c4f
projection_receipt   9dab67907ac5757f635a29e856b54c2b5ab81344705a782b4812eceb2aaa19c7
xml                   5acf1501d4b0948521f30c9a63091cb65bf5a632fea14036dea519a3c3bcac7a
assembly_receipt     33be68d8afe73695dcf71e25d5809e867633cff5191af4d1e001ed16b517ef25
```

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
| missing source party | income-source owner; `SOURCE_EVIDENCE_INSUFFICIENT` |
| missing settlement or budget input | settlement/budget owner; typed missing input |
| changed Category with old group completeness | income-group owner rejects the stale binding |
| direct Category to semantic/XML bypass | semantic owner rejects non-Package input |
| historical G5.35/Gate 3/SQL fallback | monkeypatched traps remain uncalled on positive route |
| changed Category/Package/released/receipt-chain hash | coordinator receipt validator fails closed |

All material stops are machine-readable and produce no complete release or
XML receipt.

## Source delta

Changing only disposal proceeds from `60.00` to `64.00 RUB` changes exactly
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

## Uncomfortable questions

1. No demand disappears: the material commission demand is byte-for-byte
   retained in `demands` and blocks release.
2. Yes, Category can be numerically complete while declaration release must
   stop; the material control proves it.
3. No synthetic input becomes real evidence or a hidden zero. Every zero is an
   explicit source-tagged right-side fact and `real_user_fact=false`.
4. The coordinator copies no calculation or completeness meaning; each stage
   is produced and validated by its existing factory.
5. Taxpayer identity remains independent from the modeled disposal in the
   bridge, Scope receipt and Package validation.
6. One proceeds-cell change produces only the eight justified mapping deltas.
7. Old category/group and receipt-chain evidence fails after mutation.
8. Projection remains representation-only; all 49 occurrences carry existing
   mapping evidence and XSD validation is separate.
9. The official XSD result is reached with Gate 3, historical SQL Gate 4 and
   prebuilt Tax Models all absent; executable traps enforce this.
10. The proof remains synthetic, one-profile, RUB-only, legally unresolved for
    partial acquisition commission, unpersisted, non-downloadable and inactive.

## KISS and stop

No Definition, Package, semantic-input, projection, taxonomy, DB, graph,
workflow, rules engine, LLM adapter or product route was added. The next
smallest step, if separately authorized, is review/qualification of the
inactive composition; activation and legal-gap resolution remain out of scope.
