# Broker Reports Gate 2 Source Facts Contract v0

Date: 2026-07-10

Status: `GATE2_SOURCE_FACT_CONTRACT_READY`

Artifact: `broker_reports_source_facts_v0`

## 1. Purpose

This contract represents facts directly visible in one or more normalized broker-report source units. It preserves source provenance, original-value refs, mechanically normalized values, issue impact, extraction audit, and validator status.

It is not an intermediate ledger, tax model, declaration model, or export model.

## 2. Contract Strategy

Use one shared fact envelope and a discriminated typed payload union.

This keeps provenance, issue, prompt, and validation rules uniform while allowing type-specific required fields. Separate top-level fact contracts are deferred until real implementation shows independent ownership or versioning needs.

Allowed v0 `fact_type` values:

```text
trade_operation
income
withholding_tax
fee_commission
cash_movement
currency_fx
position_snapshot
document_summary_evidence
unknown_source_row
```

## 3. Top-Level Shape

```json
{
  "schema_version": "broker_reports_source_facts_v0",
  "source_facts_set_id": "sf_set_opaque",
  "extraction_run_id": "sf_run_opaque",
  "normalization_run_id": "norm_run_opaque",
  "case_id": "case_opaque_or_null",
  "package_refs": ["art_opaque"],
  "document_refs": ["brdoc_opaque"],
  "facts": [],
  "coverage": {},
  "issue_linkage_summary": {},
  "extraction_audit": {},
  "validation_ref": "art_opaque",
  "validator_status": "passed",
  "created_at": "2026-07-10T00:00:00Z"
}
```

The example is structural only.

## 4. Top-Level Rules

- One fact set belongs to one Gate 2 extraction run.
- A package-scoped fact set references one package/document; a run aggregate may reference multiple package fact sets but must not merge semantic duplicates.
- The model candidate uses this schema shape with `validator_status=pending`
  and nullable validation/raw-output refs; it is persisted only inside the
  private raw-output artifact.
- The system-of-record `broker_reports_source_facts_v0` artifact contains only
  validator-accepted facts and has non-null validation/raw-output refs.
- Failed candidates remain in the private raw output and validation result, not in the validated `facts` array.
- `validator_status` is assigned by deterministic code.
- The canonical fact-set payload is `private_case` by default.

Allowed top-level and per-fact validator states are `pending`, `passed`, and
`passed_with_warnings`. Only deterministic code may replace `pending`.

## 5. Shared Fact Envelope

Every fact has this shape:

```json
{
  "fact_id": "sf_opaque",
  "fact_type": "trade_operation",
  "fact_subtype": "sell",
  "document_ref": "brdoc_opaque",
  "extraction_package_ref": "art_opaque",
  "source_unit_ref": "unit_opaque",
  "source_location": {},
  "extracted_fields": {},
  "normalized_values": {},
  "original_value_refs": {},
  "date": null,
  "amount": null,
  "currency": null,
  "quantity": null,
  "instrument": null,
  "confidence": "medium",
  "completeness": "partial",
  "evidence_refs": [],
  "linked_issue_refs": [],
  "issue_impact": {},
  "extraction_warnings": [],
  "downstream_use": {},
  "extraction_audit": {},
  "validator_status": "passed",
  "validation_ref": "art_opaque"
}
```

All fields are required. Inapplicable common values are `null`; arrays/objects are empty only when allowed by the type rules.

In the pending model candidate, `validation_ref` is null. In the validated
system-of-record artifact it is required and must resolve to the matching
`broker_reports_source_fact_validation_v0` record.

## 6. Fact Identity

`fact_id` is deterministic within the extraction run:

```text
sha256(
  extraction_run_id
  + document_ref
  + source_unit_ref
  + primary_row_or_segment_ref
  + fact_type
  + sorted(primary_original_value_refs)
)
```

The persisted id may be a shortened opaque representation of that digest. It must not contain raw source values.

Two packages in the same run cannot produce different accepted facts with the same id. Exact same-evidence duplicates caused by retry/replay are rejected or treated as idempotent persistence. Semantic duplicates across different documents remain separate facts for Gate 3.

## 7. Source Location and Provenance

Required `source_location` fields:

- `private_slice_artifact_ref`;
- `slice_ref`;
- `source_granularity`;
- `page_ref` or `null`;
- `section_ref` or `null`;
- `table_ref` or `null`;
- `row_ref` or `null`;
- `row_range_ref` or `null`;
- `cell_refs`;
- `text_segment_refs`;
- `parser_ref`;
- `source_checksum_ref`.

The referenced private source unit must also expose
`slice_payload_checksum_ref`, `source_value_projection_policy`, and a
`source_value_index`. These are input-contract fields rather than copied fact
fields; the validator resolves them through the package's private slice ref.

Allowed `source_granularity` values:

```text
table_row
table_cell_group
table_summary_row
text_segment
section
document_summary
unknown
```

Rules:

- at least one row, cell, or text-segment ref is required;
- every ref must be whitelisted by the package and resolver-valid in the same scope;
- page/table/section refs are used where the parser provides them;
- raw row or long text content is not copied into the validated fact;
- no fact may exist with document-only provenance when a more precise row/cell/segment ref is available.

## 8. Extracted, Normalized, and Original Values

### 8.1 `extracted_fields`

This object contains short source-visible categorical candidates and value slots allowed by the typed payload. It must not contain long raw text, raw rows, filenames, file ids, paths, account numbers, names, or personal data.

Example categories include:

- operation direction candidate;
- income subtype candidate;
- fee subtype candidate;
- cash movement direction candidate;
- amount role candidate;
- date role candidate.

### 8.2 `normalized_values`

Only deterministic mechanical normalization is allowed:

- decimal string normalization;
- unambiguous ISO date shape;
- visible currency code normalization;
- visible instrument identifier type normalization;
- safe enum mapping from a source-visible label.

No calculation, aggregation, lookup, tax classification, or methodology decision is allowed.

For normalized-table packages, provider-native structured output is narrowed
to package-provided exact value candidates. Fields without a candidate are
null. When several exact candidates exist for one field, the model selects the
business-relevant candidate; deterministic code may bind its ref only when the
selected normalized string identifies exactly one package candidate.

### 8.3 `original_value_refs`

This object maps every extracted/normalized field to one or more source value refs:

```json
{
  "operation_date": ["cell_value_ref_opaque"],
  "amount.value": ["cell_value_ref_opaque"],
  "amount.currency": ["cell_value_ref_opaque"]
}
```

Rules:

- every non-null extracted or normalized value has an original-value ref;
- source refs, not copied raw strings, are the audit bridge;
- deterministic validators re-resolve the refs and reproduce accepted normalized values;
- a table source-value entry resolves by row/column payload indexes and a value checksum;
- a text source-value entry resolves by character start/end span and a value checksum;
- `source_value_ref`, payload path, source checksum ref, parser ref and value checksum must all belong to the same run/case/document/slice scope;
- missing, duplicate, foreign or checksum-mismatched refs fail closed;
- ambiguous or conflicting source values remain null/uncertain or create separate facts with explicit warnings; they are not silently chosen.

The proven mechanical normalizations at the Gate 2 input-readiness boundary are
trimmed text, dot-decimal parsing, exact ISO date and directly visible
three-letter currency code. Additional normalization kinds require an explicit
validator implementation and contract update; they cannot be inferred by the
model.

## 9. Common Value Objects

### 9.1 Date

```json
{
  "value": "2026-01-01",
  "role": "operation_date",
  "precision": "day",
  "original_value_refs": ["value_ref_opaque"]
}
```

Allowed `role` examples:

```text
trade_date
settlement_date
payment_date
withholding_date
movement_date
snapshot_date
report_period_start
report_period_end
source_unspecified_date
```

Allowed `precision`: `day`, `month`, `year`, `unknown`.

### 9.2 Amount

```json
{
  "value_decimal": "100.00",
  "amount_role": "gross_amount",
  "currency": "USD",
  "original_value_refs": ["value_ref_opaque"]
}
```

The decimal is a string. Scientific notation and floating-point binary output are forbidden. Negative/positive sign must match the referenced source unless the type contract records an explicit source direction field.

### 9.3 Currency

```json
{
  "code": "USD",
  "code_kind": "iso_4217_visible",
  "original_value_refs": ["value_ref_opaque"]
}
```

No currency may be inferred from account, broker, locale, or external knowledge.

### 9.4 Quantity

```json
{
  "value_decimal": "10",
  "unit": "units",
  "original_value_refs": ["value_ref_opaque"]
}
```

### 9.5 Instrument

```json
{
  "safe_label": "instrument_label_opaque_or_null",
  "safe_label_ref": "value_ref_opaque_or_null",
  "identifiers": [
    {
      "identifier_type": "isin",
      "identifier_value": "visible_identifier_or_opaque_projection",
      "original_value_refs": ["value_ref_opaque"]
    }
  ]
}
```

Allowed identifier types start with `isin`, `ticker`, `cusip`, `sedol`, `broker_instrument_id`, and `unknown_visible_identifier`. Identifier values remain private-case unless a separate sensitivity policy redacts them.

## 10. Confidence and Completeness

Allowed `confidence` values:

```text
high
medium
low
none
```

Confidence is evidence quality, not correctness probability and not validator status. `high` requires unambiguous type-specific source refs.

Allowed `completeness` values:

```text
complete
partial
uncertain
blocked
```

Rules:

- `complete` means all fields required by the fact type are visible and no linked unresolved issue affects the fact;
- `partial` means a visible fact exists but one or more expected fields are absent;
- `uncertain` means type or value interpretation is ambiguous or limited by an unresolved issue;
- `blocked` preserves provenance for an affected source item that cannot be trusted as a downstream fact;
- an affected unresolved issue with impact `limits_confirmation` forbids `complete`;
- `blocks_fact` requires `blocked` and `downstream_usable=false`;
- validator acceptance does not upgrade completeness.

## 11. Issue Impact

Required `issue_impact` shape:

```json
{
  "warning_issue_refs": [],
  "limits_confirmation_issue_refs": [],
  "blocks_fact_issue_refs": [],
  "blocks_consolidation_issue_refs": [],
  "blocks_declaration_issue_refs": [],
  "forbidden_assumption_codes": []
}
```

`linked_issue_refs` is the sorted union of these issue refs plus any relevant informational document issue refs.

The model may copy only allowed issue refs. Deterministic validation owns impact classification. Gate 2 cannot set an issue to resolved or remove a skipped/unanswered issue.

## 12. Downstream Use

```json
{
  "downstream_usable": true,
  "gate3_ledger_candidate": true,
  "cross_document_consolidation_allowed": false,
  "tax_calculation_allowed": false,
  "declaration_mapping_allowed": false,
  "restriction_codes": []
}
```

`cross_document_consolidation_allowed` remains false in Gate 2. Gate 3 may
decide after duplicate/cross-check logic. Tax and declaration decisions belong
to Gate 4 and their flags are always false in this contract.

## 13. Extraction Audit

Every fact records:

- managed prompt ref/command/version/hash;
- prompt contract id;
- output schema id/version/hash;
- requested model id;
- structured-output mode;
- raw output artifact ref;
- extraction attempt ordinal;
- repair-attempt count;
- created timestamp.

The audit fields must match run/package/raw-output records exactly.
The fact-level `model_id` is the requested model binding. The resolved provider
model, provider profile/adapter revision, response-id hash, usage, latency and
canonical/adapted provider-schema audit are runtime facts available through
`raw_output_artifact_ref` and `validation_ref`;
they are not copied into each source fact and cannot be authored by the LLM.
`raw_output_artifact_ref` is null in the pending model candidate because the
raw-output record does not yet exist. The runner persists the raw output first,
then the deterministic finalizer inserts that ref and the validation ref. It
must not change extracted fields, normalized values, original-value refs,
completeness, evidence refs, or issue refs while finalizing audit/status fields.

## 14. Typed Payloads

The type-specific payload is carried inside `extracted_fields`/common value objects. Fields not applicable to a type remain absent from the typed payload and null in the common slots.

The machine JSON Schema must implement the union with `oneOf`, a constant
`fact_type` discriminator, and `additionalProperties=false` on the fact,
`extracted_fields`, `normalized_values`, `original_value_refs`, and typed nested
objects. Arbitrary metadata/free-form fields are forbidden.

### 14.1 `trade_operation`

Required:

- `operation_type_candidate` (`buy`, `sell`, `redemption`, `transfer`, `corporate_action`, `unknown`);
- at least one operation date or source row ref;
- instrument object or explicit warning that instrument is not visible;
- amount and/or quantity when visible;
- source-visible side/direction refs.

Forbidden:

- matched lot refs;
- cost basis;
- gain/loss;
- deductible expense;
- tax-base classification.

### 14.2 `income`

Required:

- `income_type_candidate` (`dividend`, `coupon`, `interest`, `sale_proceeds`, `other`, `unknown`);
- amount when visible;
- payment/source date when visible;
- source/country candidate only when directly visible and safe/private.

Forbidden:

- final income code;
- taxable amount;
- net-to-gross inference;
- declaration category.

### 14.3 `withholding_tax`

Required:

- `withholding_type_candidate` (`domestic`, `foreign`, `unknown`);
- amount and currency when visible;
- date/source/country only when visible;
- `related_income_source_refs` only when the document explicitly links them.

Forbidden:

- creditability/deductibility conclusion;
- final foreign-tax treatment;
- inferred income linkage.

### 14.4 `fee_commission`

Required:

- `fee_type_candidate` (`broker_commission`, `exchange_fee`, `custody_fee`, `other`, `unknown`);
- amount/currency/date when visible;
- operation link only when explicitly present.

Forbidden:

- deductible/eligible conclusion;
- allocation across operations;
- Appendix/declaration mapping.

### 14.5 `cash_movement`

Required:

- `movement_type_candidate` (`deposit`, `withdrawal`, `credit`, `debit`, `unknown`);
- amount/currency/date when visible;
- source description represented by a short safe label/ref, not copied long text.

Forbidden:

- treating every credit as income;
- treating every debit as expense;
- net cash calculation.

### 14.6 `currency_fx`

Allowed source-visible forms:

- currency amount;
- explicit source FX rate;
- explicit source-provided converted amount;
- explicit rate date.

Required field `fx_fact_kind` identifies the form. Every rate/conversion value needs its own original-value refs.

Forbidden:

- rate lookup;
- rate-date methodology selection;
- computed conversion;
- rounding policy.

### 14.7 `position_snapshot`

Required:

- snapshot date when visible;
- instrument or safe position label ref;
- quantity when visible;
- source-provided valuation only as an amount with original refs.

Forbidden:

- acquisition cost inference;
- disposal matching;
- portfolio valuation calculation.

### 14.8 `document_summary_evidence`

Use only for a total/summary explicitly visible in the document. Required:

- `summary_kind_candidate`;
- summary value refs;
- section/table/page provenance;
- `source_provided=true`.

Forbidden:

- model-computed aggregate;
- reconciliation result;
- statement that the summary overrides detailed rows.

### 14.9 `unknown_source_row`

Use when a selected source row/segment appears fact-like but cannot be safely classified.

Required:

- row/segment provenance;
- `unknown_reason_codes`;
- any mechanically parsed value objects with original refs;
- `confidence=low|none`;
- `completeness=uncertain|blocked`.

This type preserves evidence and coverage. It must not be converted to a known type by unsupported assumptions.

## 15. Coverage

Top-level `coverage` contains:

- selected row/segment refs total;
- accepted fact-covered refs;
- accepted no-fact refs with typed reasons;
- rejected refs;
- pending refs;
- coverage status;
- package/unit coverage refs.

Allowed no-fact reason codes:

```text
header_row
blank_row
layout_only
repeated_header
non_fact_annotation
package_scope_excluded
blocked_by_issue
unsupported_source_shape
```

For successful table units:

```text
selected refs = fact-covered refs + accepted no-fact refs
rejected refs = 0
pending refs = 0
```

`unknown_source_row` counts as fact-covered, not no-fact.

## 16. Validator Rules

The validator must reject:

- missing/unknown fields or wrong versions/enums/formats;
- provenance-free facts;
- refs outside the package whitelist or authorized scope;
- copied raw rows/full text or forbidden private identifiers in safe projections;
- normalized values that cannot be reproduced from source refs;
- values with missing original-value refs;
- `high` confidence without unambiguous evidence;
- `complete` facts affected by unresolved confirmation-limiting issues;
- missing issue refs or model-changed issue impact;
- incomplete coverage, duplicate fact ids, or cross-package scope drift;
- tax, profit/loss, deductibility, declaration, filing, XLS/XLSX, or duplicate-resolution semantics.

## 17. Gate 3 Boundary

Gate 3 consumes fact refs, provenance, issue linkage, completeness, and restrictions. It may build intermediate ledgers and deterministic calculation traces.

Gate 2 does not merge, consolidate or calculate. Gate 4, not Gate 3, owns
declaration mapping and filing/output readiness.

### 17.1 Domain projection and stitch authority

Domain extractors continue to emit the same strict
`broker_reports_source_facts_v0` envelope and union. Each
`broker_reports_domain_extraction_package_v0` carries an `allowed_fact_types`
set, and both provider schema and post-validator must enforce it.

The validator may deterministically replace only `pending` ids/status/refs
after all existing checks pass. It may not repair model-selected evidence,
source values, normalized values, issue linkage, completeness, or fact type.

A separate pre-validator domain finalizer may bind scope, provenance,
issue/audit/restriction fields and package-bound mechanically reproducible value
candidates under `BROKER_REPORTS_GATE2_DOMAIN_EXTRACTORS.v0.md`. It may bind a
missing ref when one exact model-selected value identifies one candidate, but
it may not choose among candidates or change a non-null mismatched value. It
does not weaken this validator rule: raw output remains private/auditable, no
fact/type is created, and the finalized candidate must pass the same validator.

The safe `broker_reports_domain_source_facts_v0` wrapper references a validated
private source-facts set and lists domain, allowed/actual fact types, fact ids,
covered refs, and validation ref. It is not a second fact authority.

Final row/segment ownership belongs to
`broker_reports_source_fact_stitch_result_v0`. Multiple typed claims are an
explicit conflict; unknown claims preserve coverage; uncovered refs prevent
complete status. Cross-document consolidation remains outside Gate 2.

### 17.2 Derived-unit provenance and completeness

A fact may reference a resolver-gated
`broker_reports_derived_source_unit_v0`. The derived unit is not a new source
of truth. It must retain the parent private-slice artifact ref, source checksum
ref, slice-payload checksum ref, and original row/cell/segment/source-value
refs.

`source_slice_truncated=false` on a derived unit means every ref selected into
that derived unit is present and accounted for. If
`parent_source_slice_truncated=true`, the fact and stitch result remain bounded
to the parent projection and the plan must carry
`parent_remainder_status=pending_gate1_reslice`. This state cannot imply whole
document completeness, Gate 3 input readiness, or primary expansion readiness.
Only `broker_reports_gate3_context_manifest_v0` may assert the latter for its
declared bounded scope.

For a selected derived unit, the unchanged validator still requires:

```text
selected refs = typed fact refs + unknown refs + accepted no-fact refs
conflicts = 0
uncovered refs = 0
issue refs carried according to impact
```

## 18. Status

```text
GATE2_SOURCE_FACT_CONTRACT_READY
GATE2_ISSUE_CONTEXT_CARRY_FORWARD_READY
GATE2_STRUCTURED_OUTPUT_INVARIANT_READY
```

## 19. Parent coverage semantics (2026-07-10)

A source fact may claim complete coverage only inside the selected extraction
unit. Limited primary expansion additionally requires the parent input mode to
be `full_source_unit`, parent truncation false, and parent remainder
`not_applicable_parent_complete`.

Facts retain original row/cell/text/source-value refs from the Gate 1 complete
unit. Segmentation may rebase private payload indices but MUST NOT replace or
mint those source refs. A fact set derived from a legacy preview cannot be used
as whole-source completion evidence.

## 20. Candidate-bound materialization (2026-07-11)

The final `broker_reports_source_facts_v0` shape and validator authority do not
change in candidate-binding mode. A pending fact may be created only after the
binding validator passes an exact package candidate/role/relation selection.
The materializer copies the selected candidate's mechanically normalized value
and existing refs; it cannot choose a candidate, role, relation, fact type or
ambiguity resolution.

The strict source-fact validator still independently resolves source refs,
reproduces normalized values, enforces issue/completeness and audit rules, and
assigns deterministic fact ids. Candidate-binding validation is an additional
fail-closed precondition, not a substitute for this contract.
