# ADR-0005: Reuse STT Infrastructure Pattern, Not Its Canonical Store

Status: `ACCEPTED_WITH_RUNTIME_RECOVERY_BLOCKER`

Date: 2026-08-05

## Decision

Broker Reports reuses the existing STT operational pattern: named Docker
volume, factory-owned SQLite adapter, opaque refs, scoped reads, typed refusals
and configuration-owned retention. It does not place canonical documents in
`stage2_stt_data` and does not adopt the STT schema as canonical authority.

The selected store is the existing Broker `ArtifactStore` namespace below
`openwebui_data:/app/backend/data`, owned by `ArtifactStoreFactory`,
`CanonicalArtifactStoreFactory` and `CanonicalReaderFactory`. No second
storage engine or volume is introduced.

## Reasons

STT's current store has no canonical version history, CAS active pointer,
immutable chunk graph or authoritative tenant model. Its payload-directory and
rotation settings are not implemented, and `scripts/backup.sh` omits
`stage2_stt_data`. Reusing that database would merge unrelated ownership while
still leaving the required invariants unimplemented.

The Broker store already owns metadata, immutable payload components,
validation, active/superseded versions, rollback receipts and trusted
`ArtifactAccessContext`. Keeping canonical data there is the smallest
factory-routed change and places it inside the existing OpenWebUI persistent
volume without overlapping uploads or STT payloads.

## Consequences

- STT backup/rotation gaps remain explicit infrastructure debt.
- Canonical backup must coordinate SQLite metadata with referenced immutable
  payloads or use a cold volume snapshot.
- Global, Wave 2 and primary canonical reads stay disabled.
- Target admission remains blocked until host recovery, post-job accounting,
  restart/recreation proof and isolated target restore.
