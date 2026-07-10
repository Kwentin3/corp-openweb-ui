# OpenWebUI Broker Reports Gate 1 Raw Upload RAG Vectorization Gap Report

Date: 2026-07-08

Scope: Broker Reports / XLS NDFL Gate 1 runtime boundary after live OpenWebUI bulk upload incident.

Status:

- BROKER_REPORTS_GATE1_RAW_UPLOAD_RAG_VECTORIZATION_GAP_CONFIRMED
- CUSTOMER_APPROVED_OPENWEBUI_BULK_UPLOAD_BLOCKED_UNTIL_NO_VECTOR_INTAKE_PROVEN
- GATE1_PIPE_ARTIFACTSTORE_CONTRACT_STILL_VALID_BUT_INCOMPLETE_FOR_SOURCE_UPLOAD_STAGE

This report intentionally does not print raw customer filenames, OpenWebUI file ids, private paths, document text, rows, sheet names, secrets, SSH targets or env values.

## 1. Executive Summary

The incident exposed a real contract gap.

The current Gate 1 implementation and reports correctly prove that private derived artifacts do not go to chat or OpenWebUI Knowledge, and that Gate 1 private slices are persisted in the project ArtifactStore. However, this is not the same as proving that raw customer uploaded files avoid OpenWebUI's native per-file RAG/vector processing.

During the live bulk upload incident, OpenWebUI Knowledge remained empty, but OpenWebUI still created/used native upload and vector storage:

- OpenWebUI `file` rows: 165.
- OpenWebUI `document` rows: 0.
- OpenWebUI `knowledge` rows: 0.
- Upload payload area: 165 files, about 999M.
- OpenWebUI vector DB area: 494 files, about 202M.
- Logs during the incident window included embedding/vector activity.

Conclusion: `customer_docs_loaded_to_knowledge=false` is true but insufficient. For the NDFL broker reports workflow, the required safety property must be expanded to:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
```

Until that is proven on synthetic and then customer-approved files, the operator should not use normal OpenWebUI bulk chat upload for Broker Reports customer packages.

## 2. What The Existing Contract Already Says

The native storage research already separates OpenWebUI native surfaces:

- uploaded files are good for source upload bytes, metadata, owner, hash, storage path/object and extracted content when processed;
- Knowledge/RAG is only for approved methodology/reference material, not raw case documents;
- Vector DB is native RAG storage, not the Gate 1 authoritative artifact store;
- Object/local storage is for OpenWebUI source uploads, not private derived slices by default.

Relevant local references:

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md:57`
- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md:60`
- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md:63`
- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md:72`
- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md:77`
- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md:80`

The same research says Knowledge is not suitable for:

- raw customer broker reports by default;
- temporary case uploads;
- private normalized slices;
- duplicate/corrupt/encrypted diagnostic data;
- per-case retention and purge artifacts;
- Gate 2 authoritative extraction input.

Relevant local reference:

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md:124`

The Workspace configuration also says:

- use Knowledge only for approved methodology, official requirements and examples;
- do not treat raw customer uploads as Knowledge.

Relevant local reference:

- `docs/stage2/config/BROKER_REPORTS_OPENWEBUI_WORKSPACE_CONFIGURATION.v0_PROPOSAL.md:88`

## 3. What Was Actually Proven Before The Incident

The ArtifactStore persistence report chose a hybrid native-first model:

OpenWebUI owns:

- source file upload;
- source file owner/access checks;
- native source file deletion;
- chat/message UX;
- Workspace Model and Pipe entrypoint;
- approved reusable Knowledge only.

Project ArtifactStore owns:

- normalization run records;
- safe internal artifacts;
- private normalized text/table slices;
- validation result;
- Gate 2 handoff refs;
- retention policy;
- expiry and purge status;
- tombstones.

Relevant local reference:

- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_ARTIFACTSTORE_PERSISTENCE_AND_RETENTION.report.md:44`

The live ArtifactStore smoke proved:

- full JSON was not the primary chat output;
- private internals were absent from chat;
- raw uploaded file ids were absent from chat;
- raw source filenames were absent from chat;
- private slices were not stored through `openwebui_knowledge`;
- `customer_docs_loaded_to_knowledge=false`;
- Knowledge count stayed unchanged.

Relevant local reference:

- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_LIVE_ARTIFACTSTORE_RETENTION_SMOKE.report.md:179`

This proof is useful and remains valid. Its limitation is precise: it did not prove that OpenWebUI's native file upload path skipped extraction, embeddings or vector collection writes for the raw uploaded files.

## 4. Live Incident Evidence

The incident happened after the customer package was uploaded through normal OpenWebUI chat upload.

Observed during triage before recovery:

- `openwebui` was formally up, but load was high.
- CPU was repeatedly around 180-198% for the OpenWebUI container.
- Memory was about 2.6 GiB out of 3.8 GiB.
- Swap was not configured.
- The two-hour log window had tens of thousands of lines with embedding/vector-related counts.
- Knowledge count remained 0.

Recovery performed:

- Restarted only the `openwebui` container.
- Did not delete volumes.
- Did not touch `stage2-stt`, `searxng`, `searxng-valkey` or `openwebui-traefik`.
- Service recovered to healthy.

Post-recovery aggregated runtime snapshot:

```text
openwebui status: healthy
openwebui cpu: about 0.15%
openwebui memory: about 987 MiB / 3.823 GiB
OpenWebUI DB file rows: 165
OpenWebUI DB document rows: 0
OpenWebUI DB knowledge rows: 0
OpenWebUI DB chat rows: 59
uploads files: 165
uploads size: about 999M
cache files: 126
cache size: about 1.1G
vector_db files: 494
vector_db size: about 202M
broker_reports_gate1 files: 21
broker_reports_gate1 size: about 660K
```

The important distinction:

```text
Knowledge stayed empty.
Vector DB was not empty.
Therefore Knowledge guard did not imply no vectorization.
```

No raw file identifiers or filenames were inspected for this report.

## 5. Current Code Boundary

The Pipe starts after OpenWebUI has already accepted files into its native file path. The Pipe collects file refs, converts them to `FileInput`, runs the backend normalizer, builds retention policy and persists Gate 1 artifacts:

- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py:91`
- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py:111`
- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py:123`

ArtifactStore correctly blocks private/customer artifacts from `openwebui_knowledge`:

- `services/broker-reports-gate1-proof/broker_reports_gate1/artifact_store.py:370`

This means the Pipe and ArtifactStore are not the direct cause of vectorization. The gap is earlier:

```text
OpenWebUI source upload
-> native file processing / extraction / possible per-file RAG/vector path
-> Pipe receives file refs
-> Gate 1 normalizer
-> ArtifactStore
```

The current contract starts too late. It protects chat, Knowledge and derived artifacts, but does not control or prove the source upload stage.

## 6. Root Cause

Root cause: Gate 1 reused the normal OpenWebUI chat attachment path as the source-file custody layer without proving a no-RAG/no-vector mode for Broker Reports case uploads.

Contributing factors:

- The docs used `Knowledge` as the main prohibited destination for customer documents, but did not explicitly treat per-file vector collections as a separate prohibited destination.
- The live smoke checked Knowledge count and ArtifactStore storage backends, but did not check vector DB delta.
- The operator package was uploaded as a bulk chat package, which triggered normal OpenWebUI file handling and created heavy embedding/vector workload.
- The server has limited RAM and no swap, so bulk embedding created a visible operational incident.

This is not a reason to globally disable RAG. Native RAG remains useful for ordinary chats and approved Knowledge. The problem is specific to Broker Reports / NDFL case source documents.

## 7. Risk Assessment

Privacy risk:

- Raw customer documents may become retrievable through native per-file RAG context, depending on OpenWebUI access rules and chat/file relations.
- Even if not attached to reusable Knowledge, vector collections are still another derived storage surface.

Retention risk:

- ArtifactStore has explicit retention and purge semantics.
- OpenWebUI native upload/vector residue has a separate lifecycle.
- Current Gate 1 purge proof does not prove cleanup of OpenWebUI source upload and vector residue.

Operational risk:

- Bulk customer packages can trigger expensive extraction/embedding work.
- The observed instance has about 3.8 GiB RAM and no swap.
- Large package upload can degrade the service even when Knowledge remains empty.

Acceptance risk:

- A report saying `customer_docs_loaded_to_knowledge=false` can be technically true while the stronger business expectation "customer docs did not enter RAG/vector storage" is false.

## 8. Required Contract Update

Add an explicit Gate 1 source upload safety boundary:

```text
Broker Reports customer source documents must not be loaded into OpenWebUI Knowledge,
must not be vectorized into OpenWebUI native RAG/vector collections,
and must not be available as reusable retrieval material.
```

Suggested safety flags:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
openwebui_source_upload_mode=no_rag_case_attachment
openwebui_vector_db_delta_for_case=0
openwebui_source_upload_purge_proven=true
```

Suggested status names for future proof:

```text
LIVE_GATE1_RAW_CASE_UPLOAD_NO_RAG_MODE_PROVEN
LIVE_GATE1_VECTOR_DB_GUARD_PROVEN
LIVE_GATE1_SOURCE_UPLOAD_PURGE_PROVEN
READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE
```

Do not use `READY_FOR_CUSTOMER_APPROVED_TEST_PACKAGE` again for live customer upload unless the vector guard is proven.

## 9. Recommended Implementation Path

### Option A: Native OpenWebUI No-RAG Attachment Mode

Preferred if OpenWebUI v0.9.6 exposes a supported way to upload/attach files without extraction/vector processing.

Required proof:

- source/API inspection identifies the exact request field, endpoint behavior or Admin setting;
- synthetic file upload through the Broker Reports Workspace path succeeds;
- Pipe receives file refs or bytes;
- `file` row may exist, but `document`, `knowledge` and vector DB delta for the case remain zero;
- chat output remains compact Russian;
- ArtifactStore artifacts persist;
- purge removes source payloads and leaves only allowed tombstones/artifact records.

Pros:

- keeps native OpenWebUI UX;
- minimal architecture change;
- no separate user-facing UI.

Risk:

- must be proven against the exact deployed OpenWebUI version, not guessed from docs.

### Option B: Project-Owned Private Case Intake

Use a project-owned intake path for Broker Reports customer files. The operator uploads the package into a private ArtifactStore/source area, and the Pipe/Gate 1 receives opaque source refs instead of relying on normal OpenWebUI chat upload.

This can still preserve the user-facing OpenWebUI chat experience:

- user selects Broker Reports Workspace Model;
- user sends a command with a case/package ref;
- Gate 1 resolves source refs through the project backend;
- chat receives only compact Russian report and safe refs.

Pros:

- strongest lifecycle and retention control;
- avoids native vectorization by construction;
- aligns with ArtifactStore and Gate 2 resolver model.

Risk:

- needs a small authenticated intake/resolver surface;
- must not become a separate user-facing sidecar UI unless explicitly approved.

### Option C: Thin OpenWebUI Extension Surface

If native no-RAG attachment mode does not exist, add a minimal OpenWebUI extension path that routes Broker Reports uploads to project intake while keeping the visible workflow inside OpenWebUI.

Pros:

- can keep one UI surface;
- avoids deep OpenWebUI core patching.

Risk:

- static loader / DOM coupling can be brittle;
- should be used only with targeted proof and limited scope.

### Option D: Patch OpenWebUI Core

Not recommended for this slice.

Reason:

- higher maintenance risk;
- version drift risk;
- contradicts the current "do not patch OpenWebUI core" operating constraint unless a hard blocker is proven.

## 10. Immediate Operational Recommendations

1. Stop using normal OpenWebUI bulk chat upload for Broker Reports customer packages.

2. Keep ordinary chat/RAG behavior unchanged for non-Broker-Reports scenarios.

3. Treat the already uploaded bulk package as runtime residue. Do not delete it silently. With explicit operator approval, run a dedicated cleanup/purge procedure that verifies:

- OpenWebUI file rows decrease as expected;
- upload payloads are removed;
- vector collection residue is removed;
- Knowledge stays unchanged;
- ArtifactStore records/tombstones remain within policy.

4. For the next customer-approved attempt, use only a small synthetic proof first, then the private `case_group_002` package only after no-vector intake is proven.

5. Add vector DB delta checks to all future Gate 1 live smokes.

## 11. Proposed Verification Slice

Slice name:

```text
Gate 1 Broker Reports No-RAG Source Intake Proof
```

Synthetic acceptance:

1. Start with a clean baseline:

```text
file_count_before
document_count_before
knowledge_count_before
vector_db_file_count_before
vector_db_size_before
```

2. Upload two synthetic files through the intended Broker Reports path.

3. Run `broker_reports_gate1_pipe`.

4. Assert:

```text
chat_visible_report_is_compact_russian=true
full_json_primary_output=false
private_slices_in_chat=false
customer_docs_loaded_to_knowledge=false
document_count_delta=0
knowledge_count_delta=0
vector_db_delta_for_case=0
artifactstore_artifacts_persisted=true
gate2_handoff_uses_opaque_refs=true
source_fact_extraction_performed=false
tax_correctness_claimed=false
declaration_generated=false
xlsx_generated=false
ocr_performed=false
```

5. Purge the synthetic run and assert:

```text
source_payloads_deleted=true
vector_residue_deleted_or_never_created=true
private_payloads_deleted=true
allowed_tombstones_only=true
resolver_denies_purged_refs=true
```

Customer-approved acceptance:

- Repeat the same checks with the selected `case_group_002` package.
- Do not print raw file names, paths, file ids, row text or private content.
- Only then mark customer-approved package as ready.

## 12. Documentation Updates Needed

Update or add docs in the next implementation slice:

- Artifact lifecycle contract: add OpenWebUI source upload/vector lifecycle as a separate boundary.
- Workspace configuration: state that raw case uploads must use no-RAG case intake, not normal chat bulk upload.
- Live smoke report template: add vector DB delta proof.
- Operator handoff: add "do not upload package through normal chat attachment until no-RAG intake is proven."
- Customer-approved package grouping report: downgrade readiness wording if it implies live upload readiness without vector guard.

## 13. Current Go / No-Go

No-go for normal OpenWebUI bulk upload of Broker Reports customer documents.

Go for:

- synthetic no-RAG source intake research/proof;
- cleanup planning for already uploaded residue;
- preserving the current Pipe, normalizer, ArtifactStore, retention and resolver architecture.

Do not proceed to customer-approved live package upload until:

```text
LIVE_GATE1_RAW_CASE_UPLOAD_NO_RAG_MODE_PROVEN
LIVE_GATE1_VECTOR_DB_GUARD_PROVEN
LIVE_GATE1_SOURCE_UPLOAD_PURGE_PROVEN
```

are backed by runtime evidence.

## 14. Commands And Checks Used

Read-only / diagnostic checks used for this report:

```text
rg over docs/stage2, docs/reports/2026-07-08 and services/broker-reports-gate1-proof
git status -sb
SSH read-only docker ps / docker stats
OpenWebUI sqlite aggregate counts for file/document/knowledge/chat
OpenWebUI runtime directory aggregate counts and sizes
OpenWebUI log keyword counts without printing raw log lines
```

Recovery action already performed before this report:

```text
docker restart openwebui
```

No repository code was changed by the recovery action. No customer document names, ids, private paths or content were printed.

## 15. Final Recommendation

Keep the current Gate 1 Pipe and ArtifactStore architecture. It is still the right shape for derived artifacts and Gate 2 handoff.

Change the source intake contract. Broker Reports source files must enter Gate 1 through a proven no-RAG/no-vector path. The next engineering slice should be a narrow runtime proof, not a broad redesign:

```text
find/prove native no-RAG attachment mode
or implement project-owned private source intake
then prove vector_db delta = 0 and purge behavior
```

Until that proof exists, the live customer-approved package should remain blocked from normal OpenWebUI bulk upload.
