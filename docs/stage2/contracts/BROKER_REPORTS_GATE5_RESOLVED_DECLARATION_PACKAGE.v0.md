# Broker Reports Gate 5 Resolved Declaration Package v0

Status: `SUPERSEDED SUPPORTING EVIDENCE`

Implementation status: `INACTIVE G5.30 BOUNDED PROOF`

G5.30 verdict: `PROVEN`

Historical representative package status: `DECLARATION_INCOMPLETE`

> Superseded on 2026-08-11 by
> [Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md).
> The v0 package state model preserves the G5.30/G5.31 historical evidence but
> is not the current authority for empty conditional evidence or completeness
> status naming.

This contract owns only the deterministic boundary between an exact G5.29
Scope Resolution Receipt and a future complete Declaration Model / PROJECT. It
does not calculate tax, resolve applicability, acquire facts, implement a
missing component or emit a target representation.

## Sole owner

The only package construction entrypoint is:

```text
Gate5ResolvedDeclarationPackageRuntimeFactory(...).create().assemble(...)
```

It composes existing authorities:

```text
Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create
Gate5DeclarationScopeResolutionRuntimeFactory(...).create
Gate5TaxPeriodCategoryAggregationRuntimeFactory.create
```

The first owns declaration requirements, the second owns applicability receipt
validation, and the third validates the bounded operation Tax Model snapshot.
The package owner does not replace any of them.

## Exact assembly inputs

```text
exact trusted Definition publication binding
exact G5.29 Scope Resolution Receipt
typed component snapshots bound into that receipt, or exact repository-owned
root components whose family and obligation coverage match that Definition
authenticated ArtifactAccessContext
```

The authenticated context is used only by the unchanged G5.29 receipt owner.
Caller-owned user, case or period identities are not accepted as package
authority.

Assembly performs this fixed sequence:

```text
resolve exact Definition
validate exact scope receipt through G5.29
validate each supplied native snapshot through its existing typed owner
seal snapshots without flattening
derive one row per Definition domain
derive completeness hashes and blockers
```

It does not read Gate 4, SQL, CanonicalArtifact, Gate 3 or ArtifactStore values
directly. Any Gate 4 freshness check remains inside G5.29 receipt validation.

## Sealed package

The package schema is:

```text
broker_reports_gate5_resolved_declaration_package_v0
```

It contains:

```text
exact Definition binding and immutable Definition snapshot
exact Scope Resolution Receipt snapshot
validated native typed component snapshots
Definition-ordered requirement-resolution manifest
Definition-bound completeness receipt
package_sha256
```

Typed component payloads remain in their native contracts. The package adds
only contract identity, owner, Definition-domain binding, content hash,
scope-decision hash and component-binding hash. It does not copy values into a
second declaration DTO.

## Component-set binding

One root domain may bind a set of distinct typed contracts from the exact
Definition component family. The original bounded proof admits one operation
Tax Model through:

```text
Gate5TaxPeriodCategoryAggregationRuntimeFactory
  .create()
  .validate_operation_member(...)
```

The snapshot must already occur as exact `validated_typed_component` evidence
in the G5.29 receipt. This supplies the current case binding without a new
registry or store lookup. The package rejects:

- a contract absent from the Definition domain;
- a snapshot absent from the scope receipt;
- a receipt-bound component whose snapshot is omitted;
- two snapshots for the same domain and contract;
- content, scope-decision or component-binding hash drift.

G5.31 adds four repository-owned exact component validators without rewriting
the immutable Definition or introducing a component registry:

```text
Gate5FilingAndPartyIdentityRuntimeFactory.create
Gate5DeclarationTaxSettlementRuntimeFactory.create
Gate5DeclarationBudgetOutcomeRuntimeFactory.create
Gate5DeclarationIncomeSourcesRuntimeFactory.create
```

These components self-bind only when their sealed owner, exact family and full
ordered obligation set equal the same trusted Definition domain and that exact
G5.29 domain is `APPLICABLE`. The Definition's original component-availability
field remains sealed as publication-time evidence; it is not relabelled to make
the receipt green. Unknown contracts and bounded snapshots still require exact
G5.29 evidence binding.

## Requirement state model

Every exact Definition domain occurs once, in Definition order:

| Package state | Meaning | Terminal for completeness |
| --- | --- | --- |
| `RESOLVED` | scope is `APPLICABLE` and trusted exact root-domain typed semantics cover the Definition obligation set | yes |
| `NOT_APPLICABLE` | G5.29 already proved legitimate non-applicability | yes |
| `SCOPE_UNRESOLVED` | G5.29 applicability is unresolved | no |
| `SCOPE_CONFLICT` | G5.29 applicability evidence conflicts | no |
| `REQUIRED_MISSING` | scope is applicable but exact root-domain semantics are absent | no |

`PARTIAL` is not a terminal state. A `published_bounded` snapshot is preserved
as `bounded_component_available` diagnostic, while the requirement remains
`REQUIRED_MISSING`.

G5.30 copies the scope state and its decision hash. It does not rediscover or
reinterpret applicability.

## Completeness rule

```text
DECLARATION_COMPLETE iff

exact trusted Definition resolved
and exact G5.29 receipt validated
and every Definition domain accounted exactly once
and every row is RESOLVED or NOT_APPLICABLE
and every supplied component is bound, validated and sealed
and no stale, orphan or ambiguous component exists
and every recorded hash matches
```

Otherwise the status is `DECLARATION_INCOMPLETE`.

The completeness receipt is bound to:

```text
definition_sha256
scope_receipt_sha256
scope_binding_sha256
component_set_sha256
resolution_manifest_sha256
receipt_sha256
```

Blockers are ordered only by Definition order. Ordering is diagnostic and adds
no business priority semantics.

## Closed PROJECT input

Native owner validation occurs before sealing. The validation-only factory
path uses `store=None` and can revalidate the sealed package without Gate 4,
ArtifactStore or methodology resolution. It checks the embedded Definition,
scope receipt, snapshots, manifests and hashes only.

Therefore a future PROJECT may consume a `DECLARATION_COMPLETE` package plus
one exact Projection Definition without searching facts, choosing methodology,
calculating tax, asking a user or resolving applicability. No current package
is claimed complete by this proof.

## Representative result

The same synthetic G5.29 case produces:

```text
RESOLVED          0
NOT_APPLICABLE    0
SCOPE_UNRESOLVED  7
SCOPE_CONFLICT    0
REQUIRED_MISSING  4
status            DECLARATION_INCOMPLETE
```

The operation Tax Model is sealed under
`financial_investment_results`, but Definition availability is
`published_bounded`; it is never promoted to exact.

The first blocker derived from Definition order is:

```text
domain   filing_and_party_identity
class    component
state    REQUIRED_MISSING
reason   required_component_missing
```

The privacy-safe machine projection is
[G5.30 package evidence](../../reports/2026-08-11/BROKER_REPORTS_GATE5_RESOLVED_DECLARATION_PACKAGE_G5_30.package.safe.json).

## Fail-closed boundary

Representative checks reject or preserve:

- wrong Definition or Scope Receipt hash;
- foreign case context and mismatched taxpayer component scope;
- missing or extra Definition domain accounting;
- rehashed promotion of scope-unresolved to resolved;
- `NOT_APPLICABLE` as terminal without requiring a component;
- `APPLICABLE` without exact semantics as `REQUIRED_MISSING`;
- bounded-to-exact promotion;
- component payload or binding hash drift;
- orphan and duplicate/ambiguous component input;
- scope conflict without adjudication;
- completeness receipt or package hash drift.

## Primitive and KISS boundary

Package assembly is ordinary deterministic composition between existing
semantic stages. It is not a sixth runtime primitive. No `PACKAGE`,
`COMPLETE`, `ASSEMBLE`, registry, graph, workflow, DB, service or ontology is
added.

## Scope stop and next boundary

G5.30 stops at the sealed package, completeness receipt and first blocker. It
does not implement filing context, taxpayer/signer authority, refund election,
foreign-income models, settlement, Declaration Model projection, PROJECT,
XML/PDF, GUI or activation.

G5.31 exercised this package boundary through the first machine-derived
blockers and stopped before `professional_activity_results`: its
`typed_legal_classification` policy cannot be closed by declarant denial, while
the current bounded case has no authoritative period-wide input or published
classifier for that legal decision. See the
[G5.31 blocker-loop report](../../reports/2026-08-11/BROKER_REPORTS_GATE5_AUTONOMOUS_BLOCKER_CLOSURE_G5_31.report.md).
