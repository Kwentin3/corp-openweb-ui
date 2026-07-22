# Broker Reports Semantic Visual Table Materialization v1

Status: `MAINTAINED_REPOSITORY_DEFAULT_OFF`

Authority: this contract defines the deterministic application boundary that
turns one valid semantic VLM response into a private evidence envelope, a
rectangular logical table, and a Gate 2-compatible table projection.

## Factory boundary

`SemanticVisualTableMaterializationFactory.create` is the only maintained
materialization entrypoint. It accepts:

- one valid `broker_reports_pdf_semantic_vlm_decision_v1`;
- the separately retained private provider evidence bound to its selected
  execution.

It does not invoke a model, parse Markdown, inspect PDF geometry, call OCR, or
assign financial meaning. Callers may not mint semantic table IDs, row or
column indexes, padding cells, spans, or Gate 2 projections themselves.

## Private system envelope

`broker_reports_semantic_visual_table_envelope_v1` contains application-owned:

- stable envelope and table IDs;
- source/document, page, crop, renderer, and crop-hash lineage;
- selected provider, profile, requested/resolved model, and execution hash;
- prompt version/hash and canonical/provider schema hashes;
- request/response hashes, usage, latency, terminal status, and validator
  status;
- the unchanged parsed `description` and `rows` payload;
- the hash-bound raw provider response as private evidence;
- the deterministic logical table and integrity hashes.

Raw provider evidence is not copied into the execution record or safe summary.
Evidence, execution, decision, crop, and transcription hashes must agree before
materialization.

## Logical table materialization

`broker_reports_semantic_logical_table_v1` is produced entirely by code:

- row indexes follow semantic row order;
- column count is the maximum semantic row width;
- column indexes cover the resulting rectangle;
- shorter rows receive explicit `null` cells with
  `empty_origin=short_row_padding`;
- source-returned nulls remain distinguishable as
  `empty_origin=semantic_null`;
- every logical cell has row span 1 and column span 1;
- literal non-null strings are not normalized or converted to numbers;
- `physical_geometry_claimed` is always false.

The application also emits a `broker_reports_canonical_table_v1` grid as a
storage compatibility view. That view is derived after the model response and
does not make the legacy geometric model contract authoritative.

## Gate 2 compatibility

The projection origin is `semantic_vlm_transcription` and its profile is
`semantic_visual_logical_table_v1`. The existing `TableProjectionValidator`
and `Gate2TablePackageFactory` accept this profile only when its deterministic
materialization validator passes. The Gate 2 handoff explicitly states:

- semantic response contract passed;
- upstream visual VLM and page rendering were used;
- provider consensus was not required;
- local OCR was not used;
- physical geometry is not claimed.

This proves structural compatibility. Production selection remains default-off
until actual-corpus qualification and the explicit downstream migration goal.
Existing CSV, XML, text-layer, neutral-PDF, and reviewed-visual origins retain
their existing validation paths.
