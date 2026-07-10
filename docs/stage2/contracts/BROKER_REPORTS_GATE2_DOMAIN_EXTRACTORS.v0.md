# Broker Reports Gate 2 Domain Extractors Contract v0

Date: 2026-07-10

Contract family:

- `broker_reports_domain_extraction_package_v0`;
- `broker_reports_domain_source_facts_v0`;
- `broker_reports_domain_source_fact_prompt_v0`.

## 1. Purpose

Each domain extractor is an isolated structured-output stage. It is not an
autonomous agent and cannot change routing, issue state, ownership, duplicate
state, tax semantics, or readiness.

## 2. Domain extraction package

Required identity and scope:

```json
{
  "schema_version": "broker_reports_domain_extraction_package_v0",
  "package_mode": "domain_runtime_strict_json_schema",
  "package_id": "sfdpkg_opaque",
  "package_artifact_ref": "art_opaque",
  "extraction_run_id": "sfdrun_opaque",
  "normalization_run_id": "run_opaque",
  "case_id": "case_or_null",
  "document_ref": "document_opaque",
  "source_unit": {},
  "base_package_id": "sfpkg_opaque",
  "base_package_artifact_ref": "art_or_null",
  "domain_route_id": "sfroute_opaque",
  "domain_route_artifact_ref": "art_opaque",
  "extractor_domain": "income",
  "extractor_id": "income_extractor",
  "candidate_source_refs": [],
  "primary_candidate_refs": [],
  "secondary_candidate_refs": [],
  "allowed_fact_types": ["income", "unknown_source_row"],
  "allowed_evidence_refs": [],
  "allowed_source_value_refs": [],
  "issue_context": [],
  "allowed_issue_refs": [],
  "forbidden_assumptions": [],
  "coverage_expectation": {},
  "prompt_contract": {},
  "output_schema": {},
  "model_id": "model_id",
  "structured_output_policy": {},
  "package_policy_version": "gate2_domain_package_projection_v0",
  "privacy_policy": {},
  "created_at": "ISO-8601"
}
```

## 3. Narrow projection rule

The package builder must physically narrow together:

- model rows/segments;
- private normalized cells/text;
- row/cell/segment provenance;
- source-value index and source-value refs;
- evidence whitelist;
- coverage expectation.

It must not send the whole source unit to every extractor. Original opaque
refs remain stable. Internal private payload indices may be deterministically
re-indexed so the existing mechanical normalization validator can reproduce
values from the narrow projection.

Every candidate ref must be in `allowed_evidence_refs`. Every allowed
source-value ref must occur exactly once in the narrow source-value index.

### 3.1 Deterministic candidate finalization

Before the unchanged semantic validator, the factory-backed domain finalizer
may fill only package-bound values:

- run/package/document/unit scope and pending ids/status;
- prompt/schema/model audit constants;
- row/segment source location from a selected candidate ref;
- row-bound cell/segment evidence refs already in the whitelist;
- exact issue refs, impact arrays, completeness limits, and downstream false
  restrictions;
- common date/amount/currency/quantity/instrument objects derived from the
  candidate's normalized values and original refs;
- missing normalized/common values only when one exact normalized header maps
  to one source-value ref and the existing mechanical reproduction function
  succeeds.

It must not create a fact, select/change a fact type, invent a value/ref,
resolve an issue, add a no-fact reason, or hide incomplete coverage. The raw
model output is persisted before finalization. The same strict validator checks
the finalized candidate and rejects any remaining mismatch.

## 4. Allowed output types

| Extractor domain | Allowed fact types |
| --- | --- |
| `trade_operation` | `trade_operation`, `unknown_source_row` |
| `income` | `income`, `unknown_source_row` |
| `withholding_tax` | `withholding_tax`, `unknown_source_row` |
| `fee_commission` | `fee_commission`, `unknown_source_row` |
| `cash_movement` | `cash_movement`, `unknown_source_row` |
| `currency_fx` | `currency_fx`, `unknown_source_row` |
| `position_snapshot` | `position_snapshot`, `unknown_source_row` |
| `document_summary_evidence` | `document_summary_evidence`, `unknown_source_row` |
| `unknown_source_row` | `unknown_source_row` |

The provider-native strict JSON Schema projection must remove all other union
variants. An exact deterministic hint may further narrow the schema, but never
widen it.

The package-bound provider projection also sets fact `maxItems` to the number
of candidate refs and constrains evidence, original-value, extracted-ref, and
source-location ref array items to the domain package whitelists. These are
pre-call constraints; the post-validator repeats the scope checks.

The post-validator separately enforces the same allowed set using
`source_fact_domain_fact_type_forbidden`; provider schema is not the only
control.

## 5. Managed Prompt registry

Every domain has its own active OpenWebUI Prompt:

```text
prompt id: broker_reports_gate2_<domain>_prompt_v0
command: broker_gate2_<domain>_v0
template id: broker_reports.<domain>_extraction.v0
template kind: broker_reports_<domain>_extraction
prompt contract: broker_reports_domain_source_fact_prompt_v0
input contract: broker_reports_domain_extraction_package_v0
output schema: broker_reports.source_facts.schema.v0
required tag: broker-reports-gate2-domain
```

The final prompt body lives in OpenWebUI Prompt management. Python, Pipe,
Valves, and bundled Function code contain only identities, access policy, and
the package marker.

## 6. Extractor permissions

The extractor may:

- classify a candidate as its one domain fact type, unknown, or an allowed
  no-fact result;
- select/copy only package evidence and source-value refs;
- propose mechanically reproducible normalized values;
- populate the domain-specific source-fact payload;
- copy schema-bound issue/audit/restriction fields.

It may not:

- change route candidates or final ownership;
- resolve or suppress issues;
- mint source refs, value refs, issue refs, or ids;
- consolidate duplicates or cross documents;
- infer missing values from external knowledge;
- calculate profit, loss, cost basis, tax base, or tax;
- map declarations or generate XLS/XLSX;
- call OCR/VLM, ordinary upload, Knowledge/RAG, or vector search.

## 7. Domain source-facts wrapper

The model output and private system-of-record remain the strict
`broker_reports_source_facts_v0` union. After validation, the runtime also
persists a safe internal wrapper:

```json
{
  "schema_version": "broker_reports_domain_source_facts_v0",
  "domain_source_facts_id": "dsf_opaque",
  "extraction_run_id": "sfdrun_opaque",
  "document_ref": "document_opaque",
  "source_unit_ref": "unit_opaque",
  "extractor_domain": "income",
  "extractor_id": "income_extractor",
  "domain_package_ref": "art_opaque",
  "source_facts_ref": "art_opaque",
  "validation_ref": "art_opaque",
  "allowed_fact_types": [],
  "fact_ids": [],
  "fact_types": [],
  "covered_source_refs": [],
  "no_fact_results": [],
  "validator_status": "passed",
  "created_at": "ISO-8601"
}
```

The wrapper does not copy private fact payloads. The referenced source-facts
artifact is `private_case` in `project_artifact_payload`.

## 8. Validation and repair

All existing schema, scope, lifecycle, provenance, source-value reproduction,
issue, completeness, privacy, Gate 3 boundary, audit, and coverage validators
remain mandatory.

Provider-native `response_format=json_schema` with `strict=true` is required.
Customer fallback is none. At most one repair call may use the unchanged narrow
package, unchanged schema/whitelists, and safe validator code/path findings.
Raw initial and repair outputs remain private even when rejected.

## 9. Persistence

| Artifact | Visibility | Backend |
| --- | --- | --- |
| domain package | `private_case` | `project_artifact_payload` |
| raw output | `private_case` | `project_artifact_payload` |
| canonical source facts | `private_case` | `project_artifact_payload` |
| validation | `safe_internal` | `project_artifact_store` |
| domain wrapper | `safe_internal` | `project_artifact_store` |

Knowledge/RAG/vector storage is forbidden for all of them.

## 10. Segmented domain packages

Customer execution defaults to one parent document, one parent source unit,
and one selected derived segment. A selected
`broker_reports_derived_source_unit_v0` is resolver-gated and private. Its
domain package must expose only:

- candidate rows/segments for the selected domain;
- whitelisted evidence refs from those rows/segments and their provenance;
- whitelisted source-value refs with rebased private payload paths;
- relevant document- or intersecting source-unit issue refs;
- the derived coverage ref and explicit parent coverage ref;
- safe segmentation metadata and pending parent remainder status.

The domain builder performs a second physical narrowing over the selected
derived unit. It must not reintroduce deferred, unknown, no-fact, or unrelated
rows. `Identifier` is a safe header synonym for the existing `instrument`
signal; its value still requires the original source-value ref and mechanical
`trimmed_text` reproduction.

The managed Prompt and strict provider schema are unchanged in authority. The
extractor may emit only its typed fact or `unknown_source_row`, copy allowed
refs only, and leave uncertainty blocked/unknown rather than inventing. Final
Prompt bodies remain managed in OpenWebUI and are not embedded in Python,
Pipe, Valves, or chat text.

## 11. Status

The contracts and local strict-output runtime are ready only when the schema
projection, validator mode, ArtifactStore lifecycle, and closed-world bundle
tests pass. Live real-case readiness is a separate proof.

## 12. Full-source unit input refinement (2026-07-10)

Domain extractors receive only a deterministically narrowed segment of a
resolver-validated `private_normalized_source_unit_v0`. The whole parent rows or
text are not sent to the model. The router partitions all parent refs, while a
limited run selects one derived segment and leaves the rest explicit/deferred.

Limited primary expansion is allowed per selected document only after:

- complete parent source unit;
- no pending parent remainder;
- validator-passed typed fact;
- complete conflict-free stitch;
- reconciled source-ready and issue refs.

This does not authorize whole-case expansion, Gate 3, tax, declaration or XLS.
