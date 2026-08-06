# Broker Reports DOC28 Gate 2 Durable Contour

Date: 2026-08-05

Status: `BLOCKED`

DOC28 stopped at the mandatory deployment gate. No durable write, activation,
provider/parser rerun, product read, research cutover or Wave 2 shadow occurred.

## 1. Durable backend

The only admissible candidate is the existing ArtifactStore using SQLite
metadata and file payloads below the compose `openwebui_data` mount. No second
storage engine was created.

## 2. Why it is not yet durable operationally

The repository declares the volume and the pipe defaults are inside its mount,
but the target volume/container are not accessible, the available Docker
context has no `openwebui_data`, and repository policy does not authorize VPS
access. Candidate configuration is not restart evidence.

## 3. Restart persistence

Not tested. Cross-process, service-restart, active-pointer and chunk-reference
persistence remain `NOT_PROVEN`.

## 4. Backup and restore

The existing backup script includes `openwebui_data` and the restore document
describes recreating that volume. No backup or restore receipt exists and no
root/manifest/access integrity drill was performed.

## 5. Approved cohort

The source cohort was frozen before DOC28 writes: `16`
documents — PDF `8`, HTML `4`,
CSV `2`, XLSX `2`. Safe evidence
contains only document/content hashes, format, size class and blocked status.
The 16 logical documents contain `15` unique
byte hashes; `1` duplicate-content item
remains explicitly accounted rather than excluded.

## 6. Versions and activation

Created `0`, validated `0`, active `0`. The temporary DOC26 store is gone, so
normalization reprocessing is explicitly required; no hidden rerun occurred.

## 7. New-upload four-format shadow

The existing normalizer supports 4/4 formats, but durable shadow runs are `0`.
Legacy results and canonical product reads are unchanged.

## 8. Research consumer

`local_pdf_compact_canonical_proof` remains blocked because there is no durable
active version. DOC27 fixture validation is not treated as real cutover.

## 9. Wave 2 shadows

- `gate2_input_readiness`: `NOT_STARTED`; side effects remain product/operator-owned.
- `gate2_source_fact_runtime`: `NOT_STARTED`; side effects remain product/operator-owned.
- `live_case_group_eligibility`: `NOT_STARTED`; side effects remain product/operator-owned.
- `live_case_group_process_false`: `NOT_STARTED`; side effects remain product/operator-owned.
- `live_pdf_table_operator`: `NOT_STARTED`; side effects remain product/operator-owned.
- `live_private_intake_smoke`: `NOT_STARTED`; side effects remain product/operator-owned.

All six are accounted, contracts are `0/6`, shadow runs `0/3`, migrations `0`.

## 10. Canonical and legacy differences

No DOC28 comparison was executed. `gate2_handoff_v0` remains the only product
read authority; therefore no new difference can honestly be classified.

## 11. Operational metrics

All durable write/read/activation/rollback/retention counters are zero. Runtime
health checks are `NOT_TESTED`; silent failures and private metric content are
zero because no operation was started.

## 12. Retention and rotation

All eight classes are `NOT_TESTED_ON_DURABLE_STORE`; no deletion or rotation
receipt was produced.

## 13. Terminal test accounting

DOC28 safe-evidence tests: `4 passed`; Ruff: `PASSED`. Runtime durability,
restart, backup/restore, research and Wave 2 tests were not started after the
stop-gate. The full suite was not run for DOC28 and is not claimed terminal;
the last recorded baseline remains DOC27 `2909`
passed / `5` skipped /
`7` failed /
`11` errors.

## 14. Exact blockers

1. Target OpenWebUI deployment is not identified and approved for mutation.
2. Its `openwebui_data` volume is not accessible.
3. Controlled restart authority is absent.
4. Backup destination and restore-drill authority are absent.
5. Capacity threshold and retention-worker owner are not confirmed.

Current deployment/storage, backup/restore, retention and authority documents
record this blocked state; none is presented as an operational receipt.

## 15. Next Wave 2 cutover goal

Not authorized. First provide the five unblock items above and rerun DOC28 from
the durable deployment gate.

## Decision

```text
DOC28_PROGRAM = BLOCKED
DURABLE_CANONICAL_STORE = BLOCKED
APPROVED_REAL_COHORT = PARTIAL
NEW_UPLOAD_DURABLE_SHADOW = NOT_STARTED
RESEARCH_CONSUMER_MIGRATION = BLOCKED
WAVE_2_SHADOW = NOT_STARTED
WAVE_2_MIGRATION_READINESS = BLOCKED
BACKUP_RESTORE = BLOCKED
RETENTION_ROTATION = BLOCKED
PRIMARY_PRODUCT_CUTOVER = NOT_PERFORMED
LEGACY_HANDOFF = RETAINED
GATE3 = NOT_STARTED
```

Deployment audit status:
`BLOCKED_DURABLE_BACKEND_NOT_APPROVED_OR_ACCESSIBLE`.
