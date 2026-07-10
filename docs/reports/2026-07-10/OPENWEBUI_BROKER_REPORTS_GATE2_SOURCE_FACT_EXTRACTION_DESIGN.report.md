# OpenWebUI Broker Reports Gate 2 Source-Fact Extraction Design Report

Date: 2026-07-10

Repository: `corp-openweb ui` repository root

Scope: docs-first Gate 2 source-fact extraction research, blueprint, and contract design. No full Gate 2 implementation or customer-document execution was performed.

## Result

Gate 2 is designed as a bounded structured extraction stage between the accepted Gate 1 / Gate 1.5 domain package and later intermediate ledgers.

The design is ready for a small contracts/schemas/validators implementation slice. It does not claim Gate 2 runtime completion, source-fact extraction from `case_group_002`, tax correctness, declaration readiness, or XLS/XLSX output.

## Deliverables

Created:

- `docs/stage2/research/BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION_RESEARCH.md`;
- `docs/stage2/blueprints/BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.blueprint.md`;
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.v0.md`;
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACTS.v0.md`;
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_SOURCE_FACT_PROMPT.v0.md`;
- this report.

The optional standalone generic runner contract was not created. The reusable runner seam is described in the research and blueprint, while chunking, source-fact schemas, issue impact, and semantic validation remain Gate 2-specific. This avoids premature abstraction.

Updated legacy wording:

- `BROKER_REPORTS_SOURCE_FACTS_SCHEMA.v0_PROPOSAL.md` is marked as historical
  domain input, not the Gate 2 execution/system-of-record contract;
- `BROKER_REPORTS_INTERMEDIATE_LEDGERS_CONTRACT.v0_PROPOSAL.md` now states that
  ledgers and calculations belong to Gate 3 and later;
- `BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md` now clarifies that its old
  minimal handoff example does not replace the DCP `next_stage_refs`, issue
  refs, and bucketed private-slice resolver contract.

## What Gate 2 Consumes

The canonical orchestration authority is a validated `domain_context_packet_v0` plus resolved linked artifacts:

- `document_usage_classification_v0`;
- `gate1_issue_ledger_v0`;
- validated `document_metadata_passport_v0` records;
- `gate2_handoff_v0` as the ArtifactStore resolver manifest;
- private normalized text/table slices;
- existing Gate 1 validation and ArtifactStore access/lifecycle context.

Gate 2 must consume DCP `next_stage_refs` and `document_issue_refs`. It must not interpret `gate2_handoff_v0.included_document_refs` as the full input because that field is only the primary/reduced subset.

The only object sent to a model is one private, bounded `broker_reports_source_fact_package_v0`. It contains one document context plus one table-row window, text slice, or section slice.

Gate 2 does not consume raw chat text, raw source files, raw OpenWebUI file ids, ordinary processed uploads, Knowledge/RAG, or vector results.

## What Gate 2 Emits

The contract family is:

- `broker_reports_source_fact_extraction_run_v0`;
- `broker_reports_source_fact_package_v0`;
- `broker_reports_source_facts_v0`;
- `broker_reports_source_fact_validation_v0`.

Supporting records include private raw model output, safe issue/fact linkage, and a compact chat-visible extraction summary.

No free-form model response is a source-of-record result. Only validator-accepted facts persisted in ArtifactStore are trusted Gate 2 output.

## Fact Types in Scope

The v0 contract uses one discriminated union:

- trade/operation;
- dividend/coupon/interest/other income;
- withholding tax;
- fee/commission;
- cash movement;
- currency/FX facts directly visible in source;
- position/holding snapshot;
- explicit document summary/source evidence;
- unknown/unclassified source row.

Every fact carries:

- stable fact id and type/subtype;
- document, package, and source-unit refs;
- page/section/table/row/cell/text-segment provenance where available;
- extracted fields and mechanically normalized values;
- original-value refs rather than copied long raw text;
- date, amount, currency, quantity, and instrument identifiers when relevant and visible;
- confidence and completeness;
- evidence refs and linked issue refs;
- extraction warnings and downstream restrictions;
- prompt/schema/model/structured-output audit metadata;
- validator status/ref.

No source fact may exist without provenance.

## Explicitly Out of Scope

Gate 2 does not:

- re-decide document identity or source readiness;
- deduplicate or consolidate semantic facts across documents;
- choose a canonical duplicate;
- match lots or link purchases to sales;
- calculate proceeds, expenses, profit/loss, tax base, tax, or currency conversion;
- decide deductibility, tax treatment, methodology, declaration codes, or filing readiness;
- generate a declaration or XLS/XLSX;
- perform OCR/VLM;
- use ordinary OpenWebUI upload, Knowledge/RAG, or vectors;
- patch OpenWebUI core.

## Structured Output

The required invariant is:

```text
OpenWebUI managed Prompt
+ private bounded source-fact package
+ response_format=json_schema with strict=true
+ deterministic fail-closed validator
+ ArtifactStore persistence
```

Customer/production execution has no free-form or unconstrained fallback. Native JSON Schema failure blocks the package. An optional JSON-object compatibility path is limited to explicitly synthetic, non-production proof and still requires the complete schema and semantic validator chain.

At most one same-schema repair attempt may be enabled. It uses the same private package, safe error codes, and unchanged evidence/source-value/issue whitelists. It cannot relax validation or introduce new values.

## Managed Prompts

The proposed OpenWebUI Prompt is identified by:

```text
command: /broker_gate2_source_facts_v0
template_id: broker_reports.source_fact_extraction.v0
prompt_contract_id: broker_reports_source_fact_prompt_v0
input_contract: broker_reports_source_fact_package_v0
output_schema_version: broker_reports_source_facts_v0
```

Backend/Pipe configuration stores ids, expected contracts/versions, model id, and policies only. The final prompt body remains in OpenWebUI managed Prompts. Each run records prompt id/command/version/hash plus schema id/hash and model id.

## Issue Context Carry-Forward

Gate 2 resolves document issue refs from the DCP against `gate1_issue_ledger_v0`. Deterministic code maps each issue to document or unit scope and one or more impacts:

- warning;
- limits confirmation;
- blocks the fact;
- blocks consolidation;
- blocks declaration.

The model cannot create, remove, resolve, or change issue criticality/impact.

Rules:

- affected unresolved issues remain linked to the fact;
- confirmation-limiting issues prevent `completeness=complete`;
- fact-blocking issues produce blocked/downstream-unusable results;
- consolidation/declaration blockers do not hide visible source facts but remain as downstream restrictions;
- skipped/unanswered Gate 1 issues remain unresolved.

## Provenance and Evidence Refs

Gate 2 uses a hybrid package: document context plus one bounded source unit.

Recommended initial configuration:

- table window: normally up to 40 non-overlapping data rows;
- text/section unit: normally up to 6,000 characters;
- repeated safe header descriptors, but no repeated data rows;
- no silent truncation;
- every selected row/segment accounted for by a fact or typed no-fact reason.

Evidence, source-value, and issue refs are whitelisted per package. Validators resolve them through ArtifactStore and require same user/run/case/chat/workspace/document/unit scope. Normalized values are accepted only when deterministic code can reproduce them from original-value refs.

## Validators

The proposed fail-closed chain checks:

1. exact schema versions, required fields, enums, formats, and unknown fields;
2. run/case/document/package/unit scope;
3. prompt/schema/model/structured-output audit metadata;
4. ref existence, whitelist membership, resolver access, lifecycle, and ownership;
5. required provenance and original-value refs;
6. mechanical normalized-value reproduction and no invention;
7. type-specific required/forbidden fields;
8. issue carry-forward, completeness, and downstream restrictions;
9. table/text coverage and duplicate fact ids;
10. no raw/private content in validated/safe projections;
11. no tax, profit/loss, declaration, filing, XLS/XLSX, or duplicate-resolution semantics;
12. privacy status before chat projection or downstream handoff.

Failed model candidates remain only in private raw-output audit records and are not included in validated facts.

## ArtifactStore Persistence

| Artifact | Visibility | Storage |
| --- | --- | --- |
| extraction run | `safe_internal` | project metadata store |
| bounded input package | `private_case` | project payload store |
| raw LLM output | `private_case` | project payload store |
| validated source facts | `private_case` by default | project payload store |
| validation result | `safe_internal` | project metadata store |
| issue/fact linkage | `safe_internal` | opaque refs only |
| compact summary | `chat_visible` | whitelist projection |

The canonical source-fact payload defaults to private because transaction values, dates, instruments, and amounts are sensitive. A safe-internal projection may expose opaque ids, types, counts, statuses, and issue linkage only unless a separate sensitivity policy proves additional fields safe.

Existing ArtifactStore same-context resolver, retention, expiry, purge, validation, and source-delete checks are reused. No Gate 2 artifact is stored in `openwebui_knowledge`.

## Difference From Gate 1.5 Passport Extraction

Gate 1.5 passport extraction answers:

- what the document appears to be;
- which metadata is visible/missing;
- which source-role hypotheses are plausible.

Gate 2 answers:

- which source facts are directly visible in a bounded normalized unit;
- where each fact came from;
- which source values support its normalized fields;
- which unresolved issues limit or block it;
- whether the fact is complete, partial, uncertain, or blocked.

Gate 2 must not re-run the passport decision. It uses validated passport and Gate 1 domain context as authoritative input.

## Handoff to Intermediate Ledgers

Gate 2 hands off ArtifactStore refs to:

- validated source-fact sets;
- validation and coverage results;
- provenance/evidence refs;
- issue/fact linkage;
- completeness/confidence/downstream restrictions.

Gate 3 owns intermediate ledgers, cross-document duplicate/cross-check logic, consolidation, deterministic calculations, methodology application, tax-base preparation, and declaration-oriented modeling.

## Recommended Implementation Slices

1. Add Gate 2 artifact type constants, JSON Schemas, pure validators, and synthetic positive/negative fixtures. No model call.
2. Implement deterministic DCP/DUC/issue/handoff reconciliation and bounded package building for primary refs.
3. Implement one vertical synthetic table slice with `trade_operation` plus `unknown_source_row`, managed Prompt, native JSON Schema, validation, persistence, and safe summary.
4. Add remaining fact types and issue-impact matrix tests.
5. Complete synthetic lifecycle/no-RAG proof, then run controlled `case_group_002` primary and non-primary waves.

Each slice has a narrow acceptance surface and stops before Gate 3 behavior.

## Proof Plan

### Synthetic

Prove:

- all fact types and unknown rows;
- bounded non-overlapping chunking and complete row/segment accounting;
- native JSON Schema output and fail-closed model eligibility;
- provenance and source-value reproduction;
- issue-qualified completeness;
- negative cases for invented/foreign/private/tax/declaration output;
- ArtifactStore cross-scope denial, expiry, purge, and source-delete behavior;
- compact report privacy;
- zero Knowledge/document/vector deltas.

### `case_group_002`

Use accepted process=false Gate 1 artifacts, not ordinary re-upload. Run:

1. primary 12-document selection/extraction;
2. secondary plus duplicate/non-primary selection/extraction with issue restrictions.

Reconcile all 15 source-ready refs to selected/deferred/blocked outcomes, keep all carried unresolved issue refs reachable, require zero dropped refs and explicit package coverage, persist only validator-passed facts, and prove zero Knowledge/RAG/vector writes.

No `case_group_002` Gate 2 execution was performed by this design task.

## Remaining Risks

- Cell-level original-value refs may need strengthening in current normalized table slices.
- Gate 1 issues are mainly document-scoped; precise unit matching depends on evidence-ref quality.
- Source-fact sensitivity requires private-case default and careful safe projections.
- Model/provider JSON Schema support varies and needs configured preflight.
- Full table coverage and no-invention validators need synthetic proof before customer execution.
- Gate 2 artifact types are not yet in the code enum; that is Slice 1 work.

## Final Statuses

Proven by the docs/design delivered in this task:

```text
GATE2_SOURCE_FACT_RESEARCH_READY
GATE2_SOURCE_FACT_BLUEPRINT_READY
GATE2_SOURCE_FACT_CONTRACT_READY
GATE2_SOURCE_FACT_PROMPT_CONTRACT_READY
GATE2_STRUCTURED_OUTPUT_INVARIANT_READY
GATE2_ISSUE_CONTEXT_CARRY_FORWARD_READY
GATE2_ARTIFACTSTORE_PLAN_READY
READY_FOR_GATE2_SOURCE_FACT_IMPLEMENTATION_SLICE
```

Not claimed:

```text
GATE2_RUNTIME_IMPLEMENTED
GATE2_SYNTHETIC_EXTRACTION_PASSED
CASE_GROUP_002_GATE2_EXTRACTION_PASSED
GATE3_INTERMEDIATE_LEDGERS_READY
TAX_CALCULATION_READY
DECLARATION_READY
XLSX_READY
```
