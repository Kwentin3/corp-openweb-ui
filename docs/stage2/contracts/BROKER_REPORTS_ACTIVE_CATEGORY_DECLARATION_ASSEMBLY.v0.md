# Broker Reports Active Category Declaration Assembly v0

Status: `CURRENT SUPPORTING CONTRACT`

Issue: `#295`

Implementation: `INACTIVE / SHADOW / SYNTHETIC CONTROL ONLY`

## Boundary

The sole coordinator is:

```text
ActiveCategoryDeclarationAssemblyRuntimeFactory.create
```

It owns ordering and accounting only. Meaning remains with the existing
fact, FIFO, Tax Model, category, income-group, component, Full Definition,
Scope, Package, release, projection and official-XSD owners.

The exact route is:

```text
OrdinaryTradeTaxModelBridgeRuntimeFactory.create
-> Gate5IncomeGroupTaxBaseRuntimeFactory.create
-> existing settlement and declaration component factories
-> Gate5DeclarationScopeResolutionRuntimeFactory.create_current_source_fact_scope
-> Gate5ResolvedDeclarationPackageRuntimeFactory.create_current_source_fact_package
-> Gate5DeclarationSemanticInputRuntimeFactory.create release
-> Gate5FullTargetXmlProjectionRuntimeFactory.create.project_released
-> packaged official 2025 3-NDFL XSD
```

The coordinator accepts source-fact route inputs and explicit synthetic
right-side facts. It does not accept a prebuilt operation/category Tax Model,
Scope receipt, Package, semantic input or released value set.

## Identity and source binding

The Issue #293 binding remains authoritative for the relationship:

```text
operation_subject_ref -> modeled SECURITY_DISPOSAL subject
taxpayer_scope_ref    -> declaration/category taxpayer scope
provenance.source_kind = user_verified_fact
```

The two identities must differ in the positive control and are never equated.
The current-Fact Scope receipt embeds that typed binding and exact Fact v2
hashes. Its source boundary is
`Gate4OrdinaryTradeCandidateRuntimeFactory.create`, with Gate 3 explicitly
`not_executed`. Package validation rechecks the operation subject against the
operation side of the binding and the scope against the taxpayer side.

Historical `Gate5DeclarationScopeResolutionRuntimeFactory.create` and
`Gate5ResolvedDeclarationPackageRuntimeFactory.create` remain compatible and
are not fallbacks for this route.

## Terminals

```text
ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN
BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
```

A positive terminal requires zero blockers and zero demands before release,
44 released semantic leaves, 49 consumer target occurrences, successful
packaged XSD validation and byte-identical XML for identical inputs.

A bounded terminal retains the exact upstream bridge demand or emits one
typed owner-bound blocker. Material stops contain neither released values nor
a target receipt.

## Commission boundary

The clean control has one purchase and one partial disposal, no acquisition
commission, and an explicitly source-tagged disposal charge. The material
control has an acquisition commission and must retain:

```text
required_input            partial_acquisition_commission_allocation
gap_owner_classification  LEGAL_INTERPRETATION_REQUIRED
```

No proportional formula, first-disposal allocation or silent exclusion is
authorized.

## Completeness and mutation binding

Category completeness binds the exact member/category scope. Income-group
completeness binds the exact Category Tax Model plus taxpayer/group context.
Scope, component set, Package, released semantics, projection receipt and XML
are independently hashed and joined by a deterministic receipt chain.

The executable proof rejects:

1. material acquisition commission;
2. missing, foreign or misbound taxpayer identity;
3. absent or stale category completeness;
4. absent or stale income-group completeness;
5. missing organized-market/applicability evidence;
6. missing residency or filing identity;
7. missing source-party/income-source evidence;
8. missing settlement or budget input;
9. changed Category Tax Model with old downstream completeness;
10. direct Category Tax Model to semantic/XML bypass;
11. historical G5.35 Gate 3 or SQL-backed Gate 4 fallback;
12. changed category, package, release or receipt-chain binding.

Every material negative is machine-readable, identifies one primary owner and
returns no complete release/XML.

## Source delta and consumer accounting

Changing only one disposal-proceeds cell from the bounded control changes the
operation, Category, income-group, Package, release and XML hashes. Under the
existing G5.45 profile, the exact changed mapping IDs are:

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

All other target occurrence hashes remain unchanged. Projection performs only
mapping, formatting, encoding, repetition, placement, serialization and XSD
validation.

## Safety stop

The route is inactive, shadow-only, unpersisted and non-downloadable. Provider
and LLM calls, Gate 3 execution, historical SQL-backed Gate 4 reads, downstream
Canonical/Source Observation reads and caller-supplied Tax Models are zero.
It is not filing readiness, legal correctness, real-taxpayer completeness,
cross-broker evidence or product activation.
