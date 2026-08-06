# Broker Reports Canonical Durable Storage Runbook

Status: `CURRENT`

Date: 2026-08-05

## Approved implementation boundary

Use the existing `ArtifactStoreFactory` with the SQLite metadata and file
payload adapters. In the declared compose deployment, both paths must remain
below the existing `openwebui_data:/app/backend/data` mount:

```text
/app/backend/data/broker_reports_gate1/artifacts.sqlite3
/app/backend/data/broker_reports_gate1/payloads
```

Do not create a second storage engine, a workspace-local durable store, or a
temporary-volume substitute. `SqliteArtifactStoreAdapter._ensure_schema`
remains the schema owner; callers must use factories and pass the trusted
tenant/case access context.

## Deployment gate

Before the first durable write, record safe evidence for:

1. approved target deployment and operator authority;
2. mounted persistent volume and available capacity threshold;
3. metadata and payload writability under the service identity;
4. cross-process read of a committed candidate;
5. controlled service restart preserving candidate, active pointer, root hash,
   chunks, and access denial outside the owning context;
6. backup and restore integrity receipt;
7. retention-worker ownership and fail-closed configuration.

Any missing item blocks backfill, activation, new-upload durable shadow,
research cutover, and Wave 2 shadow. Candidate configuration alone is not
durability proof.

## Runtime admission

Historical executions are audit evidence, not proof of today's target. Before
each authorized migration, perform the deployment gates above against the
current exact image/config/volume and record terminal counts. A missing receipt,
OOM, partial state or host-health loss blocks continuation and does not permit a
retry or resource-policy change. Monolithic cohort jobs remain forbidden.
