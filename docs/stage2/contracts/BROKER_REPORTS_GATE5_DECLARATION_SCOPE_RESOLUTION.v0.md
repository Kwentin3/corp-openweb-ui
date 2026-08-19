# Broker Reports Gate 5 Declaration Scope Resolution v0

Status: `SUPERSEDED SUPPORTING EVIDENCE`

Implementation status: `INACTIVE G5.29 BOUNDED PROOF`

G5.29 verdict: `PROVEN`

Historical receipt status for the representative case: `SCOPE_INCOMPLETE`

> Superseded on 2026-08-11 by
> [Supplied-case Completeness v1](./BROKER_REPORTS_GATE5_SUPPLIED_CASE_COMPLETENESS.v1.md).
> The v0 interpretation incorrectly treated empty conditional evidence as a
> universal unresolved taxpayer-period question. Retain this file only as
> historical evidence for G5.29 and the G5.31 research scar.

This contract owns the smallest deterministic case-time RESOLVE boundary over
the trusted G5.28B Full Declaration Definition. It does not own a complete
Declaration Model, component completeness, tax calculation, PROJECT, XML/PDF,
adjudication, GUI or product activation.

## Sole owner

```text
Gate5DeclarationScopeResolutionRuntimeFactory.create
```

The factory composes only existing authorities:

```text
Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create
Gate4FinancialCaseRuntimeFactory.create
Gate5TaxPeriodCategoryAggregationRuntimeFactory.create
ArtifactResolver / injected ArtifactStore
```

G5.28B remains the sole owner of domain IDs, order, applicability policies,
allowed authority classes and expected component contracts. The scope runtime
contains no copied domain or policy list. The trusted authority's additive
`resolve_for_scope` method exposes the already reviewed, hash-pinned
applicability audit together with the exact published Definition.

## Exact input boundary

The Definition reference is the complete trusted publication tuple:

```text
definition_id      ru_3ndfl_2025_root_declaration
definition_version 2026-08-10.1
definition_sha256  8d2a4ad11c766a5d346f4840b033d08e6c854fe07e336836541f9437ea8bf19d
```

The caller supplies only an opaque declaration-scope reference, an opaque
taxpayer-scope reference and the tax period. Authenticated application user,
case and normalization-run identities are derived exclusively from
`ArtifactAccessContext` and included in the scope hash. Application user
identity is not promoted to taxpayer or signer identity.

Financial data is read only through:

```text
Gate4FinancialCaseRuntimeFactory(...).create().read_case(context=...)
```

The receipt binds the current Gate 4 source and fact hashes. SQL, Gate 3
targets, CanonicalArtifact and source documents are not read by the resolver.

## Deterministic accountant

The runtime materializes exactly one row for every trusted Definition domain,
in Definition order, with one of:

```text
APPLICABLE
NOT_APPLICABLE
UNRESOLVED
CONFLICT
```

Resolution is automatic first:

1. `definition_mandatory` domains become `APPLICABLE` through `RESOLVE`.
2. An already produced, same-scope published typed component may provide
   positive evidence after validation by its existing owner. The bounded proof
   accepts the G5.13 operation Tax Model through the G5.14 validator and checks
   that every referenced Financial Case fact is current and value-exact.
3. Existing case-bound declarant assertions are loaded only through
   `ArtifactResolver` and accepted only when the Definition policy includes
   `user_case_evidence`.
4. No evidence produces `UNRESOLVED`, never a negative decision.
5. Opposed allowed evidence produces `CONFLICT`; no source priority or
   last-write-wins rule exists.

`CASE_COMPLETE_FOR_CURRENT_INPUT_SET` is retained only as Gate 4 technical
evidence. It never means that a taxpayer had no other income, activity,
property, gifts, deductions or elections during the year.

## Human residual

If there is no conflict, the resolver selects the first Definition-ordered
`UNRESOLVED` domain whose policy allows `user_case_evidence` and whose policy
is one of the two bounded assertion classes:

```text
elective_claim
factual_occurrence
```

The returned request binds Definition hash, scope hash, domain, policy, tax
period, semantic meaning and exact `yes|no` answer contract. A product-facing
model may later phrase that context in plain language, but cannot select the
domain, policy, sufficient evidence or final state.

`submit_human_answer` accepts only that exact request from a validated receipt,
maps the structured answer deterministically to positive/negative polarity and
stores one private case artifact under existing ArtifactStore lifecycle and
ACL rules. A `no` answer has no universal authority. Typed-legal-classification
domains do not expose this human route.

## Receipt

The receipt schema is:

```text
broker_reports_gate5_declaration_scope_resolution_receipt_v0
```

It contains:

- exact trusted Definition publication binding;
- exact authenticated user/case/run, taxpayer and period scope binding;
- Gate 4 boundary plus source/fact hashes;
- all Definition domain rows, states, routes, evidence bindings and decision
  hashes;
- unresolved and conflict lists;
- at most one policy-authorized human residual;
- the first Definition-derived downstream component blocker;
- one canonical receipt hash.

`SCOPE_RESOLVED` requires every domain to be `APPLICABLE` or evidence-bound
`NOT_APPLICABLE`, with no conflict. Otherwise the honest result is
`SCOPE_INCOMPLETE`.

## Scope is not component completeness

`APPLICABLE` says only that a domain belongs to the declaration scope. The
resolver separately reports the first applicable domain whose expected
component is missing or bounded-only. It does not create that component.

For the representative proof the first downstream blocker is derived as:

```text
domain_id               filing_and_party_identity
component_availability  missing
reason                  required_component_missing
```

This does not make the mandatory domain `UNRESOLVED`: its applicability is
Definition-owned, while its required filing semantics remain incomplete.

## Representative result

The synthetic 2025 case contains one current Gate 4 securities-disposal fact
and one existing validated G5.13 operation component. The trusted Definition
produces `11/11` domain rows:

```text
APPLICABLE      4
NOT_APPLICABLE  0
UNRESOLVED      7
CONFLICT        0
status          SCOPE_INCOMPLETE
```

Automatic positive evidence resolves `financial_investment_results`; the
three mandatory domains resolve from the Definition. Current-input absence
does not resolve the other seven conditional domains. The first permitted
human residual is Definition-derived `refundable_amount_disposal` under
`elective_claim`. Separate tests prove policy-bound `no`, opposed-answer
`CONFLICT`, foreign-user denial and the absence of human authority for a typed
legal classification domain.

The privacy-safe receipt projection is
[G5.29 receipt evidence](../../reports/2026-08-11/BROKER_REPORTS_GATE5_DECLARATION_SCOPE_RESOLUTION_G5_29.receipt.safe.json).

## Fail-closed boundary

Representative checks reject or contain:

- wrong Definition ID/version/hash and wrong tax period;
- foreign user/case/run assertion access;
- unknown or policy-incompatible component contracts;
- component payload hash drift and stale Gate 4 fact bindings;
- missing, extra or duplicate Definition domain rows;
- incompatible negative evidence;
- positive/negative conflict as `CONFLICT`;
- decision, scope, Gate 4 or receipt hash drift.

## Primitive and KISS boundary

The runtime uses the existing families only:

```text
RESOLVE  root accountant and mandatory domains
EXECUTE  provenance of an already validated typed classification/component
ACQUIRE  one policy-authorized residual assertion
```

AGGREGATE and PROJECT are downstream. No `SCOPE`, `DECIDE` or `INTERVIEW`
primitive was added. There is one owner module, one private assertion shape and
one ArtifactStore allowlist entry; there is no new DB/table, registry, workflow,
questionnaire, rules DSL, ontology or service.

## Scope stop and next boundary

G5.29 stops at the Scope Resolution Receipt and the first downstream blocker.
It does not implement filing context, taxpayer/signer authority, missing Tax
Models, settlement, complete Declaration Model, package completeness, PROJECT,
XML/PDF or activation.

G5.30 is governed by the separate
[Resolved Declaration Package v0](./BROKER_REPORTS_GATE5_RESOLVED_DECLARATION_PACKAGE.v0.md)
contract. It consumes this exact receipt and returns
`DECLARATION_INCOMPLETE` with `filing_and_party_identity` as the first
Definition-ordered component blocker. This G5.29 owner still does not close
that gap.
