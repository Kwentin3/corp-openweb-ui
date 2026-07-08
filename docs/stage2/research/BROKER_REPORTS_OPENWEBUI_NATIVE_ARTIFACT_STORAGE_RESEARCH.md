# Broker Reports OpenWebUI Native Artifact Storage Research

Status: OPENWEBUI_NATIVE_STORAGE_RESEARCH_READY
Date: 2026-07-08
Scope: Gate 1 Broker Reports storage, lifecycle and retention boundary research.

## 1. Decision Summary

Use a hybrid native-first model.

OpenWebUI should stay the native product shell for:

- source file upload;
- source file ownership and user access;
- source file deletion through File Manager / files API;
- chat messages and the compact user-visible Gate 1 report;
- Workspace Model and Pipe entrypoint;
- optional approved methodology/reference Knowledge.

The Broker Reports project must own a separate ArtifactStore for:

- normalization runs;
- safe run metadata;
- private normalized text/table slices;
- validation state;
- blockers and review decisions;
- Gate 2 handoff refs;
- explicit retention, expiration and purge status.

Do not store private Gate 1 slices in OpenWebUI Knowledge, chat JSON, Function Valves, or direct OpenWebUI DB extensions as the product contract.

## 2. Local Context Reviewed

Reviewed local Broker Reports and adjacent Stage 2 materials:

- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_GATE1_LIVE_PIPE_UPDATE_AND_SMOKE.report.md`
- `docs/reports/2026-07-07/OPENWEBUI_BROKER_REPORTS_GATE1_BACKEND_PROFILING_COMPLETION.report.md`
- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_NORMALIZATION_PIPELINE.blueprint.md`
- `docs/stage2/contracts/BROKER_REPORTS_GATE1_PIPELINE_TO_ARTIFACTS_MAPPING.v0.md`
- `docs/stage2/research/BROKER_REPORTS_GATE1_NORMALIZATION_TOOLING_AUDIT.md`
- `docs/stage2/proof/BROKER_REPORTS_GATE1_DOCUMENT_NORMALIZATION_PROOF_PLAN.md`
- `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/contracts.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/normalizer.py`
- `services/broker-reports-gate1-proof/broker_reports_gate1/safe_report.py`
- `services/stage2-stt/stage2_stt/artifact_store.py`
- `docs/stage2/contracts/STT_V2_ARTIFACT_STORAGE_RETENTION_CONTRACT.md`

The current Gate 1 proof produces safe and private in-memory artifact structures, then renders the safe report to chat. It does not yet persist project artifacts or enforce retention.

## 3. OpenWebUI Native Storage Surface

OpenWebUI natively stores these relevant objects:

| Native object | What it is good for | Gate 1 decision |
|---|---|---|
| Uploaded files | Source upload bytes, file metadata, owner, hash, storage path/object, extracted content when processed. | Use for original user uploads and source file references. |
| Chat and messages | User-visible workflow history, message files, safe status/report text. | Use for compact safe report and navigation refs only. |
| Chat-file relation | Links accessible file ids to a chat/message. | Use as native user-facing source attachment relation. |
| Knowledge/RAG | Reusable retrieval over approved documents and collections. | Use only for approved methodology/reference material, not raw case docs. |
| Functions/Pipes | Server-side Python extension point and native model-like entrypoint. | Use as Gate 1 entrypoint, not as artifact persistence. |
| Valves | Persisted Function/Pipe configuration. | Use for config only, not per-run artifacts. |
| Vector DB | RAG embeddings and per-file/knowledge collections. | Native RAG only; not the Gate 1 authoritative artifact store. |
| Object/local storage provider | Uploaded file payload storage under local, S3, GCS or Azure provider. | Use for source uploads through OpenWebUI, not private derived slices by default. |

OpenWebUI also has a chat "Artifacts" feature for renderable code/HTML/SVG style outputs. That is a UI feature, not a documented lifecycle API for Broker Reports private artifacts.

## 4. Uploaded Files

Official docs and upstream source show the native file flow:

- `POST /api/v1/files/` accepts uploaded files and may process them for RAG.
- A file row has `id`, `user_id`, `hash`, `filename`, `path`, `data`, `meta`, `created_at`, `updated_at`.
- Upload storage can be local under `DATA_DIR/uploads` or object storage through `STORAGE_PROVIDER`.
- File metadata includes name/content type/size/hash and optional extracted content/status.
- File access is owner/admin/access-rule based.
- File deletion removes the DB file row, storage object, knowledge links and vector collection entries.
- Chat files are linked through a chat/file relation and also appear in message file metadata.

Gate 1 should treat OpenWebUI uploaded files as source-file custody. The project can store `source_file_ref` with the OpenWebUI file id, hash, size, content type and storage provider class, but should not copy source bytes unless a future approved retention policy explicitly requires it.

## 5. Function/Pipe File Access

OpenWebUI Function reserved args expose file context:

- `__files__` contains file metadata;
- `__metadata__["files"]` can also carry file refs;
- binary payload is not passed directly for performance;
- a server-side Function can access file content by path or OpenWebUI APIs when allowed by deployment policy.

The current `broker_reports_gate1_pipe` already follows this native surface: user attaches files in OpenWebUI, the Pipe receives file refs, reads accessible bytes, and sends only a safe report back to chat.

The remaining gap is persistence and retention for the derived artifacts. That gap should be closed in a project ArtifactStore, not by treating transient Pipe invocation args as durable storage.

## 6. Chat And Message Metadata

OpenWebUI chat storage is useful for user-facing continuity:

- compact Gate 1 result message;
- safe run status;
- safe opaque refs for "show details" or Gate 2 navigation;
- visible blocker summaries;
- source attachment relationship.

Chat storage is not suitable as the system of record for Gate 1 artifacts because:

- chat JSON is optimized for conversation state, not artifact lifecycle;
- users/admins may delete chats;
- metadata shape can change with OpenWebUI internals;
- private slices must not be exposed in chat payloads;
- retention and purge must be explicit and testable outside message text.

Rule: chat may contain safe display refs, but Gate 2 must resolve artifacts through the project ArtifactStore.

## 7. Knowledge Suitability

Knowledge is suitable for:

- reviewed methodology;
- approved official instructions;
- stable examples that are safe to reuse across cases;
- source-attributed reference lookup.

Knowledge is not suitable for:

- raw customer broker reports by default;
- temporary case uploads;
- private normalized slices;
- duplicate/corrupt/encrypted diagnostic data;
- artifacts that need per-case retention and purge;
- Gate 2 authoritative extraction input.

If customer material is ever loaded into Knowledge, it must be an explicit approved workflow with its own owner, access scope, TTL and purge proof. Gate 1 default remains `customer_docs_loaded_to_knowledge=false`.

## 8. Community And Upstream Patterns

| Pattern | Source | Classification | Gate 1 decision |
|---|---|---|---|
| File Manager delete cleans uploaded file and embeddings | Official RAG/FAQ/docs and files router source | Native supported pattern | Use for source-file lifecycle. |
| Knowledge sync/diff/cleanup | Official Knowledge docs | Native supported pattern | Use only for approved reusable Knowledge. |
| Function/Pipe as a model-like entrypoint | Official Functions/Pipe docs | Native supported extension | Keep `broker_reports_gate1_pipe` as entrypoint. |
| Pipe delegating to external workflow/state store | Community LangGraph/Pipe pattern | Reasonable sidecar pattern | Aligns with Project ArtifactStore, with local access checks. |
| Legacy Pipelines with shared volume/file metadata assumptions | Community discussion and docs | Brittle/legacy | Do not use for Gate 1 target path. |
| Direct writes to OpenWebUI internal DB/models from Function | Under-the-hood docs say technically possible but internal APIs are unstable | Unsupported as product contract | Avoid except narrow admin migration tooling. |
| Chat UI "Artifacts" | Official Artifacts docs | Renderable chat UI feature | Not a Broker Reports artifact store. |
| README "persistent artifact storage" claim | OpenWebUI README | Unresolved during this research | Do not depend on it until exact API/schema/ACL/retention docs are found and proven on target runtime. |

## 9. Options A-F

| Option | Description | Strength | Weakness | Decision |
|---|---|---|---|---|
| A. Chat-only | Put full Gate 1 JSON or summary in chat. | Simple and native. | No reliable private storage, purge, Gate 2 handoff, or lifecycle. | Reject for artifacts; keep compact safe report only. |
| B. Uploaded file refs + metadata | Use OpenWebUI file ids and message file refs. | Native custody and deletion for source uploads. | Does not store derived slices or validation lifecycle. | Use as source-file layer. |
| C. Knowledge | Load documents/chunks into OpenWebUI Knowledge. | Useful RAG over approved references. | Reusable retrieval scope, vector cleanup complexity, not per-case artifact lifecycle. | Use for approved methodology only. |
| D. DB extension inside OpenWebUI | Add tables or write OpenWebUI internals directly. | Close to native data. | Fork/migration/internal API risk; unclear support boundary. | Avoid for Gate 1 MVP. |
| E. Project ArtifactStore | Sidecar DB/object store with typed records and retention. | Explicit lifecycle, private payloads, Gate 2 handoff, tests. | Additional service/schema to maintain. | Use for Gate 1 artifacts. |
| F. Hybrid native-first | OpenWebUI for native UX/source/chat, ArtifactStore for derived artifacts. | Uses OpenWebUI where it is strong and keeps lifecycle explicit. | Needs careful access-context binding. | Select. |

## 10. Recommended Native/Project Split

OpenWebUI native responsibilities:

- user login/session and OpenWebUI workspace access;
- source file upload and source file deletion;
- file ownership/access checks;
- chat/message UX;
- Workspace Model and Pipe invocation;
- approved Knowledge for methodology/reference only;
- optional safe generated report file later, if implemented through supported files API.

Project ArtifactStore responsibilities:

- `normalization_run_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `private_normalized_text_slice_v0`;
- `private_normalized_table_slice_v0`;
- `chat_visible_normalization_report_v0` metadata;
- validation result and privacy projection status;
- retention policy, expiration and purge status;
- Gate 2 resolver.

## 11. Risks And Unknowns

| Risk/unknown | Impact | Current treatment |
|---|---|---|
| OpenWebUI version drift between deployed `v0.9.6` and current docs/source | Native API behavior can differ. | Verify exact target runtime before implementation smoke. |
| File deletion does not automatically know project-derived artifacts | Private slices could outlive source file deletion. | ArtifactStore needs source-delete reconciliation and purge policy. |
| Chat deletion does not delete uploaded files or project artifacts by itself | User may assume case data is gone. | Define chat-delete retention trigger explicitly. |
| Direct OpenWebUI DB access from Functions is possible | Tempting shortcut. | Treat as unsupported/brittle for product storage. |
| README mentions persistent artifact storage | Could become useful later. | Unresolved until exact stable API and runtime proof exist. |
| Object storage deployment | File path assumptions can break. | Use OpenWebUI APIs/Storage abstraction when possible; avoid path-only contracts. |
| Knowledge oversharing | Customer docs may leak into reusable retrieval. | Keep default ban on customer source docs in Knowledge. |

## 12. Sources

Official OpenWebUI docs:

- API endpoints: https://docs.openwebui.com/reference/api-endpoints/
- Knowledge: https://docs.openwebui.com/features/workspace/knowledge/
- RAG and File Manager: https://docs.openwebui.com/features/chat-conversations/rag/
- FAQ: https://docs.openwebui.com/faq/
- Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/
- Pipe Functions: https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/
- Reserved arguments: https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args/
- Under the Hood: https://docs.openwebui.com/features/extensibility/plugin/development/under-the-hood/
- Scaling and storage providers: https://docs.openwebui.com/getting-started/advanced-topics/scaling/
- Chat Artifacts: https://docs.openwebui.com/features/chat-conversations/chat-features/code-execution/artifacts/
- Code execution storage: https://docs.openwebui.com/features/chat-conversations/chat-features/code-execution/

Upstream source inspected:

- Files model: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/files.py
- Files router: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/files.py
- Storage provider: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/storage/provider.py
- Chats model: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/chats.py
- Chats router: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/chats.py
- Config: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/config.py
- README: https://github.com/open-webui/open-webui/blob/main/README.md

Community references:

- Cleanup / old files discussion: https://github.com/open-webui/open-webui/discussions/12091
- File metadata / pipelines discussion: https://github.com/open-webui/open-webui/discussions/20949
- Pipe with external LangGraph state pattern: https://github.com/open-webui/open-webui/discussions/17337
