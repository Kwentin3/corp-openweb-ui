# Broker Reports Gate 3 NDFL Case Readiness v1

Status: `COMPLETED_INACTIVE`

Date: 2026-08-07

## Purpose

G3.6 exposes one private, deterministic `NDFL` case read model. It derives
current readiness from existing case-scoped source records, active canonical
versions and current immutable `FinancialAnnotationsV2` sidecars. Historical
V1 label-only sidecars are retained but do not satisfy current role-ready
state. The snapshot is not
persisted and is recomputed for every read.

The sole entrypoint is `Gate3NdflCaseReadinessFactory.create(context)`. The
authenticated `ArtifactAccessContext` is the only origin of user, case and
workspace identity; no separate tenant or case argument is accepted.

## State rules

- a document is Gate 2 ready only when it has a current active canonical
  version;
- it is Gate 3 ready only when a validated readable annotation sidecar binds
  that exact active canonical version;
- a sidecar for a superseded canonical version is stale, not ready;
- blocked, expired, purge-pending, purged, inaccessible or malformed sidecars
  never count as ready;
- when several current sidecars exist, the latest immutable record by
  `(created_at, artifact_id)` is selected deterministically;
- zero annotations is valid when the complete sidecar itself is valid;
- readiness aggregates documents but never combines their labeling contexts.

`PREPARE_DECLARATION` is allowed only when at least one document exists and
every document is Gate 3 ready. This is a fail-closed handoff permission, not a
Gate 4 implementation.

## Relationship to Gate 3 acceptance

This read model is downstream integration evidence, not an acceptance owner
for the Gate 3 semantic-labeling mechanism. An incomplete current case proves
that incomplete state and handoff permissions are reported honestly; it does
not make a working per-document Gate 3 system unready. Gate 3 system acceptance
is based on complete representative document paths and semantic quality.

## Non-goals

- no workflow database, event log or graph;
- no persisted readiness state;
- no LLM-owned completion decision;
- no document labeling or cross-document context;
- no financial meaning, reconciliation, tax calculation or declaration;
- no Gate 4 execution or product activation.

The closed output schema is
[Gate 3 NDFL Case Readiness v1](./BROKER_REPORTS_GATE3_NDFL_CASE_READINESS.v1.schema.json).
