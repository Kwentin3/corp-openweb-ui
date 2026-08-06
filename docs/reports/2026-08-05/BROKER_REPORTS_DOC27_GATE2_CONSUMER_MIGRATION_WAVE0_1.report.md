# Broker Reports DOC27 Gate 2 Consumer Migration Wave 0-1

Date: 2026-08-05

Status: `PARTIALLY_COMPLETED`

This is Gate 2 consumer migration evidence. It performs no Gate 3 work, no
global canonical read enable and no primary product cutover.

## 1. Frozen 17-surface inventory

| # | Consumer | Final classification |
| ---: | --- | --- |
| 1 | `artifact_schema_registry` | `MIGRATION_ONLY` |
| 2 | `legacy_handoff_producer` | `LEGACY_FALLBACK` |
| 3 | `gate2_input_readiness` | `WAVE_2_BACKGROUND_PRODUCT` |
| 4 | `gate2_source_fact_runtime` | `WAVE_2_BACKGROUND_PRODUCT` |
| 5 | `gate1_primary_pipe` | `WAVE_3_PRIMARY_PRODUCT` |
| 6 | `gate1_primary_pipe_bundle` | `WAVE_3_PRIMARY_PRODUCT` |
| 7 | `domain_source_fact_bundle` | `WAVE_3_PRIMARY_PRODUCT` |
| 8 | `source_fact_bundle` | `WAVE_3_PRIMARY_PRODUCT` |
| 9 | `live_retention_smoke` | `MIGRATION_ONLY` |
| 10 | `live_case_group_eligibility` | `WAVE_2_BACKGROUND_PRODUCT` |
| 11 | `live_case_group_process_false` | `WAVE_2_BACKGROUND_PRODUCT` |
| 12 | `live_pdf_table_operator` | `WAVE_2_BACKGROUND_PRODUCT` |
| 13 | `live_private_intake_smoke` | `WAVE_2_BACKGROUND_PRODUCT` |
| 14 | `local_pdf_compact_canonical_proof` | `WAVE_0_RESEARCH` |
| 15 | `doc22_safe_evidence_test` | `WAVE_0_TEST` |
| 16 | `gate1_artifact_store_test` | `WAVE_0_TEST` |
| 17 | `pdf_compact_canonical_test` | `WAVE_0_TEST` |

Accounting is `17/17`; unresolved surfaces are zero.

## 2. Exact Wave 0 consumers

Enabled test-only: `doc22_safe_evidence_test`, `gate1_artifact_store_test`, `pdf_compact_canonical_test`. Research consumer
`local_pdf_compact_canonical_proof` has a validated adapter but is blocked from
real cutover because its durable actual-corpus store/active version is absent.

## 3. Exact Wave 1 consumers

None. No frozen surface satisfies the internal read-only, no-side-effect
contract. Wave 1 is `NOT_STARTED`, not fabricated by relabeling product tools.

## 4. Compatibility mappings

- `doc22_safe_evidence_test`: `gate2_handoff_v0` -> `CanonicalReaderFactory.create` -> `doc22_safe_evidence_compatibility_output_v1` via `doc22_safe_evidence_canonical_adapter_v1`.
- `gate1_artifact_store_test`: `gate2_handoff_v0` -> `CanonicalReaderFactory.create` -> `gate1_artifact_store_compatibility_output_v1` via `gate1_artifact_store_canonical_adapter_v1`.
- `pdf_compact_canonical_test`: `gate2_handoff_v0` -> `CanonicalReaderFactory.create` -> `pdf_compact_compatibility_output_v1` via `pdf_compact_canonical_adapter_v1`.
- `local_pdf_compact_canonical_proof`: `broker_reports_pdf_compact_canonical_controlled_proof_v1` -> `CanonicalReaderFactory.create` -> `local_pdf_compact_research_output_v1` via `local_pdf_compact_research_canonical_adapter_v1`.

All mappings and outputs are versioned and consumer-specific.

## 5. Shadow results

Three test consumers are behavior-equivalent on the sealed fixture with three
expected schema differences, zero canonical regressions, zero unresolved
comparisons, and passing single/chunked/access/fail-closed coverage. The
research consumer actual shadow is blocked; DOC26 actual-corpus evidence was
reused as frozen baseline and was not rerun.

## 6. Migrated and blocked consumers

Migrated: `doc22_safe_evidence_test`, `gate1_artifact_store_test`, `pdf_compact_canonical_test`. Blocked:
`local_pdf_compact_canonical_proof`. All Wave 2/3 consumers remain unmigrated.

## 7. Canonical and legacy differences

Canonical reads expose active version, physical-layout/component accounting,
ordered containers/nodes, provenance and terminal issues. Legacy contracts
retain their historical shapes. These are expected schema differences; no
financial semantic fields were added and no adapter reads legacy on failure.

## 8. Operational results

Sealed observation: `3/3`, attempts
`16`, success `12`,
blocked flag-off reads `4`, p50
`6.39425 ms`, p95
`6.6808 ms`, frozen threshold
`250.0 ms` (passed).

## 9. Rollback proof

Four consumer flags were disabled independently. Every call failed explicitly
with `canonical_read_disabled`, recorded a rollback event, changed no active
pointer and performed no adapter-level legacy fallback.

## 10. Active-version safety

CAS rejected a stale candidate; document-specific activation and rollback
changed the expected pointer; rollback restored its target; flag rollback was
independent. Cross-context reads failed closed. This is fixture proof, not an
actual migration-cohort activation.

## 11. Current read-authority map

- Three isolated tests: their consumer adapter over `CanonicalReaderFactory`.
- Research proof: same boundary, blocked without a real active version.
- Wave 1: none.
- Background and primary product: `gate2_handoff_v0`.
- Global `CANONICAL_GATE2_READ_ENABLED=false` remains mandatory.

## 12. Legacy state

`gate2_handoff_v0`, schemas, readers and persisted-data compatibility remain.
The three migrated test reads are deprecated as consumer authorities but are
retained for rollback and regression. No legacy core file was deleted.

## 13. Terminal test accounting

Focused regression: `119 passed`. Latest DOC27 targeted: `23 passed`.
Full suite was terminal, not timed out: `2909 passed`,
`5 skipped`, `7 failed`, `11`
errors in `885.178 s`; it is not reported green. Five
failures are frozen DOC8-DOC11 source hashes and eleven errors are the frozen
Type-First authority hash guard. Two bundle-parity failures found in that run
were fixed by the maintained builder and passed targeted `18/18`. The full
suite was not retried and historical hashes were not rewritten.

## 14. Exact blockers before Wave 2

1. No durable approved actual-corpus canonical store exists after DOC26.
2. No actual migration cohort or active-version set exists.
3. The research consumer has no real consumer-level shadow/cutover receipt.
4. There is no eligible frozen Wave 1 consumer.
5. Wave 2 needs a separately authorized operational contract and cohort.

## 15. Separate Wave 2 task

Not authorized yet. A new task becomes appropriate only after the durable
store/cohort/active versions exist and its scope explicitly permits background
product migration. DOC27 itself stops here.

## Program decision

```text
DOC27_PROGRAM = PARTIALLY_COMPLETED
CONSUMER_INVENTORY = FROZEN
CANONICAL_READ_BOUNDARY = VALIDATED
WAVE_0_MIGRATION = PARTIAL
WAVE_1_MIGRATION = NOT_STARTED
ACTIVE_VERSION_SAFETY = CONFIRMED
ROLLBACK = CONFIRMED
REPOSITORY_HYGIENE = SAFE
WAVE_2_READINESS = BLOCKED
PRIMARY_PRODUCT_CUTOVER = NOT_PERFORMED
LEGACY_HANDOFF = RETAINED
GATE3 = NOT_STARTED
```

Repository pre-state remained intact: 243
pre-DOC27 dirty paths were preserved and no cleanup/reset was performed.
