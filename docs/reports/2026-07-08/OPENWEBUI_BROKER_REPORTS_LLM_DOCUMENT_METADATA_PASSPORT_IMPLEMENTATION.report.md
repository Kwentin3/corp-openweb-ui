# OpenWebUI Broker Reports Gate 1 / Gate 1.5 LLM Document Metadata Passport Implementation

Date: 2026-07-08

Scope: implementation and live smoke for Gate 1 / Gate 1.5 LLM-assisted document metadata passports through the proven `process=false` private intake path.

## Result

```text
GATE1_LLM_DOCUMENT_METADATA_PASSPORT_PARTIAL
BLOCKER: live synthetic process=false smoke built packages, resolved the managed OpenWebUI Prompt, called the configured OpenWebUI model and persisted passport artifacts, but the produced passports did not pass the fail-closed document_metadata_passport_v0 validator. case_group_002 was not rerun with customer documents after this synthetic validator failure.
```

## Implemented

- Added `broker_reports_gate1.document_passport` with:
  - OpenWebUI Prompt resolver factory;
  - prompt contract/hash capture;
  - private LLM document package builder;
  - strict `document_metadata_passport_v0` validator;
  - passport application stage that recomputes source eligibility v2, Gate 2 handoff, safe report and validation.
- Added ArtifactStore artifact types:
  - `llm_prompt_snapshot_v0`;
  - `llm_document_package_v0`;
  - `llm_passport_raw_output_v0`;
  - `document_metadata_passport_v0`;
  - `document_metadata_passport_validation_v0`.
- Integrated passports into source eligibility v2 without bypassing PDF/HTML source policy review.
- Preserved safe fallback: when passport is disabled or unavailable, existing Gate 1 behavior remains the base normalizer + compact Russian report.
- Updated bundled Pipe build order and rebuilt the live bundled Function.
- Added live operator scripts for Function/Prompt update and passport-enabled synthetic/case-group process=false runs.

## OpenWebUI-Native Prompt Mechanism

The managed prompt source is the OpenWebUI `prompt` table, resolved at runtime by command:

```text
broker_gate1_document_passport
```

The backend/Pipe does not store the final prompt body as Python source of truth. The live prompt was seeded from the contract document:

```text
docs/stage2/contracts/BROKER_REPORTS_DOCUMENT_METADATA_PASSPORT_PROMPT.v0.md
```

Live managed Prompt proof:

```json
{
  "prompt_ref": "broker_reports_document_metadata_passport_prompt_v0",
  "command": "broker_gate1_document_passport",
  "version": "passport-v0-2026-07-08-implementation",
  "prompt_hash": "7b93fcf0f29402520d7c774da559df3deab26953686cb8cef67fd1b803dc997d",
  "output_schema_version": "document_metadata_passport_v0",
  "template_id": "broker_reports.document_metadata_passport.v0"
}
```

## Live Function Deployment

Updated live Function:

```text
broker_reports_gate1_pipe
```

Final deployed bundled Pipe hash:

```text
c2c12868fc4c707c21181a11511c87800278f09492e37a43b98083a866561834
```

The Function content contains the Document Passport resolver and was verified after container restart.

## Bounded LLM Input/Output

Input packages are private `broker_reports_llm_document_package_v0` packages built from normalized slices, technical profiles, table/header signals, taxonomy candidates and safe evidence refs.

The package includes prompt ref/version/hash/model id and forbidden-task boundary. It is persisted as private ArtifactStore payload, not chat and not Knowledge.

Output is expected to be strict JSON for one `document_metadata_passport_v0` object per document. The validator is fail-closed and rejects:

- missing required fields;
- unknown fields;
- forbidden raw fields such as rows/text/path/file ids;
- prompt/model/run/document mismatch;
- unknown evidence refs;
- incomplete critical metadata without declared missing fields;
- high confidence without evidence refs.

## Source Eligibility V2

Validated passports are now an input to source eligibility v2:

- accepted source passports can promote previously unknown readable documents;
- methodology/output/duplicate/out-of-scope passports stay excluded or review-bound;
- PDF/HTML documents still do not bypass explicit source-policy review unless that policy is explicitly approved;
- metadata gaps create `metadata_review_required`.

## Synthetic Proof

Command:

```powershell
python services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py --env-file .env --enable-llm-passport --timeout 300 --settle-seconds 6
```

Synthetic files:

```text
2 existing synthetic Gate 1 fixtures from docs/stage2/testdata
```

No raw fixture filenames, OpenWebUI file ids, private paths, rows or text are printed here.

Final synthetic live result:

```json
{
  "status": "partial",
  "process_false_upload_count": 2,
  "llm_passport_prompt_resolved": true,
  "llm_passport_packages_built": true,
  "llm_passport_model_calls_passed": true,
  "llm_passport_artifacts_persisted": true,
  "llm_passport_validator_passed": false,
  "compact_russian_report": true,
  "private_slices_not_in_chat": true,
  "document_rows_zero_delta": true,
  "knowledge_rows_zero_delta": true,
  "vector_delta_zero_after_upload": true,
  "vector_delta_zero_after_chat": true,
  "vector_delta_zero_after_delete": true,
  "source_uploads_deleted": true,
  "artifact_private_payloads_purged_or_tombstoned": true
}
```

Persisted passport-related artifact types in the live synthetic run:

```json
{
  "llm_prompt_snapshot_v0": 1,
  "llm_document_package_v0": 2,
  "llm_passport_raw_output_v0": 2,
  "document_metadata_passport_v0": 2,
  "document_metadata_passport_validation_v0": 1
}
```

The live model call stage ran, but both passport records were validator-failed. The validator failure is the blocker for claiming `LIVE_GATE1_LLM_PASSPORT_VALIDATOR_PASSED`.

## case_group_002 Proof

`case_group_002` was not rerun through the LLM passport stage in this slice.

Reason: synthetic proof did not pass the strict validator. Running customer-approved documents after synthetic validator failure would not be an evidence-grade progression and would violate the intended gate discipline.

Therefore these statuses are not claimed:

- `CASE_GROUP_002_LLM_PASSPORT_RERUN_READY`;
- `CASE_GROUP_002_VECTOR_GUARD_PASSED`;
- `CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED`;
- `READY_FOR_CASE_GROUP_002_GATE2_SOURCE_FACT_PROOF`.

## ArtifactStore Evidence

Runtime boundary remains project ArtifactStore under OpenWebUI backend data. The report intentionally does not print private payload paths.

Synthetic proof showed:

- `llm_document_package_v0` persisted as private payload;
- `llm_passport_raw_output_v0` persisted as private payload;
- prompt snapshot, passport validation and passport records persisted as safe internal artifacts;
- private payloads were purged/tombstoned after source upload cleanup;
- no `openwebui_knowledge` storage backend was used for private artifacts.

## No-RAG / Vector / Knowledge Guard

The final synthetic run preserved the required private intake guard:

```json
{
  "document_rows_delta": 0,
  "knowledge_rows_delta": 0,
  "vector_collections_delta": 0,
  "vector_file_delta": 0,
  "vector_size_delta": 0,
  "customer_docs_loaded_to_knowledge": false
}
```

## Safety Flags

The implementation and live synthetic run did not:

- run Gate 2 source-fact extraction;
- extract trades/operations as source facts;
- calculate tax;
- generate declaration;
- generate XLS/XLSX;
- perform OCR/VLM;
- load source files, private slices or LLM packages into Knowledge/RAG.

## Commands Run

```powershell
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
python -m compileall -q services/broker-reports-gate1-proof
python services/broker-reports-gate1-proof/scripts/build_openwebui_pipe_bundle.py
python -m py_compile services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py
python services/broker-reports-gate1-proof/scripts/live_update_function_and_passport_prompt.py --env-file .env
python services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py --env-file .env --enable-llm-passport --timeout 300 --settle-seconds 6
```

Live runtime operations:

```text
docker restart openwebui
```

The restart was used to force Function code reload after live Function updates.

## Remaining Blocker

The remaining blocker is live strict passport validation. The model-call path returns a model response recorded as passed by the Pipe, but the resulting `document_metadata_passport_v0` objects fail the fail-closed validator on synthetic fixtures.

Next narrow slice:

1. Capture validator error-code summaries before purge in the live smoke script.
2. Tighten the managed Prompt or add a bounded repair loop that still validates fail-closed.
3. Re-run synthetic process=false passport smoke until `document_metadata_passport_validation_v0` passes.
4. Only then run `case_group_002` through the LLM passport stage.

## Gate 2 Readiness

Not ready for Gate 2 source-fact proof from this slice.

Reason: strict live passport validator pass is not proven, and `case_group_002` LLM passport rerun was intentionally not performed.
