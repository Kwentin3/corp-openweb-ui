# Broker Reports DOC29 Infrastructure Reuse and Durable Contour

Date: 2026-08-05

Status: `BLOCKED_TARGET_HOST_RECOVERY_REQUIRED`

## Outcome

DOC29 found the real deployment and rejected a second storage engine. Broker
canonical belongs in the existing `ArtifactStore` namespace inside
`openwebui_data`; STT contributes a reusable operational pattern, not its
database/schema. The exact 16-document contour, application-consistent backup,
isolated restore, research consumer and six Wave 2 compatibility shadows all
passed in an isolated persistent store. Target admission did not complete: the
first bounded production backfill returned no receipt and the host stopped
serving both application health and SSH banners.

The stop condition is real. No service restart, Compose recreation, target
restore, research target cutover or Wave 2 target shadow was attempted after
health loss. Legacy handoff and every product read path remain unchanged.
Blocker code: `TARGET_HOST_UNRESPONSIVE_DURING_BOUNDED_BACKFILL`.

## Existing STT infrastructure

`stage2-stt` uses a factory-created SQLite ArtifactStore in the named
`stage2_stt_data` volume and reads OpenWebUI data through a read-only mount. The
live database was healthy and held 103 expiring records with inline/redacted
payloads. The reusable pieces are the named-volume, factory, opaque-ref,
scope-check and retention-configuration patterns.

The STT schema is not canonical authority. It has no canonical version graph,
CAS active pointer or chunk model; tenant is nullable/future; its configured
payload directory and rotation/hard-delete worker are not implemented; and the
current backup script omits `stage2_stt_data`.

## Official research

- Open WebUI documents `/app/backend/data` as persistent volume data and says
  to back it up before updates and regularly: [Updating Open WebUI](https://docs.openwebui.com/getting-started/updating/).
- Its official Compose example mounts the named volume at that path:
  [Open WebUI docker-compose.yaml](https://github.com/open-webui/open-webui/blob/main/docker-compose.yaml).
- Docker states that named volumes outlive containers and documents helper-
  container backup/restore: [Docker volumes](https://docs.docker.com/engine/storage/volumes/)
  and [Compose volumes](https://docs.docker.com/reference/compose-file/volumes/).
- SQLite's [Online Backup API](https://www.sqlite.org/backup.html) produces a
  consistent live snapshot; SQLite also warns that an uncontrolled copy during
  a transaction may be inconsistent: [backup/restore while a transaction is active](https://www.sqlite.org/howtocorrupt.html#_backup_or_restore_while_a_transaction_is_active).

This supports either a cold volume snapshot or paused canonical mutations plus
SQLite Online Backup and an immutable referenced-payload snapshot. An
uncontrolled `cp` was not used.

## Deployment and storage decision

The target label, public service, Compose project, deployment root, OpenWebUI
container, STT sidecar, `openwebui_data`, `stage2_stt_data`, mounts and Broker
metadata/payload paths were identified live. Exact SSH/IP material remains
outside Git.

The selected topology is the existing Broker namespace below
`/app/backend/data/broker_reports_gate1`, using:

- `ArtifactStoreFactory` for SQLite metadata and immutable file payloads;
- `CanonicalArtifactStoreFactory` for candidates, versions and activation;
- `CanonicalReaderFactory` for full/partial reads and access checks.

It does not overlap uploads or STT payloads, write into the repository or
`/tmp`, create a second engine, enable global canonical read or change Gate 3.

## Isolated durability and cohort proof

The frozen cohort was exactly 16 documents: 8 PDF, 4 HTML, 2 CSV and 2 XLSX;
15 unique byte hashes and one duplicate-content item. The temporary DOC26 graph
was unavailable, so the rerun was declared in advance: one parser-only pass per
document, zero provider/VLM calls and no legacy handoff change.

Attempt accounting is explicit:

- local attempt 1: external 304-second timeout before any DB/payload/state
  write;
- local attempt 2: PASS in 504.204 seconds;
- production attempt 1: no terminal receipt; no retry.

The successful isolated result was 16/16 validated and active versions, 172
components, 5 chunked and 11 single-payload layouts, 16/16 root matches and
partial reads, zero missing chunks and fail-closed cross-tenant access.

## Backup and restore

The first local proof receipt incorrectly contained zero payload files because
the metadata-only resolver intentionally redacted `payload_ref`; it was
rejected and never restored. The corrected factory/access-checked backup used
SQLite Online Backup plus all 172 referenced immutable canonical payloads
(105,498,864 bytes). Isolated restore through the same reader passed with
16/16 active pointers and roots, 0 missing chunks, 16 partial reads and 0 access
failures.

Before target mutation, a SQLite Online Backup was written outside
`openwebui_data`: 114,364,416 bytes, `integrity_check=ok`, one pre-DOC29 table.
The target restore drill was not run after host health loss. Therefore
`BACKUP_RESTORE=NOT_CONFIRMED` on the target even though the isolated drill
passed.

## Capacity and retention

The canonical write now fails before version reservation when free space is
below 1 GiB or at/below 10%; 20% is warning. A logical artifact is capped at
128 MiB and 4096 components. The isolated cohort contained 105,494,726 logical
canonical bytes, average 6,593,420, p95/largest 47,494,041, maximum 69
components, version amplification 1.0 and evidence amplification 18.528778.

All eight retention classes are contract-accounted. No target rotation ran;
active versions deleted = 0, rollback targets deleted = 0. Post-job target
capacity and orphan state are unknown until console recovery.

## Consumers

`local_pdf_compact_canonical_proof` passed on all eight PDFs with zero
regressions/unresolved comparisons. Flag-off returned explicit
`canonical_read_disabled`, re-enable passed, and silent fallback was zero. It
is not marked migrated on the target because target active pointers are not
verified.

Each of the six Wave 2 consumers received an explicit read-only compatibility
contract and completed three stable 16-document isolated runs. Every consumer
reported 48 canonical OK reads, fail-closed access, zero regression,
unresolved comparison, provider call or product side effect. Consumers
migrated = 0. Target shadow was not run.

## Target incident and exact recovery request

The one-off immutable job image was built from a recorded 22,997,504-byte
context and verified against the 16/15 cohort accounting. A pre-change backup
passed. The bounded target parser job then exceeded its 20-minute internal
window and 1304-second control-session limit without a receipt. HTTPS health
failed and SSH accepted TCP but did not issue a banner. Three health windows
failed; two accounting sessions and one exact-container stop attempt never
reached the daemon.

Required recovery authority/action:

1. use the VPS/provider console to stop only
   `broker-reports-doc29-prepare` if it is still running;
2. verify `openwebui` health and Broker/STT SQLite integrity;
3. collect read-only counts for DOC29 versions, active pointers and components,
   plus post-job free capacity;
4. compare with the pre-change snapshot and choose retain or restore;
5. do not retry until an explicit CPU/memory/resource-limited job policy is
   approved.

## Terminal accounting and decision

Final focused tests: 34 passed, 0 failed in 7.36 seconds (after an earlier
27-pass contour/lifecycle run). Isolated prepare, reader,
backup, restore, research and Wave 2 shadows passed. Target pre-change backup
passed. Target prepare, restart, recreation and restore did not close.

```text
DOC29_PROGRAM = BLOCKED
STT_INFRASTRUCTURE_REUSE = PARTIAL
TARGET_DEPLOYMENT = IDENTIFIED
DURABLE_CANONICAL_STORE = PARTIAL
BACKUP_RESTORE = NOT_CONFIRMED
APPROVED_COHORT = PARTIAL
RESEARCH_CONSUMER = BLOCKED
WAVE2_SHADOW = PARTIAL
WAVE2_MIGRATION_READINESS = BLOCKED
PRIMARY_PRODUCT_CUTOVER = NOT_PERFORMED
LEGACY_HANDOFF = RETAINED
GATE3 = NOT_STARTED
```

A separate Wave 2 cutover goal is not authorized. The next goal, if any, must
be target recovery and bounded durability accounting only.
