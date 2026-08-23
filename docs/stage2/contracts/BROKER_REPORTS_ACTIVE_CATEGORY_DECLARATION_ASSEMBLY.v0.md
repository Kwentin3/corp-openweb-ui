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
-> Gate5DeclarationRightSideAssemblyRuntimeFactory.create
-> Gate5DeclarationScopeResolutionRuntimeFactory.create_current_source_fact_scope
-> Gate5ResolvedDeclarationPackageRuntimeFactory.create_current_source_fact_package
-> Gate5DeclarationSemanticInputRuntimeFactory.create release
-> Gate5FullTargetXmlProjectionRuntimeFactory.create.project_released
-> packaged official 2025 3-NDFL XSD
```

The coordinator accepts source-fact route inputs and explicit synthetic
right-side facts. It does not accept a prebuilt operation/category Tax Model,
Scope receipt, Package, semantic input or released value set.

`Gate5DeclarationRightSideAssemblyRuntimeFactory.create` is the single owner
of the right-side assembly sequence shared by historical G5.35 and this
composition. It delegates tax-base, settlement, income-source, filing, budget
and financial component meaning to their existing factories. Direct
`income_group.taxpayer_status` and `taxpayer.period_status` inputs are
forbidden; taxpayer status is produced only by the residency-evidence owner.

The ordinary Fact v2 marriage is localized here. This composition constructs
and injects the ordinary Gate 4 runtime into Scope, then injects Scope into
Package. The reusable Scope and Package modules import neither
`ordinary_trade_tax_model_bridge` nor
`Gate4OrdinaryTradeCandidateRuntimeFactory`; the bundle therefore keeps its
normal right-domain ordering.

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

## Completeness and artifact-backed mutation binding

Category completeness binds the exact member/category scope. Income-group
completeness binds the exact Category Tax Model plus taxpayer/group context.
Scope, component set, Package, released semantics, projection receipt and XML
are independently hashed and joined by a deterministic receipt chain. The
receipt also embeds the owner-produced operation, Category, income-group,
Scope, Package, released-value and projection artifacts needed for replay.
Validation does not trust a self-consistent outer hash chain: it reopens the
current Fact v2 inputs, reruns the Scope, Package, release and projection
owners, requires the exact stage set, and verifies 44 released leaves, 49
known-owner target occurrences and `xsd_valid=true`.

Individually valid artifacts are not interchangeable between executions. The
composition additionally checks the owner-produced adjacency fields:

```text
live Fact v2 IDs/hashes -> Operation normalized-source-fact refs
Operation SHA-256       -> Category member operation binding
Category SHA-256        -> income-group Tax Base input binding
Scope receipt           -> Package scope receipt snapshot
Operation               -> Package operation component snapshot
Category                -> Package financial component snapshot
Tax Base                -> Package settlement component snapshot
Package                 -> released-value source binding
released values         -> regenerated projection input and target receipt
```

These comparisons establish execution adjacency; stage hashes alone establish
only byte integrity. A receipt assembled from valid outputs of two executions
must fail even when every outer hash, accounting block, hash chain and receipt
hash has been recalculated.

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
12. changed category, Package, released artifact or target receipt even after
    recalculating the outer hash chain;
13. missing, extra or reordered receipt stage;
14. caller-supplied raw visual control;
15. direct `income_group.taxpayer_status` or `taxpayer.period_status`.
16. cross-run Category, Tax Base or Package/release/projection tail assembled
    from a different otherwise-valid execution.

Every material negative is machine-readable, identifies one primary owner and
returns no complete release/XML.

## Source-bound Fact delta and consumer accounting

The visual control is derived from the current Fact v2 owner, not copied from
caller input. Every row carries the exact fact ID/hash, role, normalized value,
source literal and source target; those hashes must equal the Scope binding.
There is no caller-owned `raw_control` field.

Changing only one disposal-proceeds source literal from `60.00` to `64.00`
changes the live Fact v2 value and the
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
