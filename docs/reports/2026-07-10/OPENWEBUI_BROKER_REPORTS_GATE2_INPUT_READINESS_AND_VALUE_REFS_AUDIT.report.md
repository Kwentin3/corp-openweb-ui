# Broker Reports Gate 2 Input Readiness And Value-Refs Audit

Date: 2026-07-10

Scope: Gate 1 / Gate 1.5 input readiness for deterministic construction and
validation of `broker_reports_source_fact_package_v0`.

This report contains safe aggregate evidence only. No customer filename, file
id, path, row, source text, account, personal datum, secret, or environment
value is included.

## Executive result

At audit start, the persisted Gate 1 private slices were not independently
sufficient for strict Gate 2 value-ref validation. They carried bounded `cells`
or `text`, a slice id, parser metadata and coarse source location, but did not
carry stable row/cell/source-value refs, text spans, payload checksums or full
row/segment coverage accounting.

After the refinement, newly produced Gate 1 slices are sufficient Gate 2 input
units. Existing `case_group_002` slices also contain enough private primitive
data to derive the same provenance deterministically in memory through the
canonical factory. The dry-run builder validated all 15 source-ready documents
and 37 source units without a model call or persistence.

The result proves Gate 2 input readiness. It does not claim source-fact model,
source-fact JSON Schema, tax, declaration, XLS/XLSX, OCR/VLM, or customer
source-fact execution.

## Audit answers

| Question | Result | Evidence |
|---|---|---|
| Every DCP source-ready document maps to resolver-gated private slices | Passed | Existing-case dry run reconciled 15/15 source-ready document refs and built at least one package for each. |
| Primary, secondary and duplicate/non-primary buckets are packageable | Passed | 12 primary, 1 secondary and 2 duplicate/non-primary documents; 37 packages across their private source units. |
| Table refs are sufficient | Passed after refinement | Stable table, row, row-range, cell, cell-value, source-value, parser, source-checksum and payload-checksum refs; row/column ordinals and safe coverage. |
| Text refs are sufficient | Passed after refinement | Stable segment, section, page/range where available, character-span, source-value, parser, source-checksum and payload-checksum refs; safe section labels and coverage. |
| Packages avoid unsafe transport fields | Passed | Factory input is DCP plus resolver-gated ArtifactStore refs. Package validation rejects raw filename, file id, private path and chat-text fields. The bounded normalized cells/text projection exists only inside the private package. |
| Validators reproduce normalized values | Passed for the declared mechanical set | Original-value refs resolve through private payload paths and checksums. Proven kinds: trimmed text, dot decimal, exact ISO date and directly visible three-letter currency code. |
| Row/segment coverage is checkable | Passed | Every selected table row is exactly one of header, blank, layout or fact candidate; every text segment is exactly blank or text candidate. Selected and accounted totals must match. |
| Issues reach the appropriate scope | Passed | Evidence-ref intersection maps issues to a source unit; other relevant issues remain document-scoped. Missing or foreign refs fail closed. |
| DCP, DUC, ledger, passports, handoff and slices preserve scope | Passed | Resolver validates same user/run/case/chat/workspace, lifecycle, validation and source availability for every resolved record. |
| DCP rather than reduced handoff subset is canonical | Passed | Contracts, DCP payload and comments now require `domain_context_packet_v0.next_stage_refs`; `included_document_refs` remains compatibility-only. |

## Refined implementation

### Stable source-unit provenance

`NormalizedSliceProvenanceFactory.create` is the sole production entrypoint for
minting provenance refs. The normalizer applies it centrally after profiling
and before validation/persistence. Profilers and Gate 2 code do not construct
refs independently.

The source-unit contract now includes:

- `source_unit_schema_version=source_unit_provenance_v0`;
- `private_normalized_table_slice_v0` and
  `private_normalized_text_slice_v0` payload schemas;
- `source_value_projection_policy=private_payload_path_plus_checksum_v0`;
- parser, source and slice-payload checksum refs;
- indexed private payload paths for each source value;
- `source_unit_coverage_v0` accounting.

The validator recomputes the projection from the bounded private payload,
document checksum, parser metadata and slice location. A missing, duplicate,
foreign, altered or checksum-mismatched ref fails closed.

### Deterministic dry-run package builder

`Gate2InputReadinessFactory.create` is the sole production dry-run builder
entrypoint. It starts with a DCP ArtifactStore ref, uses an explicit private
`ArtifactAccessContext`, resolves all linked records through
`ArtifactResolver`, reconciles DCP and DUC readiness, maps issue evidence to
units, builds one private package per selected source unit, validates it and
returns a safe aggregate report.

Dry-run packages are not persisted. No model/prompt execution occurs. The
builder snapshots ArtifactStore record ids and fails if the record set changes.
It also rejects `openwebui_knowledge` storage and all forbidden package fields.

For legacy persisted slices without strong provenance, the builder invokes the
same canonical provenance factory in memory and validates the result. It does
not mutate the legacy ArtifactStore record.

### ArtifactStore and handoff behavior

Private-slice safe metadata now exposes only schema/ref/checksum/coverage
identifiers and counts. New handoff records remain resolver-readable when DCP
source-fact readiness is valid, while their payload still preserves any
full/reduced compatibility blocker.

The existing case has an older compatibility-blocked handoff record. The dry
run did not read that blocked payload. It used the validated DCP and individually
resolver-gated same-scope artifacts, compared only the handoff safe aggregate
summary, and reported
`gate2_legacy_handoff_compatibility_blocked`. The DCP/handoff next-stage safe
summaries matched. This is a retained legacy warning, not loss of a source-ready
document and not a blocker for the next schema/validator slice.

## Contracts and comments updated

- `BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`;
- `BROKER_REPORTS_DOMAIN_CONTEXT_PACKET.v0.md`;
- `BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.v0.md`;
- `BROKER_REPORTS_GATE2_SOURCE_FACTS.v0.md`;
- `BROKER_REPORTS_DOCUMENT_NORMALIZATION_ARTIFACTS.v0_PROPOSAL.md`;
- `BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md`;
- DCP downstream instructions and source-unit access declaration;
- normalizer, handoff and factory-boundary comments/constants.

The contracts now require source-value reproduction by payload path plus
checksum, complete row/segment accounting, DCP next-stage authority,
resolver-scoped access, factory-only ref minting, and no-model semantics for the
input-readiness dry run.

## Synthetic proof

The synthetic fixture contains a header row, fact-like rows, a blank row, a
layout row, text segments, unresolved issue refs and cross-scope negative refs.

Focused proof passed 5/5 tests:

- stable table/text refs and full coverage;
- original value resolution and mechanical normalization reproduction;
- deterministic primary/secondary/duplicate package construction;
- document- and source-unit-scoped issue carry-forward;
- wrong-user, foreign, missing and altered refs fail closed;
- compatibility-blocked handoff payload remains blocked while the new
  resolver-ready source-fact manifest policy is proven.

The full Gate 1 proof suite passed 97/97 tests. Baseline before the change was
92/92, so the proof adds five terminal-outcome tests without replacing or
weakening existing assertions.

## Existing `case_group_002` dry-run proof

The read-only live operator script used the existing `process=false` Gate 1
artifacts. It performed no ordinary upload, model call, OCR/VLM or persistence.

Result:

| Measure | Value |
|---|---:|
| Safe checks passed | 16/16 |
| DCP source-ready documents | 15 |
| Packageable source-ready documents | 15 |
| Dry-run packages validated | 37/37 |
| Primary documents | 12 |
| Secondary documents | 1 |
| Duplicate/non-primary documents | 2 |
| Table source units packaged | 25 |
| Text source units packaged | 12 |
| Source-unit refs reconciled | 7,164 |
| Source-value refs reconciled | 2,232 |
| Selected row/segment refs accounted | 1,598 |
| Unit-scoped issue mappings | 40 |
| Document-scoped issue mappings | 120 |
| Dropped source-ready documents | 0 |

All 56 legacy private slices were upgraded only in memory through the canonical
factory: 44 table slices and 12 text slices. The selected source-ready subset
produced the 37 packages above.

Before/after runtime snapshots were identical:

- ArtifactStore records: 4,181, delta 0;
- OpenWebUI document rows: 0, delta 0;
- OpenWebUI file rows: 232, delta 0;
- Knowledge rows: 0, delta 0;
- vector collections: 123, delta 0;
- vector directories: 123, delta 0;
- vector files: 502, delta 0;
- vector bytes: 210,086,652, delta 0.

This proves no Knowledge/RAG/vector/document regression and no source-ready
document loss for the audited case. The counts are aggregate runtime evidence;
no private payload was printed.

## Remaining boundary

There is no Gate 2 input-readiness blocker after this refinement. The retained
legacy handoff warning is documented above and future handoffs use the refined
resolver status policy.

The next permitted slice is the Gate 2 source-fact machine schema and
deterministic output validator. Actual model execution remains outside this
proof and must not begin until that schema/validator slice passes its own
synthetic and privacy tests.

## Verification commands

```powershell
python -m unittest discover -s 'services/broker-reports-gate1-proof/tests' -v
python -m compileall 'services/broker-reports-gate1-proof/broker_reports_gate1' 'services/broker-reports-gate1-proof/scripts'
python 'services/broker-reports-gate1-proof/scripts/live_case_group_gate2_input_readiness_dry_run.py'
```

## Final statuses

```text
GATE2_INPUT_READINESS_AUDIT_READY
GATE2_VALUE_REFS_SUFFICIENCY_PROVEN
GATE2_SOURCE_UNIT_REFS_READY
GATE2_DRY_RUN_PACKAGE_BUILDER_READY
GATE2_ROW_SEGMENT_COVERAGE_READY
GATE2_ISSUE_REF_CARRY_FORWARD_READY
GATE2_INPUT_CONTRACTS_REFINED
GATE2_INPUT_READINESS_SYNTHETIC_PASSED
CASE_GROUP_002_GATE2_INPUT_DRY_RUN_READY
CASE_GROUP_002_NO_SOURCE_READY_DOC_LOSS_PROVEN
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
READY_FOR_GATE2_SOURCE_FACT_SCHEMA_VALIDATOR_SLICE
```
