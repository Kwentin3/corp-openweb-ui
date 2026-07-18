# Broker Reports Gate 1 LLM Document Metadata Passport Blueprint

Status:

- GATE1_LLM_PASSPORT_BLUEPRINT_READY
- READY_FOR_LLM_PASSPORT_IMPLEMENTATION_SLICE

Date: 2026-07-08

Scope: implementation blueprint for a future Gate 1 / Gate 1.5 LLM-assisted document metadata passport slice.

Compatibility note: `Gate 1.5` is a historical local label for this
metadata-passport sub-stage wholly inside global Broker Reports Gate 1. It is
not a fifth/half global product gate. Global numbering is defined by the
[canonical gate architecture](BROKER_REPORTS_GATE_ARCHITECTURE.md).

No runtime code is changed by this blueprint. This blueprint does not authorize ordinary OpenWebUI upload, Gate 2, source-fact extraction, tax calculation, declaration generation, XLS/XLSX export, OCR/VLM or Knowledge loading.

## 1. Problem And Risk

Current Gate 1 can normalize files, profile technical readability, create taxonomy candidates, persist private slices, render a compact Russian report and produce a reduced Gate 2 handoff. After the PDF/HTML source-policy V2 rerun, 11 case_group_002 documents remain in `source_role_policy_review_required`.

The active risk is false exclusion or over-promotion:

- PDF/HTML text-layer documents may contain broker-report metadata but are not safe to auto-accept by container/taxonomy alone.
- Safe registry role hints are useful but must not bypass evidence and policy.
- A pure rules classifier cannot reliably identify broker/client/account/period/section metadata across broker report layouts.
- An LLM can help classify metadata, but if unmanaged it can drift into Gate 2 fact extraction.

The fix is a bounded metadata-only passport stage.

## 2. Domain And Ownership Map

| Domain | Owner | Owns | Does not own |
| --- | --- | --- | --- |
| OpenWebUI Workspace | OpenWebUI admin/operator | Workspace Model, group access, managed Prompt, selected model, chat shell | Broker Reports artifact contract |
| Pipe adapter | Broker Reports Gate 1 | file ref collection, retention config, prompt locator, user/chat/case context | final prompt body |
| Gate 1 normalizer | Broker Reports Gate 1 | technical profiles, private slices, taxonomy, blockers, package orchestration | tax/source-fact extraction |
| LLM passport stage | Broker Reports Gate 1.5 | LLM-friendly package, prompt resolution, model call, strict JSON parse | Knowledge ingestion, Gate 2 extraction |
| Validator | Broker Reports Gate 1 | schema checks, privacy checks, evidence ref checks, fail-closed decisions | semantic truth guarantee |
| ArtifactStore | Broker Reports project | prompt metadata, private input/output, validated passport, retention, purge | OpenWebUI Knowledge/vector DB |
| Source eligibility v2 | Broker Reports Gate 1 | combine profile/taxonomy/passport/blockers/duplicates/case scope | final tax readiness |
| Gate 2 | Future source-fact extractor | resolve allowed private refs after handoff | parse chat JSON or bypass resolver |

## 3. Boundary Contracts

### 3.1 Managed Prompt Contract

Prompt source:

```text
OpenWebUI Prompt
```

Required prompt identity:

```text
template_id=broker_reports.document_metadata_passport.v0
template_kind=document_metadata_passport
output_schema_version=document_metadata_passport_v0
```

Runtime code stores only locator and expectations:

```text
prompt_id or command
required template_id
required schema version
selected model id
hash algorithm
fail-closed policy
```

### 3.2 LLM Input Contract

Input contract:

```text
broker_reports_llm_document_package_v0
```

The package is private and built from current Gate 1 artifacts. It contains bounded metadata-classification material and evidence refs. It must not be chat-visible or Knowledge-visible.

### 3.3 LLM Output Contract

Output contract:

```text
document_metadata_passport_v0
```

The passport is metadata-only. It contains no raw rows, full source text, tax calculations, declaration fields or XLS/XLSX rows.

### 3.4 Artifact Contract Additions

Next implementation slice should add artifact types:

```text
llm_document_package_v0
llm_prompt_snapshot_v0
llm_passport_raw_output_v0
document_metadata_passport_v0
document_metadata_passport_validation_v0
```

Recommended visibility:

| Artifact | Visibility | Storage backend |
| --- | --- | --- |
| `llm_document_package_v0` | `private_case` | `project_artifact_payload` |
| `llm_prompt_snapshot_v0` | `safe_internal` | `project_artifact_store` or `project_artifact_payload` |
| `llm_passport_raw_output_v0` | `private_case` | `project_artifact_payload` |
| `document_metadata_passport_v0` | `safe_internal` | `project_artifact_store` |
| `document_metadata_passport_validation_v0` | `safe_internal` | `project_artifact_store` |

The chat report may reference only safe counts/statuses and opaque refs.

## 4. Target Workflow

Current workflow:

```text
process=false upload
-> technical normalization
-> taxonomy
-> eligibility
-> Gate 2 handoff
```

Target workflow:

```text
process=false upload
-> technical normalization
-> LLM-friendly document package
-> OpenWebUI managed Prompt
-> OpenWebUI model call
-> document_metadata_passport_v0
-> validator
-> ArtifactStore
-> source eligibility v2
-> Gate 2 handoff
```

The LLM passport stage is Gate 1 / Gate 1.5. It is not Gate 2.

## 5. Implementation Slices

### Slice 1: Prompt Resolver

Add:

- `DocumentPassportPromptResolver`;
- factory entrypoint;
- prompt source adapter;
- prompt metadata DTO;
- hash computation;
- typed failures.

Acceptance:

- resolves active OpenWebUI Prompt by `prompt_id`;
- resolves by exact command only as fallback;
- requires expected tags/meta/schema;
- returns prompt content only inside server execution path;
- exposes hash/version/ref metadata to ArtifactStore;
- missing/inactive/wrong-contract prompt fails closed;
- no prompt body appears in chat or safe report.

### Slice 2: LLM-Friendly Package Builder

Add:

- package builder from technical profile, private slices, taxonomy and blockers;
- per-document size caps;
- evidence ref table;
- forbidden-task declarations;
- private ArtifactStore persistence.

Acceptance:

- package has no raw filename/path/file id in safe projection;
- package refs belong to same run/document;
- package is never returned as chat JSON;
- no Knowledge/vector write is introduced.

### Slice 3: OpenWebUI Model Invocation Adapter

Add:

- adapter that calls the selected OpenWebUI model through the Pipe runtime;
- strict response timeout;
- JSON-only response handling;
- low-temperature/default deterministic settings;
- typed model-call failures.

Acceptance:

- provider credentials are not added to Broker Reports code;
- model id is configured through Valves/runtime config;
- response is parsed as JSON only;
- model failure blocks passport but preserves existing Gate 1 safe report.

### Slice 4: Passport Schema And Validator

Add:

- `document_metadata_passport_v0` schema;
- validator for schema, refs, forbidden fields, confidence, null-on-missing and safety flags;
- safe validation result artifact.

Acceptance:

- invalid JSON fails closed;
- evidence refs must exist and match run/document;
- forbidden raw content fields fail validation;
- `review_required=true` when metadata is missing/conflicting;
- no Gate 2 handoff includes unvalidated passport data.

### Slice 5: ArtifactStore Persistence

Add new artifact types and persistence mapping.

Acceptance:

- prompt ref/version/hash recorded;
- input refs and output schema version recorded;
- private input/output payloads use `project_artifact_payload`;
- safe passport projection uses `safe_internal`;
- retention and purge handle new artifact types;
- resolver denies wrong-user/wrong-case/expired/purged refs.

### Slice 6: Source Eligibility v2

Refactor eligibility to consume optional passport results:

```text
technical profile
+ taxonomy candidate
+ passport
+ blockers
+ duplicate state
+ case scope
```

Acceptance:

- existing behavior remains when passport stage is disabled;
- passed passport can promote PDF/HTML candidates only through explicit source-policy rules;
- incomplete passport produces metadata review, not silent exclusion;
- case_group_002 expected source-policy review set becomes passport-target set.

### Slice 7: Proof Runs

Run in this order:

1. Synthetic files only.
2. case_group_002 only through retained/proven `process=false` refs.
3. No ordinary OpenWebUI upload.
4. No Gate 2 source-fact extraction.

Acceptance:

- vector/document/Knowledge delta remains zero for intake path;
- compact Russian chat report remains primary output;
- passports persist in ArtifactStore;
- private input/output does not appear in chat or Knowledge;
- prompt version/hash recorded;
- source eligibility v2 decisions are explainable through safe reason codes.

## 6. Source Eligibility v2 Rules

Eligibility v2 should keep terminal blockers terminal:

- bytes unavailable;
- unsupported format;
- encrypted/corrupt/parser failed;
- OCR/VLM required.

PDF/HTML source promotion requires:

- text/table evidence from technical profile;
- validated passport;
- source-report role hypothesis with sufficient confidence;
- broker/client/account/period or approved alternative identifiers;
- relevant financial sections;
- no terminal blockers;
- explicit source-policy mode that allows promotion.

If any required metadata is missing:

```text
source_eligibility=metadata_review_required
can_enter_gate2=false
requires_specialist_decision=true
```

If the role is plausible but source policy is not explicit:

```text
source_eligibility=source_role_policy_review_required
can_enter_gate2=false
requires_specialist_decision=true
```

If the passport indicates methodology/output:

```text
source_eligibility=methodology_or_output_artifact
can_enter_gate2=false
```

## 7. Tests And Acceptance Checks

Unit tests:

- prompt resolver missing/inactive/wrong-meta;
- hash changes when prompt changes;
- package builder produces bounded refs;
- validator rejects forbidden fields;
- validator rejects unknown evidence refs;
- eligibility v2 disabled preserves current output;
- eligibility v2 promotes only when policy and passport pass.

Integration tests:

- synthetic Gate 1 run with passport enabled;
- failed model response still produces safe Gate 1 report with passport blocker;
- ArtifactStore stores new artifact types;
- purge removes private payloads and leaves tombstones;
- resolver denies wrong-user/wrong-case/expired/purged.

Live smoke:

- use `process=false` intake only;
- check file/document/Knowledge/vector deltas;
- check compact Russian chat output;
- check no private passport input/output in chat;
- check prompt ref/version/hash in ArtifactStore;
- check source eligibility v2 summary.

## 8. Non-Goals

This blueprint does not include:

- ordinary OpenWebUI upload restoration;
- OpenWebUI core patching;
- separate user-facing sidecar UI;
- Gate 2 source-fact extraction;
- tax calculation;
- declaration generation;
- XLS/XLSX export;
- OCR/VLM;
- loading customer documents or private slices into Knowledge;
- final customer production rollout.

## 9. Deferred Work

Deferred until after the first implementation proof:

- prompt API adapter if runtime-local prompt resolver is insufficient;
- multi-document batching;
- model comparison;
- prompt editor approval workflow beyond OpenWebUI access/history;
- customer-facing explanation page;
- Gate 2 consumption of passport metadata.

## 10. Ready Conditions For Implementation

Proceed to implementation when:

- managed OpenWebUI Prompt is created or seeded by operator;
- prompt locator is known;
- passport model id is selected under provider policy;
- source intake remains `process=false`;
- retention mode is explicit;
- test fixtures are synthetic or already customer-approved through the private intake boundary.

Expected next implementation status after code proof:

```text
LIVE_GATE1_LLM_PASSPORT_PROMPT_RESOLVED
LIVE_GATE1_LLM_PASSPORT_ARTIFACTS_PERSISTED
LIVE_GATE1_LLM_PASSPORT_VALIDATOR_PASSED
LIVE_GATE1_SOURCE_ELIGIBILITY_V2_PASSED
```
