# Broker Reports Gate 2 Consumer Migration Matrix v1

Status: `CURRENT`

Date: 2026-08-05

This matrix is the current human-readable index. The machine-readable frozen
authority is `FROZEN_CONSUMER_SURFACES` in
`broker_reports_gate1/canonical_consumer_migration.py`.

## Read authorities

| Scope | Authority | Rollback owner | State |
| --- | --- | --- | --- |
| two Wave 0 tests | consumer-specific adapter over `CanonicalReaderFactory.create` | the individual test flag | canonical enabled in isolated test scope |
| local Wave 0 research proof | same factory boundary | `--no-canonical-read-enabled` | blocked: real active version/store absent |
| Wave 1 | none | none | no eligible frozen consumer |
| Wave 2 background | `gate2_handoff_v0` | existing legacy route | unchanged |
| Wave 3 primary product | `gate2_handoff_v0` | existing product valve/deploy | unchanged |

## Compatibility rule

Each adapter maps one named legacy contract to one versioned compatibility
output. There is no consumer-id branch table inside a universal adapter. Reads
are active-version only, trusted-context only and fail closed for absent active
version, unsupported schema, unresolved provenance, missing/corrupt component,
root mismatch or blocking conflict.

Telemetry is aggregate and identity-free. It never includes source text, table
values, private paths, raw provider payloads or tenant-identifying content.

## Next wave entry

Wave 2 requires a durable approved actual-corpus canonical store, explicit
document cohort, validated active versions with rollback targets, consumer-level
shadow parity, frozen operational threshold and separate authorization. No
legacy deletion is allowed before Waves 2-4 close.
