# Broker Reports Gate 2 Migration Strategy v1

Status: `CURRENT`

Date: 2026-08-05

## Boundary

DOC27 freezes all 17 surfaces and validates the canonical read boundary.
`gate2_handoff_v0` remains authoritative for background/primary product flows,
`CANONICAL_GATE2_READ_ENABLED=false` globally, and rollback is a
consumer-specific flag-off operation independent of the active pointer.

The canonical equivalent is always obtained through
`CanonicalReaderFactory.create`; consumers must not read SQLite, payload paths,
manifest/chunk records, FullSource internals or caller-supplied tenant IDs.

## Frozen inventory

The DOC27 classification is immutable after the first cutover test. A live
script with upload/delete/write/provider behavior is not read-only merely
because one of its assertions reads an artifact.

| # | Consumer | Frozen class | DOC27 state |
| --- | --- | --- | --- |
| 1 | `broker_reports_gate1/artifact_models.py` | `MIGRATION_ONLY` | registry retained |
| 2 | `broker_reports_gate1/gate2_handoff.py` | `LEGACY_FALLBACK` | authoritative producer retained |
| 3 | `broker_reports_gate1/gate2_input_readiness.py` | `WAVE_2_BACKGROUND_PRODUCT` | not migrated |
| 4 | `broker_reports_gate1/gate2_source_fact_runtime.py` | `WAVE_2_BACKGROUND_PRODUCT` | not migrated |
| 5 | `openwebui_actions/broker_reports_gate1_pipe.py` | `WAVE_3_PRIMARY_PRODUCT` | not migrated |
| 6 | `openwebui_actions/broker_reports_gate1_pipe_bundled.py` | `WAVE_3_PRIMARY_PRODUCT` | not migrated |
| 7 | `openwebui_actions/broker_reports_gate2_domain_source_fact_pipe_bundled.py` | `WAVE_3_PRIMARY_PRODUCT` | not migrated |
| 8 | `openwebui_actions/broker_reports_gate2_source_fact_pipe_bundled.py` | `WAVE_3_PRIMARY_PRODUCT` | not migrated |
| 9 | `scripts/live_artifactstore_retention_smoke.py` | `MIGRATION_ONLY` | upload/chat/delete side effects; not Wave 1 |
| 10 | `scripts/live_case_group_eligibility_rerun.py` | `WAVE_2_BACKGROUND_PRODUCT` | not migrated |
| 11 | `scripts/live_case_group_process_false_gate1_run.py` | `WAVE_2_BACKGROUND_PRODUCT` | not migrated |
| 12 | `scripts/live_pdf_table_intake_gate1_operator_proof.py` | `WAVE_2_BACKGROUND_PRODUCT` | not migrated |
| 13 | `scripts/live_process_false_private_intake_smoke.py` | `WAVE_2_BACKGROUND_PRODUCT` | not migrated |
| 14 | `scripts/local_pdf_compact_canonical_proof.py` | `WAVE_0_RESEARCH` | adapter implemented; cutover blocked by absent real active version |
| 15 | `tests/test_broker_reports_doc22_safe_evidence.py` | `WAVE_0_TEST` | enabled test-only |
| 16 | `tests/test_broker_reports_gate1_artifact_store.py` | `WAVE_0_TEST` | enabled test-only |
| 17 | `tests/test_broker_reports_pdf_compact_canonical.py` | `WAVE_0_TEST` | enabled test-only |

There is no frozen `WAVE_1_INTERNAL_READ_ONLY` surface. Creating one by
relabeling a side-effecting operator script would violate the wave contract.

For the three enabled test-only consumers, the legacy read is marked
`DEPRECATED_FOR_CONSUMER_READ_RETAINED_FOR_REGRESSION`. It remains available
for rollback and historical regression coverage; this is not legacy deletion.

## Consumer contract

For every maintained runtime consumer, record before change: its purpose,
legacy fields read, canonical container/node/table query, compatibility
adapter, exact tests and shadow receipt. A migration fails closed if a required
legacy field has no canonical equivalent. Silent fallback is forbidden.

The four Wave 0 mappings and flags are:

| Consumer | Adapter | Consumer flag | Output |
| --- | --- | --- | --- |
| DOC22 safe evidence test | `Doc22SafeEvidenceCanonicalAdapterFactory` | `CANONICAL_READ_DOC22_SAFE_EVIDENCE_TEST` | `doc22_safe_evidence_compatibility_output_v1` |
| ArtifactStore test | `Gate1ArtifactStoreCanonicalAdapterFactory` | `CANONICAL_READ_GATE1_ARTIFACT_STORE_TEST` | `gate1_artifact_store_compatibility_output_v1` |
| PDF compact test | `PdfCompactCanonicalAdapterFactory` | `CANONICAL_READ_PDF_COMPACT_CANONICAL_TEST` | `pdf_compact_compatibility_output_v1` |
| local PDF research proof | `LocalPdfCompactResearchCanonicalAdapterFactory` | `CANONICAL_READ_LOCAL_PDF_COMPACT_CANONICAL_PROOF` | `local_pdf_compact_research_output_v2` |

The first three are migrated only in isolated test scope. The fourth defaults
to canonical read and stops with `CANONICAL_INCOMPLETE` when its real store or
active version is absent; it never invokes the legacy proof automatically.

## Waves

| Wave | Scope | Entry and smoke | Metrics and rollback | Deletion condition |
| --- | --- | --- | --- | --- |
| 0 | research/test consumers | three test consumers enabled; research consumer blocked on missing active version | 3/3 sealed observation, no regression/unresolved; consumer flag off | historical tests/fixtures never deleted |
| 1 | read-only internal consumers | no eligible frozen surface | no cutover performed; do not relabel side-effecting scripts | operator compatibility retained |
| 2 | background processing | Wave 1 stable; terminal job accounting | completion/failure parity and zero pointer corruption; return to legacy | old persisted artifacts remain readable |
| 3 | primary product consumers | explicit authorization; actual-corpus shadow PASS | customer-safe error/latency/semantic parity; immediate valve rollback | all consumers observed and approved |
| 4 | legacy fallback removal | Waves 0-3 closed; no legacy reads; retention window elapsed | no fallback calls; restore last release if regression | delete only after zero imports/tests/contracts/persisted-data/audit dependencies |

The sealed local threshold was frozen at 250 ms p95 before observation and
passed. It is not a production SLO. Wave 2 remains blocked until the approved
actual-corpus canonical store is durably available, document-specific active
versions/rollback targets exist, and a Wave 2 operational threshold is frozen.

## DOC28 stop-gate result

The 16-document DOC26 source cohort remains available with the frozen
`8 PDF / 4 HTML / 2 CSV / 2 XLSX` composition. It was frozen before any DOC28
write. The deployment candidate is the existing `openwebui_data` volume and
the existing ArtifactStore paths beneath `/app/backend/data`; no second engine
is authorized. Because the target runtime/volume is inaccessible and no
restart or restore drill can be performed, backfill, activation, new-upload
shadow, research cutover and all Wave 2 shadows are `NOT_STARTED`. A new task
must supply approved target-runtime access before this strategy can advance.

## DOC29 update

Target access and storage topology were discovered. The research adapter and
all six Wave 2 compatibility shadows passed against an isolated restored
16-document active cohort, with explicit flag-off refusal and no fallback.
The first bounded target backfill did not return a receipt and coincided with
loss of HTTPS health and SSH banner service. Therefore the research target
cutover and target Wave 2 shadow remain blocked; the isolated results do not
authorize a Wave 2 cutover goal.

## DOC32 update

The local PDF research consumer is migrated to the reader-only v2 output and
its consumer-specific flag/rollback proof passed on all eight repaired PDFs.
All six Wave 2 consumers completed three stable target shadow runs over the
16-document cohort with zero canonical, access or product-side-effect
regressions. Consumers migrated in Wave 2 remain `0`; the global read stays off,
legacy handoff is retained, and a separate explicitly authorized Wave 2 cutover
goal is required before any product switch.
