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
| valid Category from another execution | exact Category member operation hash rejects the join |
| valid Tax Base from another execution | Tax Base owner input binding rejects the Category join |
| valid Package/release/projection tail from another execution | Package-owned Scope and component snapshots reject the join |

All material stops are machine-readable and produce no complete release or
XML receipt.

## Cross-run mix-and-match experiment

Two complete owner-produced executions used the same taxpayer and right-side
context. Run A used disposal proceeds `60.00`; run B used `64.00`. Each hybrid
was evaluated under runtime/store B after recalculating all available stage
hashes, release/target/visual accounting, hash chain and outer receipt hash.

| Hybrid using artifacts from A | Before correction | After correction | Deciding owner/seam |
| --- | --- | --- | --- |
| Operation only | rejected before receipt replay: A disposal Fact ID is absent from live Fact v2 B | rejected | Gate 4/Scope live Fact binding plus Operation source refs |
| Category only | **accepted** | rejected: `operation_to_category` | Category member operation SHA-256 |
| Tax Base only | **accepted** | rejected: `category_to_income_group_tax_base` | Tax Base input binding |
| Package + release + projection tail | **accepted** | rejected: `scope_to_package` | Package Scope receipt snapshot; component snapshots also bind Operation, Category and Tax Base |
| released-value + projection tail | rejected: `gate5_declaration_release_candidate_mismatch` | rejected | semantic release owner binds Package |
| projection tail | rejected: `gate5_active_assembly_projection_input_invalid` | rejected | semantic preparation plus projection owner replay |
| all downstream artifacts | rejected before receipt replay: A disposal Fact ID is absent from live Fact v2 B | rejected | live source binding |

The defect was not invalid owner output. It was missing adjacency comparison
between valid owner outputs. Stage hashes proved only the integrity of isolated
bytes, so a newly resealed receipt could omit provenance of the join.

The minimal correction adds no new artifact type or authority. The composition
validator now compares only fields already produced by existing owners:
Category member hashes, Tax Base input binding, Package Scope snapshot and
Package component snapshots. Package-to-release and release-to-projection
replay remain unchanged.

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

- `38 passed`: active composition, source-bound delta, direct-status rejection,
  exact-stage validation, self-consistent artifact mutation and cross-run
  mix-and-match attacks;
- `124 passed`: combined active composition, Issue #293 bridge, Category,
  Tax Base, Scope, Package, semantic release and projection owner suites;
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
12. Old downstream cannot survive the `60.00 -> 64.00` Fact change: the live
    disposal Fact ID/hash no longer matches Operation A source refs.
13. Scope B cannot be joined to Package A: Package owns and retains the exact
    Scope receipt snapshot, which the composition compares byte-for-byte.
14. Stage hashes prove integrity of individual artifacts, not their common
    execution origin; explicit adjacency comparisons are therefore required.
15. Link owners remain local: Gate 4/Scope for live facts, Category aggregation
    for member Operation, Tax Base for Category input, Package for Scope and
    component snapshots, semantic release for Package, and projection replay
    for released values.

## KISS and stop

No Definition, Package, semantic-input, projection, taxonomy, DB, graph,
workflow, rules engine, LLM adapter or product route was added. The next
smallest step, if separately authorized, is review/qualification of the
inactive composition; activation and legal-gap resolution remain out of scope.

## Universal skill used for the audit

The instruction-only user skill remains outside this repository at
`$HOME/.agents/skills/domain-boundary-change/SKILL.md`.
Its SHA-256 is
`25c3ee26a6c238b682298f3d6462fcf6b40ae39bddf359d8f26870187a35b497`.
The complete text used for this audit is reproduced below for independent
review; the repository does not import or install it.

<details>
<summary>Complete domain-boundary-change SKILL.md</summary>

````markdown
---
name: domain-boundary-change
description: Review or implement changes that connect domains, add bridges/adapters/coordinators/assemblers/composition roots, expose hidden logic, change contract seams, connect an existing path to a new source, or create provenance/completeness/receipt/mutation proofs. Use for cross-domain architecture work; do not use for isolated local fixes that leave boundaries unchanged.
---

# Domain Boundary Change

Keep one owner per meaning and localize cross-domain coupling at an explicit
composition boundary. Prefer the smallest change that preserves existing
contracts; do not introduce a generic engine, registry, graph, DSL, or
framework merely to make the design look uniform.

## Before implementation

Write a compact map for every meaning or transformation crossing the seam:

```text
meaning or transformation
-> existing owner
-> public contract
-> consumer
```

Search for existing behavior, not only matching class names. Inspect schemas
and fields, constants and terminals, emitted structures, tests, behavioral
expectations, and similar private helpers.

Classify each proposed block as exactly one of:

- owner of meaning;
- representation-only adapter;
- call-order coordinator;
- duplicate owner of existing meaning.

If required logic exists behind a private seam, do not copy it silently.
Choose and justify the narrowest viable action:

1. reuse an existing public seam;
2. expose a minimal public seam;
3. extract one narrow owner and move both old and new paths to it;
4. stop with an explicit architectural blocker.

## Boundary rules

A coordinator may order calls, pass typed results between owners, collect a
technical execution receipt, and stop on a blocker or demand.

A coordinator must not repeat business calculations, rebuild semantic inputs
already assembled elsewhere, own mapping/completeness/classification/
provenance, invent defaults, silently repair contradictions, or overwrite an
input without an explicit derivation contract. If it does, it is becoming a
second assembler or meaning owner.

Domain implementations must not import a neighboring domain's implementation.
Let implementations meet in a composition root and pass typed boundary
contracts across the seam. An import of a shared neutral contract is not an
implementation dependency.

Do not require refactoring for aesthetic purity. A temporary MVP seam can be
acceptable when it is explicit, isolated, tested at the real boundary, does
not create competing meaning, and records the residual risk and removal
condition. When tradeoffs are ambiguous, state them instead of imposing one
architecture style.

## Evidence integrity

Keep these distinctions explicit:

- data versus a description or display of data;
- a source binding versus caller-supplied illustration;
- a checksum versus proof of origin;
- a self-consistent receipt versus a receipt bound to owner-validated
  artifacts.

Source/provenance accounting must be derived from the real source owner or
verified against it. Never allow a caller-provided source picture to enter an
evidence receipt unchecked.

Mutation tests must alter the real artifact at the contract seam: for example,
a package, released value set, typed binding, source fact, or projected
artifact. Recomputing surrounding receipt hashes must not make the mutation
valid unless the responsible owner independently accepts the changed artifact.
Changing one hash string without changing the artifact is only a checksum test,
not an integrity proof.

Test the contract between domains, including foreign identity/scope, missing
binding, misbinding, stale owner output, and valid minimal representation-only
adaptation where relevant. Do not treat tests of the new wrapper alone or a
green CI result as proof that ownership remains correct.

## Completion audit

Before declaring completion, compare the new code again with all relevant
existing paths and answer:

1. What existing logic might have been copied?
2. Is there a second owner of any meaning?
3. Does one domain import another domain's implementation?
4. What remains in the coordinator besides call ordering and technical
   accounting?
5. Which inputs are silently added, repaired, or overwritten?
6. Can a caller lie through provenance or receipt fields?
7. Do mutation tests change real artifacts at their owner seams?
8. Can recalculated hashes make a forged artifact appear valid?
9. Do tests prove the cross-domain contract rather than only the wrapper?
10. What is the smallest design that retains one owner and a strict boundary?

If a material violation remains, do not report the work complete. Either fix
it within scope or report the precise blocker, tradeoff, and residual risk.
````

</details>
