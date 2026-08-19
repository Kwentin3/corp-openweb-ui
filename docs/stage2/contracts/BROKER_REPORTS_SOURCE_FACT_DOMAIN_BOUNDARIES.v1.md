# Broker Reports Source-Fact Domain Boundaries v1

Status: `CURRENT CONTRACT`

Goal: `G5.40C`; clarified by `G5.40D`

Date: 2026-08-12

Updated: 2026-08-13

## Governing rule

Normalization may change representation, never source meaning. Source
granularity is the semantic ceiling of Gates 2-4. A target, row, section or
document may be retained as source-authored context, but proximity and shared
attributes do not create an economic relation.

Every value crossing this boundary belongs to exactly one class:

| Class | Meaning | Earliest owner |
| --- | --- | --- |
| source structure | page, region, row, cell, order and exact locator retained from input | Canonical Artifact |
| source fact | a financial observation directly asserted by one exact source target | Gate 3 dictionary and Role Pack |
| source-authored context | a relation or aggregate scope explicitly represented by the same source target | Gate 3 label plus canonical target |
| normalized source fact | deterministic typed representation of a source literal without new meaning | Gate 4 Fact |
| methodology-derived value | calculation, eligibility, allocation, reconciliation or declaration meaning | Gate 5 published methodology |
| unsupported inference | meaning not proved by source structure or an authorized methodology input | no producer; fail closed |

## Domain map

| Domain | Receives | May assert or normalize | Must preserve | Must not infer | Produces | Consumer | Failure behavior |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Canonical Artifact | uploaded source bytes and format-specific extraction | structural nodes, tables, rows, cells, literals and provenance | exact source accounting and target identity | financial meaning, event identity, aggregation or tax meaning | immutable `CanonicalArtifactV1` | Gate 3 | incomplete/invalid canonical fails activation |
| Gate 3 labeling | exact, atomically addressable canonical targets plus current dictionary/Role Pack | one sparse source fact label; literal role bindings; only source-authored context present in the exact target | canonical target, literals, missing roles and semantic authority identity | converting a coarse presence observation into one transaction; reconciliation, calculation, hidden relations, FIFO, commission allocation or aggregate decomposition | immutable `FinancialAnnotationsV2` | Gate 4 | reject a non-atomic proposal, reject the proposal otherwise, or retain explicit `missing` |
| Gate 4 materialization | current atomic sidecar, exact active canonical and trusted case context | typed date/decimal representation under the exact source semantic authority | one addressable source assertion, source literal, target, sidecar/canonical binding and dictionary/Role Pack versions | materializing a broad presence claim; label/role choice, detail-total reconciliation, economic relations, methodology or tax meaning | `Gate4FinancialCaseFactV2` and rebuildable SQL projection | Gate 5 | reject stale/misbound/non-atomic input; keep atomically targeted role-incomplete facts visible |
| Gate 5 methodology | current Gate 4 facts plus explicit same-run user/methodology inputs | calculations and declaration semantics allowed by one published typed methodology | all source and user provenance; exact completeness boundary | missing acquisition roles/quantity, expense evidence, scope completeness or tax facts | typed Tax Models, declaration semantics and XML projections | declaration consumer | missing methodology input returns a typed blocker and no downstream artifact |

The LLM boundary ends when the strict `FinancialAnnotationsV2` proposal has
passed deterministic validation. Gate 4, SQL materialization, Gate 5
calculation and declaration projection are ordinary deterministic code.

`ONE G4 FINANCIAL FACT -> ONE UNAMBIGUOUSLY ADDRESSABLE SOURCE ASSERTION`.
This is a structural admission law, not a requirement that Canonical know
financial meaning. Presence in a coarse region is a recovery signal, not a
transaction. An exact but source-incomplete assertion remains materializable
with explicit missing roles.

## Detail and aggregate observations

Detail and aggregate observations are independent source facts. For example,
two commission details of `10` and `15` and a source-authored commission total
of `30` remain three facts. The same rule applies to withheld-tax detail and
total observations.

Gates 3 and 4 must not:

- calculate a total from detail facts;
- compare, reconcile or repair a source total;
- replace a total with details or details with a total;
- allocate an aggregate to operations, assets or lots;
- create membership or economic-relation edges.

An authorized Gate 5 methodology may consume both only if its typed input
contract explicitly defines the reconciliation or allocation and obtains every
required completeness assertion.

## Economic relations

An exact relation may cross the source-fact boundary only when the source
explicitly authors it in the same accepted target, or when a downstream
published methodology consumes explicit relation evidence. Asset equality,
quantity equality, dates, ordering, page membership, row proximity and literal
equality are evidence features, not relation identity.

The former `Gate5RelatedSecuritiesEventsRuntime` inferred purchase-to-disposal
identity from those features and is removed. Existing declaration replay uses
explicit supplemental acquisition-cost and expense facts; it does not require
that relation owner. When those values are absent, the consumer fails closed at
`gate5_tax_model_inputs_not_satisfied`.

## Versioning and compatibility

- Dictionary `1.0.0`, Role Pack `1.0.0` and Gate 4 Fact v1 remain readable
  historical contracts.
- Dictionary `2.0.0` and Role Pack `3.0.0` are the current source-fact
  authorities. Role Pack `3.0.0` narrows `asset` to a source-authored code or
  other unambiguous identifier without changing financial-label meaning.
- Gate 4 Fact v2 carries `semantic_kind=normalized_source_fact` and the exact
  dictionary/Role Pack identities used upstream.
- A version upgrade creates a new immutable package resource and hash pin. It
  never rewrites a historical identity.

## Remaining explicit gap

Partial acquisition-cost attribution and commission allocation remain a
methodology gap. This contract neither solves it nor establishes that an
economic relation is required to solve it. A consumer that requires those
meanings must provide an authorized typed methodology with its exact required
inputs, or stop without Tax Model, declaration or XML. G5.40D separately proves
date-ordered FIFO acquisition-cost consumption for fully available purchase
and disposal facts without creating or persisting a purchase-to-sale relation.
