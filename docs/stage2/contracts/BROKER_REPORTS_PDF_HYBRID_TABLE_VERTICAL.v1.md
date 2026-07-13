# Broker Reports PDF Hybrid Table Vertical v1

Status: implemented for private shadow use only. Production Gate 2 selection is unchanged.

## Boundary

The vertical accepts one detected PDF table, an exact crop of its declared bbox and candidates derived only from the existing production PDF word inventory. The multimodal model may place short candidate ids into a grid; it may not produce values, business facts or source refs.

```text
current PDF words + table bbox
-> deterministic classifier
-> reproducible private crop
-> bounded candidate package
-> native multimodal structured output
-> deterministic materialization
-> independent fail-closed validation
-> private shadow decision
```

OCR, whole-PDF provider transport, Knowledge/RAG/vector writes and OpenWebUI core changes are outside this contract.

## Versioned contracts

| Schema | Responsibility |
|---|---|
| `broker_reports_pdf_table_classification_v1` | Immutable table identity, exact policy/config hash, measured structural signals, typed path and reason codes. |
| `broker_reports_pdf_hybrid_evidence_package_v1` | Crop identity, compact model-facing candidates, private reversible dictionary, output schema and pre-provider component accounting. |
| `broker_reports_pdf_hybrid_binding_output_v1` | Complete rectangular placement of existing candidate ids or explicit empty arrays; no free values. |
| `broker_reports_pdf_provider_attempt_v1` | Exact evidence task, visible attempt lineage, provider/model/transport identity, usage, finish and terminal failure. |
| `broker_reports_pdf_table_materialization_result_v1` | Deterministic full grid, exact values resolved from candidates, source refs, conflicts, package checksum and package-independent placement checksum. |
| `broker_reports_pdf_table_validation_v1` | Independent contract, identity, provenance, rectangularity, empty, duplicate, header, accounting, ambiguity, signal and repeatability gates. |

Shadow coordination also persists `broker_reports_pdf_hybrid_shadow_decision_v1` and `broker_reports_pdf_hybrid_proposed_compact_revision_v1`. Both state `authority_state=non_authoritative`, `production_ready=false` and `production_gate2_selection_changed=false`.

## Classifier paths

- `deterministic_simple`;
- `hybrid_complex`;
- `hybrid_after_deterministic_block`;
- `human_review_required`;
- `unsupported_image_or_text_layer`.

A `quality=high` label alone never selects the simple path. Existing structural blockers, wide or multi-row headers, continuation signals, conflicting grids and the explicit allowlist are observable inputs.

## Raster identity

PyMuPDF `1.26.5` renders only the padded table bbox as a lossless PNG. Primary DPI is 150. DPI 200 requires a typed reason and creates a different crop and evidence package identity. Limits are 4096x4096, 16 megapixels and 8 MiB encoded PNG; no silent resize is allowed.

Crop bytes and provider responses are private ArtifactStore payloads. Safe metadata contains hashes, dimensions, byte counts and policy identities only.

## Candidate and output rules

Candidates are deterministic table-local spans of current production words. Short ids (`c0`, `c1`, ...) map privately and reversibly to exact source spans, bboxes, checksums, `source_value_ref[]` and `word_ref[]`.

For `decision=bound`, every row x column position is present. A non-empty cell is an array of known candidate ids; an explicit empty cell is `[]`. Arbitrary `value`, amount, currency, tax, copied cell text and invented refs are rejected by the canonical output validator before materialization.

`materialization_checksum` is evidence-package scoped. `placement_checksum` intentionally excludes package/crop identity and is used when comparing 150- and 200-DPI package revisions. Repeatability for identical evidence still requires the full materialization checksum to match.

## Hard context budgets

| Component | Hard limit |
|---|---:|
| Candidates | 512 |
| Model-visible candidate JSON | 128 KiB |
| Estimated input | 32,000 tokens; target 24,000 |
| Rows | 64 |
| Columns | 24 |
| Grid positions | 1,536 |
| Header depth | 8 |
| Requested output | 16,384 tokens; target 12,000 |

Every package records image bytes/dimensions, candidate count/JSON/text, task/header/schema bytes, estimated tokens, grid size and both text and provider-token amplification. A hard-budget failure blocks before the provider. Silent truncation and column splitting are forbidden.

## Provider boundary

The provider-neutral factory currently has a Gemini native `generateContent` adapter. Credentials are resolved through the approved OpenWebUI Connection configuration; Valves contain no secret. The adapter owns image wrapping, structured-output schema projection, response parsing and provider failure classification.

No hidden retry or failover exists. Identical evidence permits at most two explicit attempts with lineage. A DPI change is a new task/package revision.

## Validation result

Possible aggregates are `accepted_shadow`, `blocked`, `human_review_required` and `unsupported`. HTTP 2xx alone is never acceptance. Valid provenance does not prove correct placement; provisional reference scoring remains a separate diagnostic and cannot make the shadow result authoritative.
