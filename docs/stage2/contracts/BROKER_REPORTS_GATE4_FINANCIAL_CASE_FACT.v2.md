# Broker Reports Gate 4 Financial Case Fact v2

Status: `CURRENT CONTRACT`

Goal: `G5.40C`

Date: 2026-08-12

Updated: 2026-08-21 (ordinary-trade producer compatibility)

## Purpose

`Gate4FinancialCaseFactV2` is one deterministic normalized source fact in one
trusted case/chat scope:

```text
historical rollback producer:
  current validated FinancialAnnotationsV2
  + exact active CanonicalArtifactV1

active ordinary-trade producer:
  validated ordinary-trade runtime projection
  + exact Source Observation / Canonical-cell lineage

+ trusted ArtifactAccessContext
-> deterministic Gate4FinancialCaseFactV2
```

The normative shape is
[`BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.schema.json`](./BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.schema.json).
The schema identity and `fact_id` algorithm remain owned by
[`gate4_financial_case_materialization.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_materialization.py).
The historical Gate 3-backed producer is
`Gate4FinancialCaseMaterializerFactory.create`. The active ordinary-trade
producer is the narrow compatibility adapter
[`Gate4OrdinaryTradeCandidateRuntimeFactory.create`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate4_ordinary_trade_candidate.py).
The adapter may only validate and project already compiled runtime records into
this exact shape; it is not a second fact schema or meaning authority.

## V2 additions

V2 retains the v1 case, Gate 3, target, role and completeness fields and adds:

```text
semantic_kind = normalized_source_fact
semantic_binding:
  dictionary: authority_id + semantic_version
  role_pack: authority_id + semantic_version
```

The binding is copied from the immutable current upstream projection and
participates in `fact_id`. On the historical path that projection is a
`FinancialAnnotationsV2` sidecar. On the active ordinary-trade path it is the
immutable `broker_reports_ordinary_trade_runtime_projection_v5` artifact with
exact Canonical lineage and mapping authority identity.

`gate3_binding` and its
`broker_reports_financial_annotations_v2` discriminator are retained field
names required by the published v2 schema. They are compatibility syntax, not
evidence that current Gate 3 executed. Their ordinary-route
`financial_annotations_artifact_id` value is the ordinary projection artifact
ID. Consumers must treat the envelope as upstream provenance and must not infer
the producer from its historical name.

## Allowed normalization

Gate 4 normalizes only unambiguous source syntax. Valid exact `YYYY-MM-DD` and
`DD.MM.YYYY` calendar dates become ISO dates; other non-empty date literals are
preserved unchanged. Decimal roles accept plain dot/comma decimals and the
unambiguous grouped forms used by the frozen broker sources: spaces as grouping,
comma grouping with dot decimal, or dot grouping with comma decimal. Any other
non-empty decimal literal is preserved unchanged for downstream sufficiency
validation. Gate 4 must retain the exact `source_literal`, canonical target and
optional exact substring. Normalized representation does not prove event
identity, economic relation, completeness or tax eligibility.

Missing roles remain explicit and produce `role_incomplete`. Sparse Gate 3
omission remains a non-claim.

`source_wording`, when an explicitly selected published Role Pack requires it,
is preserved as a non-empty literal exactly like other non-computed text roles.
It is evidence for the already selected source meaning, not a second label,
tax conclusion or relation authority. The current default Role Pack remains
`3.0.0`; the G5.91 `3.1.0` candidate is explicit and inactive.

## Atomic source-evidence admission

Each materialized `Gate4FinancialCaseFactV2` represents exactly one
unambiguously addressable source assertion inherited from its validated
upstream target. For the active ordinary route, one runtime record must bind
one `RUNTIME_READY` Source Observation and exact Canonical row/cells. A broad
presence observation over a target containing
multiple indistinguishable occurrences is not an atomic financial fact and is
not materializable. It may remain upstream as a discovery or recovery signal
only when a named upstream consumer exists.

Atomicity and role completeness are independent. An exact source row with
missing amount or currency remains a legitimate `role_incomplete` fact; a
coarse multi-operation target does not become a fact merely because a
financial type is present somewhere inside it. Gate 4 does not inspect the PDF
or choose a narrower row: the selected source-semantic producer and exact
Canonical targeting must establish this boundary before Fact v2 admission.

The deterministic minimum guard uses existing Canonical structure rather than
a new ontology. Exact `table_row`, `table_cell` and `list_item` targets remain
materializable when roles are missing. A `node` is materializable when its
source-visible content is one line, or when a bound `exact_text` occurs exactly
once inside its allowed Canonical target and therefore supplies an unambiguous
literal anchor. A multi-line node without such an anchor is
`non_atomic_region_presence_only`; merely binding a repeated literal does not
make it atomic. This is a structure-only addressability test, not financial
interpretation. Gate 4 never reparses the PDF or splits the region.

## Forbidden behavior

The materializer and SQL cache must not:

- choose or repair a label, mapping or role;
- materialize a non-atomic presence observation as one transaction fact;
- parse broker-specific formats;
- calculate, aggregate or reconcile detail and totals;
- infer a relation between facts;
- allocate commissions or acquisition cost;
- apply methodology, tax or declaration semantics;
- accept caller-provided tenant/case identity or bypass the existing factories.

The SQL representation is a deletable JSON cache of the exact v2 fact. It is
not a meaning authority and cannot add columns or queries that imply relations.

## Identity and compatibility

`fact_id` is the first 32 lowercase hex characters of a canonical SHA-256 over
the v2 schema identity, trusted case binding, exact upstream compatibility binding,
semantic kind/binding, annotation target identity and financial type. The same
inputs rebuild the same ID; changing semantic authority changes the ID.

Fact v1 remains historical and readable where explicitly requested. Current
materialization and Gate 4 SQL/cache reads produce v2 only.

See [Source-Fact Domain Boundaries v1](./BROKER_REPORTS_SOURCE_FACT_DOMAIN_BOUNDARIES.v1.md)
for the complete Gate 2-5 responsibility map.
