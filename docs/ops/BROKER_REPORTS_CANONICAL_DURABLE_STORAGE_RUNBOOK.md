# Broker Reports Canonical Durable Storage Runbook

Status: `CURRENT_RUNTIME_PARTIAL_NOT_DURABLE`

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

## DOC29 current status

The target is identified and was accessible through the repository-local
operator route. Live inspection confirmed the `compose` project,
`openwebui_data:/app/backend/data`, `stage2_stt_data:/data/stage2-stt`, the
Broker SQLite/payload paths and adequate pre-run capacity. A pre-change online
SQLite snapshot completed outside the volume with `integrity_check=ok`.

The exact 16-document path passed in an isolated persistent store: 16 active
pointers, 172 components, 16 partial reads, matching roots and fail-closed
cross-tenant access. The first target job was later proven OOM-killed by the
host and auto-removed. Read-only recovery accounting found zero DOC29
canonical versions or payload files, both SQLite stores healthy and the
Broker logical row set equal to its pre-change snapshot. Recovery selected
`RETAIN`; the monolithic job remains forbidden.

Current DOC29 result: `ACCOUNTED_ZERO_CANONICAL_WRITES_RETAIN`.

## DOC30 recovery attempt

SSH recovered at `2026-08-05T16:29:50Z`. DOC30 added a closed-world,
factory-routed, one-document entrypoint with durable checkpoints and receipts.
Both canaries passed and 8 target versions were published with matching roots,
16 verified components, zero missing chunks and fail-closed cross-tenant
access. Document 7, an XLSX, then hit the frozen 1 GiB memory cgroup and exited
137. It left zero persisted partial state. The mandatory OOM stop prevented a
retry, the remaining seven documents, restart/recreation and backup/restore.
Current result: `PARTIAL_8_OF_16_TARGET_DURABILITY_NOT_CONFIRMED`.
