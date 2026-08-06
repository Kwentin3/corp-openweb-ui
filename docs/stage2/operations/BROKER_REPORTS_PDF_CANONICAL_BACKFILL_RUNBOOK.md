# Broker Reports PDF canonical backfill runbook

Status: `CURRENT`

Date: 2026-08-05

## Scope

This runbook republishes an approved PDF only when its immutable active
canonical version is incomplete. It does not authorize new provider, VLM or
cropper calls, a global canonical read, product cutover or Gate 3.

## Preconditions

- exact source bytes and their SHA-256 are available;
- parser and table evidence are available, or a frozen deterministic
  parser-only rerun is explicitly allowed;
- the closed-world image pins the complete parser dependency set;
- `CanonicalNormalizerFactory`, `CanonicalArtifactStoreFactory` and
  `CanonicalReaderFactory` remain the only build/lifecycle/read routes;
- the target document has a recorded expected active version for CAS;
- the new private state, backup and restore namespaces do not already exist.

## Per-document sequence

1. Process one PDF in a network-disabled container with fixed CPU, memory, swap
   and pid limits.
2. Build a new candidate; never edit the old version.
3. Require non-empty ordered nodes, 100% source-atom accounting, zero unresolved
   atoms, source refs on primary nodes, and terminal table-projection accounting.
4. Persist through the canonical store factory and resolve every manifest
   component through the reader.
5. CAS-activate against the recorded old active version.
6. Verify the old version is `SUPERSEDED`, preserved, and classified
   `INCOMPLETE_PDF_CANONICAL_VERSION` in the private repair receipt.
7. Stop on any unexplained failure; do not retry provider/VLM/cropper work.

## Cohort closure

- reopen the store in a new process and read every repaired PDF;
- require roots, node/table counts and component checksums to match;
- prove cross-tenant access is denied;
- restart the service, then recreate its container without deleting the volume,
  repeating the reader check after each operation;
- create an application-consistent SQLite Online Backup plus every referenced
  immutable active-PDF payload and a sealed hash manifest;
- restore into a new isolated namespace and repeat the reader/access checks;
- run the research adapter and Wave 2 only in shadow mode after durability PASS.

## Rollback and retention

The consumer-specific flag is the research rollback. Active-pointer rollback is
available through `CanonicalReader.rollback` but is not automatic. Superseded
incomplete versions remain forensic evidence through the rollback window.
Legacy handoff remains authoritative until a separately authorized cutover.
