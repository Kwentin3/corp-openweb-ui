# Broker Reports Gate 2 Source-Fact Extraction Research

Date: 2026-07-10

Status: `GATE2_SOURCE_FACT_RESEARCH_READY`

Scope: design research for structured source-fact extraction from validated Gate 1 / Gate 1.5 artifacts. This note does not implement Gate 2, process customer documents, run tax calculations, generate a declaration, generate XLS/XLSX, perform OCR/VLM, use ordinary OpenWebUI upload, or load any source or derived private artifact into Knowledge/RAG.

## 1. Research Basis

The current repository state was inspected before choosing the design. The authoritative inputs are:

- `docs/reports/2026-07-09/OPENWEBUI_BROKER_REPORTS_DOMAIN_CONTEXT_PACKET_HANDOFF_AUDIT.report.md`;
- `docs/reports/2026-07-09/OPENWEBUI_BROKER_REPORTS_GATE1_DOMAIN_INGESTION_AND_ISSUE_LEDGER_REFACTOR.report.md`;
- `BROKER_REPORTS_DOMAIN_CONTEXT_PACKET.v0.md`;
- `BROKER_REPORTS_DOCUMENT_USAGE_CLASSIFICATION.v0.md`;
- `BROKER_REPORTS_GATE1_ISSUE_LEDGER.v0.md`;
- `BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT.v0.md`;
- `BROKER_REPORTS_GATE1_DOCUMENT_SOURCE_ELIGIBILITY.v0.md`;
- `BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`;
- `BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md`;
- the managed-prompt and structured-output passport contracts/research;
- `domain_ingestion.py`, `gate2_handoff.py`, `document_passport.py`, `artifact_store.py`, and `artifact_resolver.py` in `services/broker-reports-gate1-proof/`.

Older source-fact and intermediate-ledger proposals were treated as useful domain input, not as current Gate 2 execution authority.

## 2. Current Proven Starting Point

The following Gate 1 / Gate 1.5 artifacts are ready for Gate 2 consumption when their ArtifactStore records are validated, active, unexpired, and resolver-accessible:

| Artifact | Gate 2 use | Authority |
| --- | --- | --- |
| `domain_context_packet_v0` | Stage readiness, all next-stage buckets, unresolved issue refs, forbidden assumptions | Canonical semantic handoff |
| `document_usage_classification_v0` | Per-document source-extraction readiness, usage modes, issue refs by stage | Canonical document readiness |
| `gate1_issue_ledger_v0` | Unresolved/resolved issue state, affected/blocked/continuing stages, evidence refs | Canonical issue state |
| `document_metadata_passport_v0` | Validated document identity and bounded metadata context | Authoritative metadata context; not source facts |
| `document_source_eligibility_v0` | Compatibility/reduced-subset view | Compatibility only |
| `gate2_handoff_v0` | ArtifactStore refs and private slice refs by next-stage bucket | Resolver manifest; not semantic authority |
| `private_normalized_text_slice_v0` | Bounded private source payload | Resolver-gated source material |
| `private_normalized_table_slice_v0` | Bounded private table payload with row provenance | Resolver-gated source material |
| `validation_result_v0` | Gate 1 package validation status | Required precondition |
| Artifact record metadata | user/run/case/chat/workspace, lifecycle, retention, validation | Access and persistence authority |

The current code proves that `gate2_handoff_v0.included_document_refs` is only the primary reduced subset. Gate 2 must consume `domain_context_packet_v0.next_stage_refs` and the matching `private_slice_refs_by_next_stage_bucket`; otherwise source-ready secondary and duplicate/non-primary documents can be lost.

The latest persisted `case_group_002` handoff audit records 15 source-ready documents: 12 primary, 1 secondary, 2 duplicate/non-primary, and 0 dropped. It also carries 91 unresolved issue refs. Those counts establish input availability only; they are not Gate 2 extraction proof.

## 3. Canonical Gate 2 Input

There are two distinct input boundaries:

1. The orchestration authority is a validated `domain_context_packet_v0`, resolved with its linked classification, issue ledger, passports, handoff manifest, and ArtifactStore access context.
2. The only object sent to an extraction model is one private `broker_reports_source_fact_package_v0` built deterministically from those artifacts and one bounded source unit.

`gate2_handoff_v0` is not the canonical semantic input. It is the resolver manifest that connects safe document refs to private slices. Chat text, chat JSON, raw OpenWebUI file ids, raw uploaded files, and ordinary processed uploads are not Gate 2 inputs.

The run-level control record is `broker_reports_source_fact_extraction_run_v0`. It records the selected DCP, policies, package refs, prompt/schema/model metadata, results, and terminal status; it does not embed private source payloads.

## 4. Input Granularity Decision

Use a hybrid design: document context plus one bounded extraction unit.

Each model call receives:

- one document ref and its validated passport projection;
- its usage buckets and source-extraction readiness;
- document-wide and unit-specific issue context;
- one normalized table row window, one normalized text slice, or one section slice;
- an exact whitelist of evidence refs and issue refs;
- prompt/schema/model audit metadata.

It does not receive the whole case, all documents, all slices for a document, or raw source files.

Recommended initial package limits are configuration, not schema invariants:

- table unit: one table slice window, normally at most 40 data rows;
- text unit: one paragraph/section-aligned slice, normally at most 6,000 characters;
- no overlapping data rows; header descriptors may be repeated as context;
- no silent truncation: every omitted row/range/slice is recorded as pending coverage;
- one package belongs to exactly one run, case, document, and source unit.

For a large table, the deterministic builder creates non-overlapping row windows. Every row ref must later map to a validated fact or a typed `no_fact_reason`. This prevents table loss without asking the model to deduplicate window overlap.

## 5. Bucket Processing Policy

Source readiness and bucket role are separate decisions. A bucket does not promote a non-source-ready document.

| Bucket | Gate 2 policy | Initial priority |
| --- | --- | --- |
| `primary_source_extraction_refs` | Extract when usage classification is `ready` or `ready_with_issues` | Wave 1 |
| `secondary_source_extraction_refs` | Extract with issue context; affected facts cannot be fully confirmed | Wave 2 |
| `duplicate_or_non_primary_refs` | Extract separately for traceability/comparison; never choose a canonical document or merge facts | Wave 2 |
| `cross_check_refs` | Context only unless the same ref is also source-fact-ready and explicitly selected by extraction policy | Later context/reconciliation |
| `declaration_support_refs` | Context only unless independently source-fact-ready; no declaration mapping in Gate 2 | Later context |
| `audit_reference_refs` | Context/deferred by default; no source promotion from audit role | Deferred |
| `source_ready_not_primary_refs` | Reconciliation view only; each ref must resolve to secondary, duplicate/non-primary, or an explicitly deferred bucket | Coverage check |

For MVP proof, Wave 1 should complete before Wave 2. The run must still record every source-ready ref as `selected`, `deferred_with_reason`, or `blocked_with_reason`; omission is invalid.

## 6. Minimum Fact Types

Use one versioned source-facts set with a discriminated typed payload union. Separate top-level schemas per type would duplicate provenance, issue, prompt, and validator rules before there is implementation evidence that separate services or release cycles are needed.

The minimum union is:

- `trade_operation` — source-visible buy, sell, transfer, redemption, corporate action, or unknown operation row;
- `income` — dividend, coupon, interest, sale proceeds, other source-visible income;
- `withholding_tax` — source-visible withholding or foreign tax paid;
- `fee_commission` — broker fee, commission, custody, exchange, or other source-visible charge;
- `cash_movement` — deposit, withdrawal, credit, debit, or unknown cash movement;
- `currency_fx` — source-visible currency amount, FX rate, or source-provided conversion;
- `position_snapshot` — source-visible holding/position at a stated date;
- `document_summary_evidence` — an explicit source total or summary value, never a model-computed aggregate;
- `unknown_source_row` — a row with preserved provenance that cannot be safely classified.

Subtypes remain candidates, not tax or declaration classifications. An unknown row is preferable to silent omission or invented classification.

## 7. Gate 2 Versus Intermediate Ledgers

Gate 2 may perform only mechanical normalization that can be rechecked against source-value refs:

- decimal parsing;
- ISO date formatting when source date semantics are unambiguous;
- normalized currency code when directly visible;
- normalized instrument identifier type when the identifier is visible;
- safe categorical labels such as source-visible operation direction.

Gate 2 must not:

- match lots or purchases to sales;
- calculate proceeds, expenses, profit/loss, tax base, tax, or declaration-currency values;
- decide deductibility, income codes, filing categories, or final methodology;
- consolidate semantic duplicates across documents;
- choose canonical duplicate documents;
- generate declaration rows or XLS/XLSX.

Those decisions belong to Gate 3 intermediate ledgers and later deterministic calculation/methodology stages.

## 8. Issue Carry-Forward

Issue application is deterministic; the model does not decide issue criticality, resolution, or stage blocking.

The package builder constructs issue context as follows:

1. Start with `domain_context_packet_v0.document_issue_refs[document_ref]`.
2. Resolve every ref against `gate1_issue_ledger_v0`; unknown refs fail the package.
3. Mark an issue unit-specific when its evidence refs intersect the unit evidence whitelist; otherwise keep it document-scoped.
4. Derive impact from `status`, `affected_stage`, `blocked_stages`, and `stages_that_may_continue`.
5. Copy safe forbidden-assumption codes into the package.

Fact linkage rules:

- every fact carries the relevant issue refs from its package;
- unresolved warning-only issues remain visible but do not automatically make an unrelated fact incomplete;
- an unresolved issue that affects the fact or its evidence prevents `completeness=complete`;
- a source-extraction blocker produces a blocked unit or blocked fact record, never a confirmed fact;
- consolidation/declaration blockers do not prevent visible source extraction, but they set downstream-use restrictions;
- no Gate 2 output may mark a Gate 1 issue resolved.

## 9. Structured Output and Prompt Management

The required execution invariant is:

```text
OpenWebUI managed Prompt
+ private bounded source-fact package
+ provider-native response_format=json_schema
+ strict deterministic validator
+ ArtifactStore persistence
```

The final prompt body is stored in OpenWebUI Prompt management. Backend/Pipe configuration stores only prompt id/command, expected template/contract/schema versions, model id, and policies.

Production/customer execution should fail closed when native JSON Schema mode is unavailable. A JSON-object fallback may be retained only for synthetic compatibility research and must not produce a customer/prod validated source-facts artifact unless the same full schema and semantic validators pass and the run is explicitly marked non-production. Free-form model text is never a system-of-record artifact.

One bounded repair call may be considered only for schema/format errors. It must use the same private package, same schema, the safe validator error-code summary, and the same evidence/issue whitelists. It cannot introduce new source data or relax validation.

## 10. Reuse of the Passport Pattern

The current passport path is a sound pattern, but not a ready generic runner implementation.

Reusable now:

- factory-routed managed-prompt resolution and access checks;
- prompt snapshot and prompt hash calculation;
- JSON Schema hash and `response_format` audit metadata;
- OpenWebUI model routing;
- bounded model-call failure handling;
- validator-error summary shape;
- ArtifactStore persistence/lifecycle/resolver conventions;
- whitelist-only compact report projection.

Gate 2-specific and not to be generalized away:

- next-stage bucket selection;
- table/text window construction and coverage accounting;
- typed source-fact union;
- source-value and evidence validation;
- issue-to-fact impact rules;
- Gate 2/Gate 3 boundary checks.

The first implementation slice may introduce a small `StructuredExtractionRunner` protocol with injected prompt resolver, package builder, schema provider, validator, persistence sink, and report projector. It should not move Gate-specific schemas, chunking, issue policy, or fact validation into a universal metadata bag.

## 11. Required Fail-Closed Validators

Before a fact is trusted, validators must prove:

1. exact schema/contract versions and all required fields;
2. run/case/document/package/unit scope consistency;
3. prompt id/version/hash, schema id/hash, model id, and structured-output mode;
4. every evidence/source-value/issue ref exists, resolves, and belongs to the same authorized scope;
5. every fact has provenance and at least one source-value/evidence ref;
6. normalized numbers/dates/currencies reproduce mechanically from referenced source values;
7. no value is filled when the source ref is absent or ambiguous;
8. all package issue refs required for the fact are carried forward;
9. completeness and downstream restrictions agree with unresolved issue impact;
10. every table row or selected text unit is accounted for by a fact or typed no-fact reason;
11. no forbidden field or copied long/raw content enters validated/safe output;
12. no raw filename, OpenWebUI file id, private path, full text, raw row, account number, personal data, secret, or env value appears in safe surfaces;
13. no fact claims tax, profit/loss, deductibility, declaration mapping, filing readiness, or duplicate resolution;
14. duplicate fact ids/evidence coverage within a run are rejected; cross-document semantic deduplication is deferred;
15. privacy failure blocks chat projection and downstream handoff.

## 12. ArtifactStore Placement

| Artifact | Visibility | Storage | Notes |
| --- | --- | --- | --- |
| `broker_reports_source_fact_extraction_run_v0` | `safe_internal` | `project_artifact_store` | Refs, states, counts, policy metadata |
| `broker_reports_source_fact_package_v0` | `private_case` | `project_artifact_payload` | Contains bounded private normalized payload |
| raw model output | `private_case` | `project_artifact_payload` | Audit only; never trusted directly |
| `broker_reports_source_facts_v0` | `private_case` by default | `project_artifact_payload` | Financial facts are sensitive; safe index/projection may be separate |
| `broker_reports_source_fact_validation_v0` | `safe_internal` | `project_artifact_store` | Error codes, accepted/rejected ids, coverage summary |
| issue/fact linkage index | `safe_internal` | `project_artifact_store` | Opaque refs only |
| compact extraction summary | `chat_visible` | `openwebui_chat` plus safe ArtifactStore record | Counts/status/next step only |

All records inherit the existing user/run/case/chat/workspace, retention, expiry, purge, validation, and source-availability checks. None may use `openwebui_knowledge`.

## 13. Proof Plan

### Synthetic proof

Use only synthetic fixtures with rows for every minimum fact type plus negative fixtures for missing refs, invented values, foreign refs, unresolved issues, copied raw content, tax conclusions, duplicate fact ids, and uncovered rows.

Prove:

- deterministic package selection and non-overlapping windows;
- native JSON Schema output;
- strict validation and fail-closed persistence;
- issue-qualified completeness;
- row/slice coverage without silent loss;
- resolver denial across user/run/case/chat/workspace and after expiry/purge;
- compact report privacy;
- zero Knowledge/document/vector deltas.

### `case_group_002` proof

Do not re-upload through ordinary processing. Resolve the accepted process=false Gate 1 artifacts and run in two controlled waves:

1. primary 12-document package selection and bounded extraction;
2. secondary plus duplicate/non-primary package selection with issue restrictions.

Reconcile 15 source-ready refs to selected/deferred/blocked outcomes, keep all 91 unresolved issue refs reachable, require zero dropped source-ready refs, persist only validator-passed facts, and prove no Knowledge/RAG/vector writes. The run must stop before consolidation, tax, declaration, or XLS work.

## 14. Research Questions Answered

1. **Which Gate 1 artifacts are ready?** Validated DCP, DUC, issue ledger,
   metadata passports, compatibility eligibility, handoff resolver manifest,
   normalized private slices, Gate 1 validation, and ArtifactStore scope/
   lifecycle metadata.
2. **What is the canonical Gate 2 input?** DCP is orchestration authority;
   one private `broker_reports_source_fact_package_v0` is the canonical model
   input. The handoff is a resolver manifest, not semantic authority.
3. **Which buckets run first?** Primary first; secondary and duplicate/
   non-primary second; cross-check, declaration-support, and audit context
   later unless independently source-fact-ready and explicitly selected.
4. **Which buckets are extractable?** DUC source-fact readiness controls
   extractability. Primary/secondary/duplicate non-primary source-ready refs
   are extractable; cross-check/declaration/audit roles alone are context only.
5. **How are unresolved issues carried?** Resolve DCP document issue refs
   against the issue ledger, match unit evidence where possible, derive impact
   deterministically, attach refs to facts, and forbid affected facts from
   being marked complete or confirmed.
6. **Which fact types are minimally needed?** Trade operation, income,
   withholding, fee/commission, cash movement, currency/FX, position snapshot,
   explicit source summary, and unknown source row.
7. **What is excluded to prevent premature tax work?** Lot matching,
   consolidation, duplicate selection, aggregates, conversions, profit/loss,
   tax base/tax, deductibility/methodology, declaration mapping, and export.
8. **How is the model call chunked?** One document context plus one bounded,
   non-overlapping table-row window or text/section slice, with explicit
   budgets and full row/segment coverage accounting.
9. **Which validators are required?** Schema, scope, audit, resolver/ref,
   provenance, no-invention/value reproduction, issue/completeness, coverage,
   privacy, duplicate-id, and Gate 2/Gate 3 boundary validators.
10. **What is the proof plan?** Complete synthetic typed/negative/coverage/
    lifecycle/no-RAG proof first; then resolve existing process=false
    `case_group_002` artifacts in primary and non-primary waves and reconcile
    every source-ready ref and unresolved issue without entering Gate 3.

## 15. Remaining Risks

- Current normalized slices may not yet expose cell-level refs consistently enough for strong mechanical value validation.
- `gate1_issue_ledger_v0` is primarily document-scoped; unit-specific matching depends on usable evidence refs.
- Source values are sensitive, so `safe_internal` source-fact payloads should not be the default.
- Provider-native JSON Schema support varies by model; model eligibility must be a configured preflight.
- Table coverage rules need synthetic proof before a customer case run.
- Existing ArtifactStore artifact-type enums do not yet include Gate 2 types; that belongs to the first implementation scaffold, not this docs-only design.

## 16. Research Conclusion

Gate 2 should be a bounded, resolver-gated, structured extraction stage. Its semantic authority is Gate 1's domain context and issue ledger; its model input is a private per-unit package; its system of record is validator-passed ArtifactStore output. This is materially different from the Gate 1.5 passport, which classifies document identity and metadata rather than extracting event-level source facts.

```text
GATE2_SOURCE_FACT_RESEARCH_READY
GATE2_STRUCTURED_OUTPUT_INVARIANT_READY
GATE2_ISSUE_CONTEXT_CARRY_FORWARD_READY
GATE2_ARTIFACTSTORE_PLAN_READY
```
