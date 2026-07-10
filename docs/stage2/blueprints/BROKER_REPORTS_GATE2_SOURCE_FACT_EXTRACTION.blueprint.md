# Broker Reports Gate 2 Source-Fact Extraction Blueprint

Date: 2026-07-10

Status: `GATE2_SOURCE_FACT_BLUEPRINT_READY`

## 1. Problem and Risk

Gate 1 / Gate 1.5 now identifies documents, classifies their downstream use, records unresolved issues, and provides resolver-gated normalized slices. Gate 2 must turn those slices into traceable source facts without repeating document classification or crossing into consolidation, tax, declaration, or export work.

The active risks are:

- using only the reduced primary subset and losing secondary or duplicate/non-primary source-ready documents;
- sending whole documents/cases to the model and losing table-row provenance;
- accepting plausible free-form model text as source-of-record;
- inventing missing values or silently treating unresolved issues as resolved;
- mixing source facts with intermediate calculations or declaration rows;
- placing private source facts into chat, Knowledge/RAG, or an insufficiently scoped store;
- introducing a broad generic runner before Gate 2-specific behavior is proven.

## 2. Domain and Ownership Map

| Domain | Owns | Does not own |
| --- | --- | --- |
| Gate 1 domain context | Document identity, readiness, buckets, issue state, private slice refs | Source facts |
| Gate 2 selection/package builder | Which source-ready refs run now, bounded units, evidence/issue whitelists, coverage plan | Document reclassification, fact interpretation |
| Managed Prompt resolver | Prompt access, prompt contract/version/hash snapshot | Prompt body in Python, fact validation |
| OpenWebUI model adapter | Routed structured-output call and audit metadata | System-of-record acceptance |
| Gate 2 fact validator | Schema, scope, provenance, value, issue, privacy, coverage, boundary checks | Tax methodology or duplicate consolidation |
| ArtifactStore | Durable records, visibility, retention, access, purge, resolver | Business interpretation |
| Chat projection | Compact safe status/counts/next step | Facts, raw rows, private refs |
| Gate 3 intermediate ledgers | Consolidation, cross-document duplicate logic, calculations and methodology-bound preparation | Gate 2 extraction |

## 3. Target Flow

```text
validated domain_context_packet_v0
  -> resolve classification + issue ledger + passports + gate2_handoff_v0
  -> reconcile all source-ready refs
  -> select bucket wave
  -> resolve private normalized slices
  -> build bounded broker_reports_source_fact_package_v0 records
  -> resolve OpenWebUI managed Prompt
  -> response_format=json_schema model call
  -> persist private raw output
  -> strict source-fact validation
  -> persist broker_reports_source_facts_v0 + validation
  -> render compact safe summary
  -> expose validated source-fact refs for Gate 3 preparation
```

OpenWebUI chat is the UX surface. ArtifactStore is the system of record.

## 4. Boundary Contracts

### 4.1 Run boundary

`broker_reports_source_fact_extraction_run_v0` owns execution state and refs. It is safe-internal and contains no source payload.

Required relationships:

- one Gate 2 run belongs to one Gate 1 normalization run and one case/chat scope;
- one run references exactly one canonical DCP artifact;
- one run records all source-ready refs as selected, deferred, or blocked;
- one run records prompt/schema/model/policy snapshots;
- one run reaches a terminal state only after validation and persistence outcomes are recorded.

### 4.2 Package boundary

`broker_reports_source_fact_package_v0` is the canonical model input. It is private-case and contains exactly one document plus one extraction unit.

Required relationships:

- the document is present in DCP and classification;
- the extraction unit resolves from a handoff private-slice ref;
- every allowed evidence ref belongs to the same run/case/document/unit;
- every issue ref resolves to the same Gate 1 issue ledger;
- package content stays within configured row/character/token budgets;
- omitted units are represented in the run coverage plan.

### 4.3 Fact boundary

`broker_reports_source_facts_v0` is a set of validator-accepted facts from one package or a deterministic aggregation of package results for the same run. It uses a shared envelope plus a typed payload union.

No fact exists without:

- a stable fact id;
- a fact type;
- a document ref;
- a package and extraction-unit ref;
- source location/provenance;
- source-value or evidence refs;
- issue linkage;
- prompt/schema/model audit metadata;
- validator status/ref.

### 4.4 Validation boundary

`broker_reports_source_fact_validation_v0` is deterministic. It decides whether output can become source-of-record. The LLM may emit `validator_status=pending` only.

## 5. Canonical Selection Algorithm

1. Resolve the DCP and require `stage_readiness.source_fact_extraction` to be `ready` or `ready_with_issue_context`.
2. Require `dropped_source_ready_refs=[]`.
3. Resolve DUC and require exact reconciliation of DUC-ready refs with DCP `source_fact_ready_refs`.
4. Resolve the issue ledger, passports, handoff, and validation artifacts.
5. Build a decision for every source-ready ref:
   - `selected_primary`;
   - `selected_secondary`;
   - `selected_duplicate_or_non_primary`;
   - `deferred_context_only`;
   - `blocked_with_reason`.
6. Do not select a ref solely because it appears in cross-check, declaration-support, or audit buckets.
7. Persist the decision map before resolving private payloads.

Wave policy:

- Wave 1: primary source extraction refs;
- Wave 2: secondary and duplicate/non-primary source-ready refs;
- later context: cross-check/declaration/audit refs not independently source-ready.

Gate 2 never promotes a document whose DUC source-fact readiness is blocked or not applicable.

## 6. Package Construction

### 6.1 Table units

The deterministic builder creates one unit per bounded, non-overlapping row window. The unit carries:

- table/slice ref;
- safe page/section/table locator refs where available;
- row refs and row-range descriptor;
- repeated normalized header descriptors;
- cell/value refs for the selected rows;
- truncation and remaining-range metadata;
- expected coverage refs.

Suggested first-slice default: at most 40 data rows. The value is configurable and recorded on the run; it is not hardcoded into the schema.

### 6.2 Text/section units

The builder prefers parser-provided section or paragraph boundaries. It does not split inside a value token when avoidable. Each package records selected text-segment refs and pending segments. Suggested first-slice default: 6,000 characters.

### 6.3 Document context

Only bounded context is repeated:

- validated passport metadata needed to interpret the unit;
- usage buckets and readiness;
- safe technical profile summary;
- relevant issue descriptors and forbidden assumptions;
- source document ref and package scope.

The builder does not include every document slice, raw filename, raw file id, private path, or chat text.

### 6.4 Coverage

Each unit emits a coverage result:

- source row/segment refs considered;
- fact refs produced;
- refs assigned a typed no-fact reason;
- refs rejected by validation;
- pending refs;
- coverage status.

For a terminal successful table unit, every selected non-header/nonblank row ref is accounted for. An `unknown_source_row` is valid evidence-preserving output; silent omission is not.

## 7. Source-Fact Model

Use one discriminated union with these v0 types:

- `trade_operation`;
- `income`;
- `withholding_tax`;
- `fee_commission`;
- `cash_movement`;
- `currency_fx`;
- `position_snapshot`;
- `document_summary_evidence`;
- `unknown_source_row`.

The shared envelope holds provenance, issue, completeness, confidence, audit, and validation fields. The typed payload holds only fields meaningful to the fact type.

Normalized values are mechanical projections. They must point back to source-value refs. A model-proposed normalized amount/date/currency is accepted only when deterministic validation can reproduce it.

## 8. Issue Impact Algorithm

Issue impact is derived before the model call:

```text
document_issue_refs
  -> resolve ledger entries
  -> match evidence refs to extraction unit
  -> classify scope: document | unit
  -> classify impact: warning | limits_confirmation | blocks_fact |
                      blocks_consolidation | blocks_declaration
```

The package contains only safe issue descriptors:

- issue id/type/status;
- scope;
- criticality;
- affected/blocked/continuing stages;
- safe reason codes;
- evidence refs limited to the package whitelist;
- forbidden assumptions.

Validation rules:

- the model cannot add, remove, resolve, or change criticality of issue refs;
- a fact affected by an unresolved `limits_confirmation` issue cannot be `complete`;
- a `blocks_fact` issue makes the unit/fact blocked and downstream-unusable;
- consolidation/declaration blockers remain attached even when the visible source fact validates;
- warning-only issues may coexist with a complete fact only when deterministic mapping proves they do not affect that fact.

## 9. Structured Extraction Runner Boundary

A small internal runner is justified because the passport path already repeats stable mechanics that Gate 2 also needs.

Proposed narrow protocol:

```text
StructuredExtractionRunner.run(
  prompt_resolver,
  package_builder,
  schema_provider,
  model_adapter,
  validator,
  persistence_sink,
  report_projector,
  run_context
)
```

Reusable behavior:

- factory-first prompt resolution and access checks;
- prompt/schema snapshots and hashes;
- native structured-output call;
- typed model-call audit;
- optional single bounded repair policy;
- raw-output persistence before acceptance;
- validator-controlled acceptance;
- compact report projection.

Remain Gate-specific:

- ref selection and bucket policy;
- private package shape;
- chunking/coverage;
- source-fact union;
- issue impact;
- semantic/boundary validation.

Do not create a general metadata-driven extraction framework or move Gate-specific rules into arbitrary callbacks until at least passport plus one Gate 2 slice demonstrate stable duplication.

## 10. Model and Prompt Policy

- Prompt source: OpenWebUI managed Prompt only.
- Primary mode: `response_format.type=json_schema`, `strict=true`.
- Production/customer fallback: none; fail closed when schema mode is unavailable.
- Synthetic compatibility fallback: optional `json_object`, explicitly non-production, with the same full validators.
- Repair: at most one same-schema call using safe error codes and unchanged evidence/issue whitelists.
- Free-form explanations: generated only from validated safe summary fields, never stored as facts.
- Final prompt body: never hardcoded in Python/Pipe/bundled Function code.

## 11. Fail-Closed Validation Pipeline

Validation executes in this order:

1. JSON parse and JSON Schema validation.
2. Contract/version and required-field validation.
3. run/case/document/package/unit scope validation.
4. prompt/schema/model/structured-output audit validation.
5. resolver and ref-ownership validation.
6. forbidden-key/content and privacy scan.
7. type-specific field validation.
8. source-value reproduction and no-invention validation.
9. issue carry-forward/completeness validation.
10. row/segment coverage and duplicate-id validation.
11. Gate 2/Gate 3 boundary validation.
12. persistence eligibility decision.

Any failure prevents the affected output from entering `broker_reports_source_facts_v0`. Failed raw output remains private for audit/retention. Privacy failure also blocks compact report publication.

## 12. ArtifactStore Plan

| Artifact type | Visibility | Payload policy |
| --- | --- | --- |
| `broker_reports_source_fact_extraction_run_v0` | `safe_internal` | refs, decisions, counts, policy snapshots |
| `broker_reports_source_fact_package_v0` | `private_case` | bounded normalized source content |
| `broker_reports_source_fact_raw_output_v0` | `private_case` | exact model output and call audit |
| `broker_reports_source_facts_v0` | `private_case` default | validated financial facts |
| `broker_reports_source_fact_validation_v0` | `safe_internal` | error codes, coverage, accepted/rejected ids |
| `broker_reports_issue_fact_linkage_v0` | `safe_internal` | opaque fact/issue refs only |
| `broker_reports_source_fact_extraction_summary_v0` | `chat_visible` | aggregate whitelist projection |

`safe_internal` source-fact payload is allowed only after an explicit sensitivity projection; v0 defaults the canonical facts to `private_case`.

All records use existing ArtifactStore factory routing and inherit same-context resolver, retention, expiry, purge, source-delete, and validation checks. No Gate 2 artifact may use `openwebui_knowledge`.

## 13. Gate 3 Handoff

Gate 2 hands off only:

- validated source-facts artifact refs;
- fact ids/types;
- provenance/evidence refs;
- issue/fact linkage refs;
- completeness/confidence/downstream-use restrictions;
- coverage and validation summary refs.

Gate 3 owns:

- semantic duplicate consolidation across documents;
- canonical-source decisions not already deterministically resolved upstream;
- lot matching and operation linkage;
- intermediate ledgers;
- currency-rate lookup/conversion policy;
- profit/loss, tax-base, and tax calculations;
- methodology application;
- declaration model and XLS/XLSX.

Gate 2 cannot claim filing or declaration readiness.

## 14. Implementation Slices

### Slice 1: contracts, schemas, and pure validators

Add artifact type constants, schema providers, typed validators, synthetic fixtures, and negative tests. No model call.

Acceptance:

- every minimum fact type validates with provenance;
- invented/foreign/private/tax/declaration outputs fail;
- issue-qualified completeness rules pass/fail correctly;
- ArtifactStore rejects invalid visibility/lifecycle combinations.

### Slice 2: deterministic selection and package builder

Resolve DCP/DUC/issues/handoff/slices and build primary table/text packages.

Acceptance:

- all source-ready refs reconcile to selected/deferred/blocked;
- non-overlapping windows and full coverage plan;
- resolver scope tests pass;
- no chat or Knowledge/RAG access.

### Slice 3: managed Prompt plus one typed vertical slice

Implement `trade_operation` plus `unknown_source_row`, native JSON Schema call, validation, persistence, and compact report on synthetic tables.

Acceptance:

- schema-mode preflight passes;
- raw output is private;
- only validated facts persist as system of record;
- row coverage is complete;
- free-form output cannot bypass validators.

### Slice 4: remaining typed facts and issue impacts

Add income, withholding, fees, cash, FX, positions, and explicit source summaries.

Acceptance:

- type-specific positive/negative fixtures;
- no calculation/declaration leakage;
- issue carry-forward matrix covered.

### Slice 5: synthetic full run and `case_group_002` controlled proof

First complete the synthetic no-RAG/private-lifecycle proof. Then resolve the existing accepted process=false case artifacts in primary and non-primary waves.

Acceptance:

- source-ready reconciliation and zero dropped refs;
- every accepted fact validator-passed;
- unresolved issues remain reachable;
- zero Knowledge/document/vector deltas;
- no consolidation, tax, declaration, XLS/XLSX, or OCR/VLM.

## 15. Validation and Proof Matrix

| Risk | Proof |
| --- | --- |
| Huge context/table loss | bounded package tests plus row coverage reconciliation |
| Wrong case/document refs | resolver and validator cross-scope denial tests |
| Invented values | source-value reproduction negative tests |
| Lost unresolved issues | package/fact issue-ref reconciliation tests |
| Premature confirmation | completeness/issue-impact matrix |
| Tax/declaration leakage | forbidden semantic/key fixtures |
| Free-form system-of-record | schema-mode plus validator/persistence tests |
| Private data in chat | whitelist projection and private marker scans |
| RAG/vector use | before/after Knowledge/document/vector deltas |
| Artifact resurrection | expiry/purge/source-delete resolver tests |

## 16. Non-Goals and Deferred Work

- No OpenWebUI core patch.
- No ordinary processed upload.
- No Knowledge/RAG/vector use.
- No raw-file parser or OCR/VLM in Gate 2.
- No cross-document semantic deduplication.
- No final totals, tax, declaration, filing, or XLS/XLSX.
- No universal extraction framework beyond a narrow runner seam.
- No UI redesign; chat remains a compact UX surface.

## 16A. Implemented Domain Refactor

The first broad real batch proved that a full nine-type union plus provenance,
issues, completeness, and whole-unit coverage is too wide for one model task.
The implemented customer target is now:

```text
validated DCP and source-unit package
  -> Gate2SourceUnitRouterFactory
  -> route artifact with one entry per selected ref
  -> Gate2DomainPackageBuilderFactory
  -> physically narrowed domain packages
  -> managed Prompt registry, strict package-bound schema per domain
  -> existing strict source-fact validator with allowed_fact_types
  -> validated private source-facts artifacts plus safe domain wrappers
  -> Gate2SourceFactStitcherFactory
  -> ownership/conflict/unknown/no-fact/issue/coverage stitch result
  -> compact safe Russian summary
```

Boundary modules are intentionally Gate 2-specific:

- router: signals and candidate domains only;
- package builder: narrow projections and whitelists only;
- prompt registry/schema projection: domain contract only;
- validator: unchanged fact authority plus domain type restriction;
- stitcher: fan-in ownership and coverage only;
- runtime: ArtifactStore lifecycle and terminal orchestration only;
- Pipe: OpenWebUI request/model adapter only.

The broad Pipe remains available for compatibility/synthetic comparison. The
domain Pipe is the customer route when managed domain Prompts exist and defaults
to one document and one source unit until a real vertical passes.

### Domain refactor proof sequence

1. Pure router/package/schema/stitch tests, including ambiguity and conflict.
2. ArtifactStore synthetic runtime with validator-passed trade and income facts.
3. Closed-world bundled domain Pipe test.
4. Live synthetic no-RAG proof across clean, ambiguous, unknown, no-fact, and
   issue cases.
5. One smallest high-confidence `case_group_002` table/unit vertical.
6. Only after step 5 is complete and conflict-free, limited primary expansion.

Non-primary and Gate 3 remain withheld before the real vertical passes.

## 17. Readiness

The design is ready for Slice 1 only. It does not claim runtime Gate 2 proof.

```text
GATE2_SOURCE_FACT_BLUEPRINT_READY
GATE2_SOURCE_FACT_CONTRACT_READY
GATE2_SOURCE_FACT_PROMPT_CONTRACT_READY
GATE2_STRUCTURED_OUTPUT_INVARIANT_READY
GATE2_ISSUE_CONTEXT_CARRY_FORWARD_READY
GATE2_ARTIFACTSTORE_PLAN_READY
READY_FOR_GATE2_SOURCE_FACT_IMPLEMENTATION_SLICE
```
