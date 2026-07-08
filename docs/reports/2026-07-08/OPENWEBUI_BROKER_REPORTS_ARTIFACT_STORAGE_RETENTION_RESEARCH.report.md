# OpenWebUI Broker Reports Artifact Storage Retention Research Report

Date: 2026-07-08
Scope: OpenWebUI-native artifact storage/lifecycle/retention research for Broker Reports Gate 1.

## 1. Status

- OPENWEBUI_NATIVE_STORAGE_RESEARCH_READY
- GATE1_ARTIFACT_STORAGE_RETENTION_BLUEPRINT_READY
- ARTIFACT_LIFECYCLE_CONTRACT_READY
- GATE1_USER_FRIENDLY_REPORT_UX_READY
- NATIVE_FIRST_STORAGE_DECISION_READY
- READY_FOR_STORAGE_IMPLEMENTATION_SLICE

Customer-approved test package readiness is not marked ready yet.

Reason: the boundary is now specified, but runtime storage and purge behavior are not implemented or smoke-proven yet. A customer-approved package should wait for the implementation slice and retention smoke.

## 2. Research Answer

OpenWebUI has strong native primitives for source uploads, file ownership, chat UX, Workspace Models, Functions/Pipes, Knowledge/RAG and storage providers. It does not give this Gate 1 workflow an already-proven, stable, per-case private artifact lifecycle for normalized slices, validation state, purge status and Gate 2 handoff.

Decision: use OpenWebUI natively for source files and chat; use a project ArtifactStore for derived Gate 1 artifacts.

## 3. What OpenWebUI Should Own

OpenWebUI should own:

- original uploaded files;
- file owner/access checks;
- source file storage and deletion;
- chat/message history;
- user-visible compact Gate 1 report;
- Workspace Model and Pipe entrypoint;
- approved reusable Knowledge for methodology/reference material.

OpenWebUI should not be treated as the authoritative store for private normalized slices or Gate 2 handoff state.

## 4. What Project ArtifactStore Should Own

Project ArtifactStore should own:

- `normalization_run_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `private_normalized_text_slice_v0`;
- `private_normalized_table_slice_v0`;
- `validation_result_v0`;
- `gate2_handoff_v0`;
- retention policy, expiry and purge status.

The local STT ArtifactStore is a useful implementation pattern for opaque refs, access context, SQLite sidecar mode, expiry and purge semantics, but it is not OpenWebUI-native evidence.

## 5. Knowledge Decision

Knowledge is allowed for:

- approved methodology;
- official instructions;
- stable examples safe for reuse.

Knowledge is forbidden by default for:

- raw customer broker reports;
- temporary case uploads;
- private normalized slices;
- duplicate/corrupt/encrypted diagnostics;
- Gate 2 authoritative extraction input.

## 6. Community/Unsupported Pattern Answer

Supported/native patterns:

- OpenWebUI files API and File Manager;
- file deletion with vector cleanup;
- Knowledge sync/diff/cleanup for approved reusable docs;
- Function/Pipe as the native model-like extension point.

Reasonable sidecar pattern:

- Pipe delegates stateful work to a project/external store while OpenWebUI remains the UX shell.

Unsupported or brittle for this slice:

- legacy Pipelines as target path;
- direct writes to OpenWebUI internal DB/models from Function code as the product contract;
- storing private artifacts in chat JSON;
- storing private case slices in Knowledge;
- relying on chat UI "Artifacts" as backend storage;
- relying on README-level artifact-storage wording before exact API/schema/ACL/retention proof exists on the target runtime.

## 7. Deliverables Created

- `docs/stage2/research/BROKER_REPORTS_OPENWEBUI_NATIVE_ARTIFACT_STORAGE_RESEARCH.md`
- `docs/stage2/blueprints/BROKER_REPORTS_GATE1_ARTIFACT_STORAGE_RETENTION.blueprint.md`
- `docs/stage2/contracts/BROKER_REPORTS_ARTIFACT_LIFECYCLE_CONTRACT.v0.md`
- `docs/stage2/ux/BROKER_REPORTS_GATE1_USER_FRIENDLY_REPORT_UX.md`
- `docs/reports/2026-07-08/OPENWEBUI_BROKER_REPORTS_ARTIFACT_STORAGE_RETENTION_RESEARCH.report.md`

## 8. Customer-Approved Package Decision

Do not proceed directly from the current chat-only proof to customer-approved documents.

Proceed after the storage implementation slice proves:

- derived artifacts persist in Project ArtifactStore;
- private slices are not in chat or Knowledge;
- source-file delete reconciliation works;
- chat-delete behavior is defined and tested;
- run purge deletes payloads and leaves only allowed tombstone;
- Gate 2 rejects expired/purged/wrong-user/wrong-case refs;
- compact Russian chat output replaces full JSON as the primary user output.

## 9. Sources

Official docs:

- https://docs.openwebui.com/reference/api-endpoints/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/chat-conversations/rag/
- https://docs.openwebui.com/features/extensibility/plugin/functions/
- https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/
- https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args/
- https://docs.openwebui.com/features/extensibility/plugin/development/under-the-hood/
- https://docs.openwebui.com/getting-started/advanced-topics/scaling/
- https://docs.openwebui.com/features/chat-conversations/chat-features/code-execution/artifacts/

Upstream source:

- https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/files.py
- https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/files.py
- https://github.com/open-webui/open-webui/blob/main/backend/open_webui/storage/provider.py
- https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/chats.py
- https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/chats.py

Community references:

- https://github.com/open-webui/open-webui/discussions/12091
- https://github.com/open-webui/open-webui/discussions/20949
- https://github.com/open-webui/open-webui/discussions/17337
