# OpenWebUI Broker Reports LLM Document Metadata Passport Research Report

Date: 2026-07-08

Status:

- OPENWEBUI_NATIVE_LLM_PASSPORT_RESEARCH_READY
- DOCUMENT_METADATA_PASSPORT_CONTRACT_READY
- DOCUMENT_METADATA_PASSPORT_PROMPT_CONTRACT_READY
- GATE1_LLM_PASSPORT_BLUEPRINT_READY
- OPENWEBUI_PROMPT_MANAGEMENT_DECISION_READY
- READY_FOR_LLM_PASSPORT_IMPLEMENTATION_SLICE

Scope: research and blueprint only. No runtime code changed. No customer documents processed. No Gate 2, source-fact extraction, tax calculation, declaration generation, XLS/XLSX export, OCR/VLM, ordinary OpenWebUI upload or Knowledge loading was performed.

This report intentionally does not print raw filenames, OpenWebUI file ids, private paths, rows, source text, names, account numbers, secrets or env values.

## 1. Selected OpenWebUI-Native Prompt Mechanism

Selected mechanism:

```text
OpenWebUI Workspace Prompt as managed prompt source
-> Broker Reports server-side prompt resolver
-> Pipe/backend LLM passport stage
-> OpenWebUI model call
-> ArtifactStore audit and retention
```

OpenWebUI Prompt is selected as the primary managed source because it provides the right native control plane: prompt body, command, tags, metadata, access controls, version history, production version and rollback.

The prompt is not used as a user slash-command workflow for Gate 1 execution. It is used as a managed, versioned prompt registry that the Pipe/backend resolves server-side.

Sources:

- OpenWebUI Prompts docs: <https://docs.openwebui.com/features/workspace/prompts/>
- OpenWebUI Functions docs: <https://docs.openwebui.com/features/extensibility/plugin/functions/>
- OpenWebUI Pipe docs: <https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/>
- OpenWebUI reserved args docs: <https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args/>
- OpenWebUI prompt router/model source: <https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/routers/prompts.py>, <https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/models/prompts.py>

## 2. Why Prompt Is Not Hardcoded In Python

The final passport prompt body must not be hardcoded in `broker_reports_gate1_pipe.py`, `normalizer.py` or backend constants.

Reasons:

- prompt edits should not require redeploying a Pipe bundle;
- OpenWebUI already provides prompt access control and version history;
- ArtifactStore needs prompt id/version/hash per run;
- code should own resolver/schema/validator logic, not mutable policy wording;
- old passport artifacts must retain old prompt hash/version after prompt changes;
- prompt text must not drift into chat-visible output or source reports.

Python may store only the locator and contract expectations.

## 3. How Prompt Version/Hash Enters ArtifactStore

At runtime, Gate 1 resolves the active OpenWebUI Prompt by `prompt_id` or exact command and verifies expected metadata:

```text
template_id=broker_reports.document_metadata_passport.v0
template_kind=document_metadata_passport
output_schema_version=document_metadata_passport_v0
```

Gate 1 computes a deterministic SHA-256 hash over normalized prompt content plus prompt contract id and output schema version.

ArtifactStore should persist:

- `llm_prompt_ref`;
- `llm_prompt_command`;
- `llm_prompt_version`;
- `llm_prompt_hash`;
- `llm_model_id`;
- `llm_input_refs`;
- `output_schema_version`;
- optional internal prompt snapshot artifact, not chat-visible.

## 4. Proposed Passport Contract

Created:

```text
docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT.v0.md
```

Contract:

```text
document_metadata_passport_v0
```

It is metadata-only. It contains candidate document kind, broker/client/account/period metadata, detected sections, role hypotheses, confidence, evidence refs, missing metadata fields, conflicts, prompt metadata and validator status.

It explicitly does not contain raw rows, full text, transaction facts, tax calculations, declaration fields or XLS/XLSX rows.

## 5. LLM Input

LLM input is a private Gate 1-built package:

```text
broker_reports_llm_document_package_v0
```

It is built from:

- technical profile;
- normalized private slice refs;
- bounded metadata-classification snippets/summaries;
- table header/section summaries;
- taxonomy candidate;
- blocker codes;
- source-policy context;
- evidence refs.

It is not ordinary OpenWebUI upload context and not Knowledge/RAG context. It must be private and retained/purged through ArtifactStore policy.

## 6. LLM Output

LLM output is strict JSON only:

```text
document_metadata_passport_v0
```

The output starts as draft/pending and becomes useful only after validator success. The model is required to set missing fields to null, include evidence refs and set review flags when metadata is incomplete or conflicting.

## 7. Validator Checks

The validator must fail closed and check:

- exact schema version;
- run/document/case scope;
- all required fields;
- enum/date/hash formats;
- prompt ref/version/hash/model id;
- evidence refs exist and belong to the same run/document;
- no forbidden fields or raw-content markers;
- confidence values are bounded;
- missing fields are explicit;
- review required is true when needed;
- safety flags remain false for source facts, tax, declaration, XLS/XLSX, OCR/VLM and Knowledge.

## 8. Passport Effect On Source Eligibility

Source eligibility v2 should use:

```text
technical profile
+ taxonomy candidate
+ document_metadata_passport_v0
+ blockers
+ duplicate state
+ case scope
```

PDF/HTML source promotion is allowed only when:

- technical profile proves text/table evidence without OCR/VLM;
- passport validator passed;
- passport supports source broker-report role;
- required metadata is present or approved alternatives are present;
- relevant financial sections are detected;
- terminal blockers are absent;
- duplicate state is resolved;
- explicit source policy allows promotion.

If metadata is incomplete, the document moves to metadata review, not silent exclusion.

## 9. Applying To case_group_002

The passport stage should target the known V2 gap:

- total documents: 16;
- accepted reduced Gate 2 subset: 2;
- duplicate canonical-choice review: 1;
- methodology/output artifacts: 2;
- OCR required after V2: 0;
- source-role policy review: 11.

The 11 source-policy-review documents are the useful target for LLM metadata passporting. The passport can help decide whether each document is a source broker report, methodology/output artifact, duplicate, outside scope, or metadata-review item.

This does not authorize source-fact extraction or Gate 2. It only prepares a safer metadata decision layer before eligibility v2.

## 10. Code Changes Needed In Next Implementation Slice

Required next code changes:

1. Add prompt resolver/factory for OpenWebUI Prompt source.
2. Add LLM-friendly package builder.
3. Add OpenWebUI model invocation adapter from the Pipe/runtime.
4. Add `document_metadata_passport_v0` schema and validator.
5. Add ArtifactStore artifact types for input package, prompt snapshot, raw output, validated passport and passport validation.
6. Add eligibility v2 integration behind a feature flag/config.
7. Add synthetic tests and process=false live smoke.

No OpenWebUI core patch is recommended. No separate user-facing sidecar UI is recommended.

## 11. Risks

Remaining risks:

- OpenWebUI Prompt internals/API can drift;
- prompt access can be bypassed if implemented with broad admin/service reads;
- prompt body or private input can leak if response/log sanitization is weak;
- LLM can hallucinate metadata without validator enforcement;
- passport stage can accidentally drift into source-fact extraction if prompt/validator are weak;
- provider/data policy must approve customer document metadata classification;
- latency/cost may be high for large packages;
- first implementation must prove no Knowledge/vector regression.

## 12. Deliverables Created

Created:

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_LLM_PASSPORT_RESEARCH.md`
- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_LLM_DOCUMENT_METADATA_PASSPORT.blueprint.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT.v0.md`
- `docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT_PROMPT.v0.md`
- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_LLM_DOCUMENT_METADATA_PASSPORT_RESEARCH.report.md`

## 13. Commands And Checks

Research/read commands used:

```powershell
Get-Content -LiteralPath docs\stage2\config\BROKER_REPORTS_OPENWEBUI_WORKSPACE_CONFIGURATION.v0_PROPOSAL.md -Encoding UTF8
Get-Content -LiteralPath docs\stage2\research\BROKER_REPORTS_OPENWEBUI_PER_MODEL_NO_RAG_UPLOAD_RESEARCH.md -Encoding UTF8
Get-Content -LiteralPath docs\stage2\contracts\BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md -Encoding UTF8
Get-Content -LiteralPath docs\stage2\contracts\BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md -Encoding UTF8
Get-Content -LiteralPath docs\reports\2026-07-08\OPENWEBUI_BROKER_REPORTS_GATE1_PROCESS_FALSE_PRIVATE_INTAKE_SMOKE.report.md -Encoding UTF8
Get-Content -LiteralPath docs\reports\2026-07-08\OPENWEBUI_BROKER_REPORTS_GATE1_RAW_UPLOAD_RAG_VECTORIZATION_GAP.report.md -Encoding UTF8
Get-Content -LiteralPath services\broker-reports-gate1-proof\openwebui_actions\broker_reports_gate1_pipe.py -Encoding UTF8
Get-Content -LiteralPath services\broker-reports-gate1-proof\broker_reports_gate1\normalizer.py -Encoding UTF8
```

Docs-only validation executed:

```powershell
git diff --check -- docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_LLM_PASSPORT_RESEARCH.md docs/stage2/blueprints/BROKER_REPORTS_GATE1_LLM_DOCUMENT_METADATA_PASSPORT.blueprint.md docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT.v0.md docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT_PROMPT.v0.md docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_LLM_DOCUMENT_METADATA_PASSPORT_RESEARCH.report.md
$paths = @('docs\stage2\research\BROKER_REPORTS_OPENWEBUI_NATIVE_LLM_PASSPORT_RESEARCH.md','docs\stage2\blueprints\BROKER_REPORTS_GATE1_LLM_DOCUMENT_METADATA_PASSPORT.blueprint.md','docs\stage2\contracts\BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT.v0.md','docs\stage2\contracts\BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT_PROMPT.v0.md','docs\reports\2026-07-08\OPENWEBUI_BROKER_REPORTS_LLM_DOCUMENT_METADATA_PASSPORT_RESEARCH.report.md'); foreach ($p in $paths) { Test-Path -LiteralPath $p }
rg -n <redacted-secret-and-private-runtime-marker-patterns> <created-docs>
```

Result:

```text
all five requested files exist
UTF-8 BOM confirmed for all five files
git diff --check passed
secret/private-runtime-path scan returned no matches
```

## 14. Decision

Proceed to the next implementation slice.

The implementation should be narrow: prompt resolver, private input package, OpenWebUI model call, strict JSON validator, ArtifactStore persistence and eligibility v2 integration. Do not redesign the current Pipe/ArtifactStore architecture.
