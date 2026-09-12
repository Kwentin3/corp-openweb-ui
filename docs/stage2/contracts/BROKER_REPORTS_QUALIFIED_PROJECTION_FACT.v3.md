# Broker Reports Qualified Projection Fact v3

Status: `ACTIVE_ORDINARY_TRADE_ROUTE`

## Purpose

`broker_reports_qualified_projection_fact_v3` is the only financial-fact
contract between the active ordinary-trade projection and deterministic Gate 5
consumers. It carries no source document content and performs no semantic
interpretation.

## Ownership and flow

```text
CanonicalArtifactV1
  -> packaged qualified mapping or qualified mapping case
  -> ordinary-trade projection
  -> QualifiedProjectionFactV3
  -> deterministic Gate 5 / tax XML assembly
```

`Gate4OrdinaryTradeCandidateRuntimeFactory.create` owns construction from the
persisted qualified projection. `Gate5DeterministicSourceFactConsumptionRuntime`
only receives the injected `list_facts(context)` reader port. It neither reads
Canonical nor imports a Gate 3 or V2 owner.

## Required binding

Each fact contains an identity-derived `fact_id`, `case_binding`, financial
type, status, roles and annotation target. Its `qualified_projection_binding`
must contain exactly:

- projection artifact id;
- Canonical document, version and root hash;
- source observation id;
- qualified semantic mapping-case reference, or `null` only when the
  dictionary authority is a packaged `ordinary_trade_schema_mapping:otmap_*`
  mapping;
- runtime-record id.

Changing any bound item or a role invalidates the fact identity. A packaged
mapping is still bound by its exact qualified mapping authority, Canonical
binding, observation and runtime record; `null` never authorizes invented
case provenance. Missing or malformed data fails closed.

## Historical boundary

`FinancialAnnotationsV2`, `Gate4FinancialCaseFactV2` and `gate3_binding` are
retained only for the explicit historical rollback route. They are not a
compatibility input, fallback or alias for this active ordinary-trade route.
