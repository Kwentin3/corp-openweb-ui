# OpenWebUI Broker Reports Gate 1: `process=false` Private Intake Smoke

Date: 2026-07-08

Status:

- `PROJECT_OWNED_PRIVATE_INTAKE_READY`
- `PROCESS_FALSE_UPLOAD_PROVEN`
- `LIVE_GATE1_VECTOR_DB_GUARD_PROVEN`
- `LIVE_GATE1_RAW_CASE_UPLOAD_NO_RAG_MODE_PROVEN`
- `LIVE_GATE1_SOURCE_UPLOAD_PURGE_PROVEN`
- `LIVE_GATE1_ARTIFACTSTORE_PERSISTENCE_PASSED`
- `LIVE_GATE1_COMPACT_RUSSIAN_REPORT_READY`
- `READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE`

## Scope

Проверялся не обычный native upload OpenWebUI, а проектный controlled intake:

`POST /api/v1/files/?process=false`
-> Workspace Model
-> `broker_reports_gate1_pipe`
-> backend normalizer
-> project ArtifactStore
-> compact Russian chat report
-> Gate 2 refs / resolver / retention smoke.

Customer documents were not used.

## Live Runtime Target

Updated live Function:

- Function id: `broker_reports_gate1_pipe`
- Live Function active: yes
- Workspace Model id: `test`
- Workspace Model base model: `broker_reports_gate1_pipe`
- Workspace Model capabilities after smoke: `file_upload=true`, `file_context=false`
- Workspace Model Knowledge attachments: `0`

Deployed bundle/version/source:

- Bundle header version: `0.4.0-backend-normalizer-bundled`
- Normalizer version: `gate1_backend_profiling_completion_v1`
- Local bundle SHA-256: `1b7136d11a1994691f4e9478d39b067077e6d29c599e0fbd4367279a9145c658`
- Live Function content SHA-256: `1b7136d11a1994691f4e9478d39b067077e6d29c599e0fbd4367279a9145c658`
- Hash parity: yes

## Retention Policy

The live Pipe used its configured explicit ArtifactStore policy:

- mode: `api_smoke`
- explicit: `true`
- ttl_seconds: `86400`

The embedded retention probe used:

- mode: `expires_after_ttl`
- explicit: `true`
- ttl_seconds: `1`

The customer-approved missing-policy guard was exercised by the live Pipe smoke: `customer_approved_test` without explicit retention policy is rejected.

## Synthetic Inputs

Used two repository synthetic fixtures from the Gate 1 normalization testdata directory:

- one plain-text synthetic broker report fixture;
- one CSV-like synthetic operations fixture.

Raw filenames, OpenWebUI file ids, source text, rows and private paths are intentionally not printed in this report.

## Chat-Visible Result

The chat-visible response was a compact Russian report, not full JSON:

- length: `1088`
- contains Cyrillic: yes
- contains Gate 2 handoff hint: yes
- JSON fence: no
- raw private slice text/rows: not found
- raw OpenWebUI file ids: not printed by the smoke

## Counter Evidence

Runtime counters were taken before upload, after `process=false` upload, after chat, and after source upload deletion.

| Counter | Before | After upload | After chat | After delete |
| --- | ---: | ---: | ---: | ---: |
| OpenWebUI `file` rows | 157 | 159 | 159 | 157 |
| OpenWebUI `document` rows | 0 | 0 | 0 | 0 |
| OpenWebUI `knowledge` rows | 0 | 0 | 0 | 0 |
| Vector collections | 123 | 123 | 123 | 123 |
| Vector dirs | 123 | 123 | 123 | 123 |
| Vector files | 502 | 502 | 502 | 502 |
| Vector bytes | 210086652 | 210086652 | 210086652 | 210086652 |
| ArtifactStore records | 332 | 332 | 368 | 368 |

Important interpretation:

- `process=false` upload created two temporary OpenWebUI file rows;
- it created zero OpenWebUI document rows;
- it created zero Knowledge rows;
- it created zero vector collection/file/byte delta;
- after source cleanup, OpenWebUI file rows returned to baseline.

The pre-existing vector baseline is residue from earlier native-upload experiments. The proven fact for this smoke is zero vector delta for the `process=false` path.

## ArtifactStore Evidence

The live case namespace produced 24 ArtifactStore records: main run plus retention probe. Type counts:

- `normalization_run_v0`: 2
- `source_file_ref_v0`: 4
- `document_inventory_v0`: 2
- `technical_readability_profile_v0`: 2
- `taxonomy_candidates_v0`: 2
- `normalization_blockers_v0`: 2
- `validation_result_v0`: 2
- `chat_visible_normalization_report_v0`: 2
- `private_normalized_text_slice_v0`: 2
- `private_normalized_table_slice_v0`: 2
- `gate2_handoff_v0`: 2

Retention/purge result after the live smoke:

- purged records: `24`
- `none_tombstone` records: `24`
- active private payload records: `0`

ArtifactStore boundary:

- Runtime boundary is inside the OpenWebUI backend data volume under the project `broker_reports_gate1` namespace.
- Individual private payload paths are intentionally not printed.

## Knowledge And Privacy Guard

Proven:

- `customer_docs_loaded_to_knowledge=false`
- Knowledge row delta: `0`
- Workspace Model Knowledge attachments: `0`
- no `openwebui_knowledge` storage backend in ArtifactStore records
- private slices did not appear in chat
- full private JSON was not returned as the primary business output

## Gate 2 Resolver And Purge

The live Pipe ArtifactStore smoke proved:

- Gate 2 receives opaque ArtifactStore refs, not chat JSON;
- resolver allows same-user/same-case/same-workspace context;
- resolver denies wrong-user;
- resolver denies wrong-case;
- resolver denies expired refs;
- resolver denies purged refs;
- purge removes private payloads and leaves tombstones.

## Source Upload Cleanup

The project-owned intake deleted the two temporary OpenWebUI source uploads after the Pipe run:

- upload count: `2`
- OpenWebUI file rows returned to baseline: yes
- vector delta after delete: `0`
- private payloads were purged/tombstoned by the live retention smoke.

This does not authorize ordinary OpenWebUI bulk upload. Customer-approved intake must use the project-owned `process=false` path.

## Forbidden Work Guard

Confirmed false:

- source-fact extraction
- tax calculation
- declaration generation
- XLS/XLSX export
- FNS filing
- OCR/VLM
- customer document processing
- customer document loading into Knowledge

## Commands Run

```powershell
python -m py_compile services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py
python services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py
python -m py_compile services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py
python -m compileall -q services/broker-reports-gate1-proof
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
git diff --check -- docs services/broker-reports-gate1-proof/scripts/live_process_false_private_intake_smoke.py services/broker-reports-gate1-proof/scripts/live_no_rag_source_intake_smoke.py
```

Supporting live checks:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py
```

OpenWebUI API checks were also used to verify live Function hash parity and Workspace Model capabilities. Credentials and env values are not printed.

## Decision

Customer-approved test package may proceed only through the project-owned `process=false` private intake path.

Do not use ordinary OpenWebUI source upload for the customer package, because prior native-upload research proved that per-model `file_context=false` alone did not prevent vectorization.
