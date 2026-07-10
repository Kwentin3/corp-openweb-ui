# OpenWebUI Broker Reports Gate 2 Source-Fact Extraction Implementation Report

Date: 2026-07-10

Repository: `corp-openweb ui` repository root

Scope: Gate 2 runtime structured extraction, managed Prompt integration,
deterministic validation, ArtifactStore persistence, synthetic proof, and a
controlled `case_group_002` primary-wave attempt.

## Result

The Gate 2 runtime is implemented and deployed as a separate OpenWebUI Pipe
Function. The canonical schema/validator/package-builder/ArtifactStore chain is
locally green, and the synthetic live proof passed the full v0 fact union.

The existing `case_group_002` cannot be declared ready for Gate 3. Its legacy
Gate 1 input contains 37 packageable private slices and every one is marked
truncated. A controlled primary batch also produced no validator-accepted fact
sets. Non-primary extraction was therefore not run.

Final overall result:

```text
GATE2_SOURCE_FACT_EXTRACTION_PARTIAL
CASE_GROUP_002_LEGACY_SOURCE_SLICES_TRUNCATED_37_OF_37
CASE_GROUP_002_PRIMARY_BATCH_VALIDATION_REJECTED_3_OF_3_PACKAGES
CASE_GROUP_002_NON_PRIMARY_NOT_RUN_BECAUSE_PRIMARY_DID_NOT_PASS
```

## Implemented Runtime

Implemented explicit Gate 2 modules:

- `gate2_source_fact_contracts.py`: artifact/schema identities, canonical full
  v0 schema, provider projection, managed Prompt resolver, hashes, and audit
  metadata;
- `gate2_input_readiness.py`: DCP-first deterministic package builder,
  resolver-gated linked artifacts, source-unit provenance/value refs, model
  row/segment projection, coverage expectations, and primary/non-primary
  selection;
- `gate2_source_fact_validation.py`: canonical schema validation plus
  fail-closed semantic, provenance, issue, coverage, privacy, lifecycle, and
  Gate 3-boundary checks;
- `gate2_source_fact_runtime.py`: extraction run, package/raw/validation/facts
  persistence, one bounded repair, issue linkage, safe summary, and explicit
  document batching within a wave;
- `broker_reports_gate2_source_fact_pipe.py`: separate OpenWebUI Pipe using
  native model routing and `response_format=json_schema` without a core patch;
- `broker_reports_gate2_source_fact_pipe_bundled.py`: closed-world Function
  bundle with no workspace-only runtime imports.

No generic extraction framework was introduced. Gate 2 fact types, issue
policy, coverage, package projection, and validators remain explicit.

## Artifact Contracts

ArtifactStore now accepts and persists:

- `broker_reports_source_fact_extraction_run_v0`;
- `broker_reports_source_fact_package_v0`;
- `broker_reports_source_fact_raw_output_v0`;
- `broker_reports_source_facts_v0`;
- `broker_reports_source_fact_validation_v0`;
- `broker_reports_issue_fact_linkage_v0`;
- `broker_reports_source_fact_extraction_summary_v0`.

Visibility/storage policy:

| Artifact | Visibility | Storage |
| --- | --- | --- |
| extraction run | `safe_internal` | ArtifactStore metadata |
| bounded package | `private_case` | project payload |
| raw model output | `private_case` | project payload |
| accepted source facts | `private_case` | project payload |
| validation | `safe_internal` | ArtifactStore metadata |
| issue/fact linkage | `safe_internal` | opaque refs/counts |
| compact summary | safe chat projection | counts/status only |

Failed candidates remain private raw audit. A
`broker_reports_source_facts_v0` record is created only after validator pass.

## Schema and Structured Output

The canonical schema is a strict discriminated `oneOf` union for all nine v0
types:

- `trade_operation`;
- `income`;
- `withholding_tax`;
- `fee_commission`;
- `cash_movement`;
- `currency_fx`;
- `position_snapshot`;
- `document_summary_evidence`;
- `unknown_source_row`.

Canonical schema SHA-256:

```text
2fcf8ef920e7aceae6fef898d4a4c375db7ab0cd73416bd9e19f76d57bff6da4
```

The provider projection uses `anyOf` because the selected provider rejected
`oneOf`; the branches remain mutually exclusive through `fact_type` constants.
Its base SHA-256 is:

```text
a0fc2958e41f7de2c32226305e81cb8edeca4627b4bda2da114ae312c3fca5a3
```

Each model call also receives a package-bound schema projection. Scalar
run/package/document/unit/audit values are constrained in the provider schema;
array equality, evidence/value/issue whitelists, and all semantic relationships
are enforced by the canonical deterministic validator. This preserves strict
provider-compatible output shape without trusting the model for ref validity.

Customer/proof mode invariants:

```text
response_format=json_schema
strict=true
free-form fallback=none
maximum repair attempts=1
validator remains final authority
```

## Managed Prompt

Installed OpenWebUI managed Prompt:

```text
prompt_ref: broker_reports_gate2_source_fact_prompt_v0
command: /broker_gate2_source_facts_v0
template_id: broker_reports.source_fact_extraction.v0
output_schema_version: broker_reports_source_facts_v0
version: gate2-source-facts-v0-2026-07-10-implementation
prompt_hash: ce875c5241314036e2633e8b573c09567252332ca6f3825562f0c354c06795a6
```

The final prompt body lives in OpenWebUI Prompt management. Python and the Pipe
contain only resolver/configuration identities and the backend-filled
`{{source_fact_package_json}}` marker.

Installed Function proof:

```text
function_id: broker_reports_gate2_source_fact_pipe
active: true
local bundle SHA-256: ae672718e97d8ddba177fef6c612fa09daeeee71e6a079391f01b185fc363320
live content SHA-256: ae672718e97d8ddba177fef6c612fa09daeeee71e6a079391f01b185fc363320
```

## DCP-First Package Builder

The runtime starts from the validated `domain_context_packet_v0` and resolves:

- `document_usage_classification_v0`;
- `gate1_issue_ledger_v0`;
- `document_metadata_passport_v0`;
- `gate2_handoff_v0` only as a resolver manifest;
- authorized private normalized table/text slices.

Every source-ready ref is reconciled with DCP `next_stage_refs`. Packages carry
one bounded source unit, issue context, allowed evidence/value/issue refs,
coverage expectations, and a private model projection where each fact-candidate
row/segment contains its exact provenance/value refs. Header, blank, and layout
refs are kept out of model fact rows and are recorded as mandatory no-fact
coverage results.

Exact visible operation labels may produce a deterministic `fact_type_hint`.
Unknown or unrecognized real labels retain the full union. The same hint is
checked by the post-validator; it is not merely a prompt suggestion.

Primary/non-primary waves can be split into document batches. A document and
all its packages remain in one batch; other source-ready documents are
explicitly deferred with a batch reason. This prevents reverse-proxy timeout
from silently dropping package work.

## Deterministic Validation

The validator checks:

- canonical schema version, required fields, enum/shape, and unknown fields;
- run/case/document/package/unit scope;
- prompt/schema/model/structured-output audit;
- ArtifactStore ref existence, ownership, lifecycle, and source availability;
- evidence, source-value, issue, and type-specific ref whitelists;
- row/cell/text provenance and source location;
- original-value refs and mechanical date/decimal/currency/text reproduction;
- common value-object consistency;
- issue carry-forward, impact, completeness, and downstream usability;
- selected row/segment accounting and mandatory no-fact results;
- duplicate deterministic fact ids;
- raw/private field rejection;
- profit/loss, tax, declaration, filing, duplicate consolidation, and XLS/XLSX
  boundary violations.

One repair may regenerate the whole candidate using the same managed Prompt,
private package, and canonical schema. It receives only safe validator codes
and field paths. Both raw attempts remain private and both validation attempts
remain auditable.

## Local Verification

```text
python -m compileall -q broker_reports_gate1 openwebui_actions scripts tests
PASS

python -m unittest discover -v -s tests
106 tests passed
```

Coverage includes full union/schema tests, deterministic reproduction, issue
carry-forward, completeness, coverage, privacy/Gate 3 negatives, cross-scope
refs, duplicate ids, ArtifactStore expiry/purge/source-delete, no Knowledge,
bounded repair, document batching, and closed-world bundle execution.

## Synthetic Live Proof

Model route: `gpt-5.4-mini-2026-03-17` through the installed OpenWebUI Pipe.

Result:

| Metric | Result |
| --- | ---: |
| packages | 3 total / 3 accepted / 0 rejected / 0 blocked |
| facts | 9 |
| fact-covered refs | 9 |
| typed no-fact refs | 3 |
| selected refs | 12 |
| pending/rejected coverage refs | 0 / 0 |
| issue-linked facts | 4 |
| raw outputs | 3, all private, strict JSON Schema |
| validated fact sets | 3, all private |
| fallback count | 0 |
| repair count | 0 |

Fact counts:

| Fact type | Count |
| --- | ---: |
| trade_operation | 1 |
| income | 1 |
| withholding_tax | 1 |
| fee_commission | 1 |
| cash_movement | 1 |
| currency_fx | 1 |
| position_snapshot | 1 |
| document_summary_evidence | 1 |
| unknown_source_row | 1 |

The compact Russian summary contained counts/status only. No tax,
declaration, or XLS/XLSX work was performed.

Infrastructure delta during the proof:

```text
document rows: 0
file rows: 0
Knowledge rows: 0
vector collections/directories/files/bytes: 0
ArtifactStore Knowledge backend records: 0
```

The synthetic case was purged through ArtifactStore after proof. Three retained
diagnostic synthetic cases were also purged through the lifecycle API (98
records total).

## `case_group_002` Proof

Input-readiness audit passed for the existing process=false Gate 1 case:

| Metric | Result |
| --- | ---: |
| source-ready documents | 15 |
| packageable documents | 15 |
| packages | 37 |
| primary packages | 16 |
| non-primary packages | 21 |
| table/text packages | 25 / 12 |
| selected coverage refs | 1,598 |
| source-value refs | 2,232 |
| dropped source-ready refs | 0 |
| truncated packages | 37 |

The first unbatched primary request was terminated by the reverse proxy after
approximately seven minutes. It left a nonterminal private audit run and no
terminal summary. Document batching was then implemented and verified locally.

Controlled primary batch result (three complete documents, three packages):

| Metric | Result |
| --- | ---: |
| source-ready decisions | 15 total / 3 selected primary / 12 deferred |
| packages | 3 total / 0 accepted / 3 rejected / 0 blocked |
| raw outputs | 6, all private |
| repair raw outputs | 3 |
| persisted fact sets | 0 |
| truncated selected source units | 3 |
| fallback count | 0 |

Safe validation error counts across initial and repair attempts:

| Code | Count |
| --- | ---: |
| `source_fact_provenance_missing` | 66 |
| `source_fact_completeness_overstated` | 14 |
| `source_fact_coverage_gap` | 5 |
| `source_fact_issue_not_carried` | 4 |
| `source_fact_missing_field` | 1 |

The rejected outputs remained private audit only. No source-fact artifact was
created from them.

Infrastructure delta during the controlled primary batch:

```text
document rows: 0
file rows: 0
Knowledge rows: 0
vector collections/directories/files/bytes: 0
ArtifactStore Knowledge backend records: 0
```

Non-primary extraction was not run because the required primary proof did not
pass. This is an intentional fail-closed stop, not a silent omission.

## Gate 3 Readiness

The runtime and synthetic source-fact contract are ready to feed a future Gate
3 intermediate-ledger design slice. The existing `case_group_002` facts are not
ready for Gate 3 because:

1. all 37 packageable legacy source slices are truncated, so full source
   coverage cannot be proven;
2. the controlled primary batch had no validator-accepted packages;
3. non-primary extraction is correctly withheld until primary proof passes.

No claim is made for profit/loss, tax base, tax, declaration readiness, filing,
duplicate consolidation, methodology, or XLS/XLSX.

## Proven Statuses

```text
GATE2_SOURCE_FACT_RUNTIME_IMPLEMENTED
GATE2_SOURCE_FACT_SCHEMA_VALIDATOR_PASSED
GATE2_SOURCE_FACT_PACKAGE_BUILDER_READY
GATE2_MANAGED_PROMPT_READY
GATE2_STRUCTURED_OUTPUT_MODEL_CALL_PASSED
GATE2_SOURCE_FACT_ARTIFACTSTORE_READY
GATE2_ISSUE_CONTEXT_CARRY_FORWARD_PROVEN
GATE2_ROW_SEGMENT_COVERAGE_PROVEN
GATE2_SYNTHETIC_EXTRACTION_PASSED
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
```

Not proven and therefore not emitted:

```text
CASE_GROUP_002_GATE2_PRIMARY_EXTRACTION_PASSED
CASE_GROUP_002_GATE2_NON_PRIMARY_EXTRACTION_PASSED
READY_FOR_GATE3_INTERMEDIATE_LEDGER_DESIGN_OR_SLICE
```
