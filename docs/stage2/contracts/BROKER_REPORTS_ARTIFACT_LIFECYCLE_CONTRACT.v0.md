# Broker Reports Artifact Lifecycle Contract v0

Status: ARTIFACT_LIFECYCLE_CONTRACT_READY
Date: 2026-07-08
Scope: typed artifact fields, lifecycle states, access rules and purge behavior for Broker Reports Gate 1 to Gate 2.

## 1. Contract Goals

The contract gives Gate 1 a durable artifact boundary without turning OpenWebUI chat, Knowledge or Function internals into the system of record.

The contract must support:

- same-user/same-case access checks;
- safe chat projection;
- private slice storage;
- explicit retention;
- purge and tombstone behavior;
- Gate 2 handoff by opaque refs.

The contract also requires a source-intake precondition: raw customer case uploads must not be accepted for customer-approved Gate 1 until OpenWebUI native extraction/vectorization is blocked or bypassed for the Broker Reports route. Empty Knowledge is not enough proof.

Required source-intake precondition:

```text
customer_docs_loaded_to_knowledge=false
raw_customer_case_uploads_vectorized_by_openwebui=false
raw_customer_case_uploads_used_as_native_rag_sources=false
raw_customer_case_uploads_not_extracted_into_openwebui_chat_context=true
gate1_pipe_receives_only_opaque_source_refs=true
```

## 2. Required Record Fields

Every artifact record must include:

| Field | Type | Required | Notes |
|---|---|---|---|
| `artifact_id` | string | yes | Opaque id, not guessable. |
| `artifact_type` | enum | yes | See section 5. |
| `schema_version` | string | yes | Example: `broker_reports_artifact_v0`. |
| `case_id` | string/null | yes | Required for customer-approved and production cases. |
| `chat_id` | string/null | yes | OpenWebUI chat context when invoked from chat. |
| `user_id` | string | yes | OpenWebUI user id. |
| `normalization_run_id` | string | yes | Run root id. |
| `document_id` | string/null | yes | Present for document-scoped artifacts. |
| `source_file_ref` | object/null | yes | Native source file reference and safe metadata. |
| `visibility` | enum | yes | `chat_visible`, `safe_internal`, `private_case`, `debug_ephemeral`, `forbidden`. |
| `storage_backend` | enum | yes | See section 6. |
| `retention_policy` | object | yes | Mode, TTL, expiry and cascade rules. |
| `created_at` | ISO datetime | yes | UTC. |
| `updated_at` | ISO datetime | yes | UTC. |
| `expires_at` | ISO datetime/null | yes | Required unless policy is explicit manual/case retention. |
| `purge_status` | enum | yes | `active`, `expired`, `purge_pending`, `purged`, `blocked`. |
| `access_policy` | object | yes | User/case/workspace requirements. |
| `validation_status` | enum | yes | `pending`, `validated`, `blocked`, `privacy_failed`. |

Recommended optional fields:

- `workspace_model_id`;
- `message_id`;
- `parent_artifact_ids`;
- `payload_kind`;
- `payload_ref`;
- `payload_inline_json`;
- `checksum_sha256`;
- `payload_size_bytes`;
- `safe_metadata`;
- `warning_codes`;
- `created_by`;
- `deleted_at`;
- `purged_at`;
- `source_delete_observed_at`.

## 3. Lifecycle Statuses

Allowed lifecycle statuses:

- `created`;
- `validated`;
- `visible_safe`;
- `private_ready`;
- `blocked`;
- `expired`;
- `purge_pending`;
- `purged`;
- `privacy_failed`.

Status meaning:

| Status | Meaning |
|---|---|
| `created` | Record exists, payload may still be pending validation. |
| `validated` | Safe/privacy validation passed for this artifact. |
| `visible_safe` | Artifact or projection may be shown in chat. |
| `private_ready` | Private payload may be resolved by same-context Gate 2 only. |
| `blocked` | Artifact cannot move forward without review or missing prerequisite. |
| `expired` | TTL elapsed; payload should not be served. |
| `purge_pending` | Purge job/operator has marked payload for deletion. |
| `purged` | Payload deleted; only allowed tombstone remains. |
| `privacy_failed` | Artifact failed privacy projection and must not be published. |

## 4. Valid Transitions

| From | To | Condition |
|---|---|---|
| `created` | `validated` | Schema and privacy validation pass. |
| `created` | `blocked` | Unsupported/corrupt/encrypted/duplicate review condition. |
| `created` | `privacy_failed` | Safe projection contains private/raw fields. |
| `validated` | `visible_safe` | Artifact visibility is `chat_visible`. |
| `validated` | `private_ready` | Artifact visibility is `private_case`. |
| `visible_safe` | `expired` | Retention expires. |
| `private_ready` | `expired` | Retention expires or source delete invalidates payload. |
| `blocked` | `purge_pending` | Retention or operator purge. |
| `expired` | `purge_pending` | Purge worker begins hard-delete. |
| `privacy_failed` | `purge_pending` | Diagnostic retention expires or operator confirms purge. |
| `purge_pending` | `purged` | Payload deletion completed. |

No transition out of `purged` may restore payload. A new run must create new artifact ids.

Artifact identity is semantically immutable. `put_record` may return the
existing record only for an idempotent replay whose contract fields, scope,
visibility, retention, source ref, safe metadata and payload are identical.
Different content under an existing `artifact_id` fails closed with
`artifact_immutable`; it must be written under a new id. Explicit lifecycle,
expiry, source-deletion and purge operations remain the only allowed metadata
mutations and cannot replace business payload.

## 5. Artifact Types

Allowed Gate 1 artifact types:

- `source_file_ref_v0`;
- `normalization_run_v0`;
- `document_inventory_v0`;
- `technical_readability_profile_v0`;
- `taxonomy_candidates_v0`;
- `normalization_blockers_v0`;
- `private_normalized_text_slice_v0`;
- `private_normalized_table_slice_v0`;
- `chat_visible_normalization_report_v0`;
- `validation_result_v0`;
- `gate2_handoff_v0`;
- `debug_diagnostic_v0`.

`debug_diagnostic_v0` is disabled in production unless an explicit operator policy enables it.

Every new private normalized slice must validate as
`source_unit_provenance_v0`. Table slices carry stable table, row, range, cell,
cell-value and source-value refs. Text slices carry stable segment, section,
page/range where available, character-span and source-value refs. Both carry
parser/source/payload checksum refs and `source_unit_coverage_v0` accounting.
Only `NormalizedSliceProvenanceFactory.create` may mint these refs; consumers
resolve and recompute them through the private payload and checksum policy.

## 6. Storage Backends

Allowed storage backend values:

| Backend | Meaning | Allowed for private slices |
|---|---|---|
| `openwebui_file` | Native OpenWebUI file record/storage object. | No, source uploads only by default. |
| `openwebui_chat` | Native chat/message content. | No. |
| `openwebui_knowledge` | Native Knowledge/RAG collection. | No. |
| `project_artifact_store` | Project metadata DB. | Metadata yes; payload by ref or inline if small/safe. |
| `project_artifact_payload` | Project payload storage for private/safe derived data. | Yes. |
| `none_tombstone` | No payload remains, record is a tombstone. | No payload. |

## 7. Source File Ref Shape

`source_file_ref` must be safe metadata only:

```json
{
  "provider": "openwebui",
  "openwebui_file_id": "opaque",
  "file_hash_sha256": "hex-or-null",
  "content_type": "application/pdf",
  "size_bytes": 12345,
  "source_deleted": false,
  "source_delete_observed_at": null
}
```

Do not put raw filenames, local paths, ZIP member names, sheet names or extracted customer text into chat-visible source refs.

For customer-approved cases, a `source_file_ref_v0` is valid only if the intake report proves that the corresponding OpenWebUI source upload did not create native RAG/vector state and did not store extracted source text in OpenWebUI file data. If that proof fails, the source ref may be kept only as a synthetic/debug tombstone or blocker evidence, not as customer-ready intake.

## 8. Access Rules

Artifact resolution must require:

- matching `user_id`, unless an approved admin/operator access path is used;
- matching `case_id` when the artifact is case-scoped;
- matching `chat_id` for chat-scoped MVP records without case id;
- matching `workspace_model_id` when available;
- lifecycle status that permits read;
- `purge_status=active`;
- `validation_status=validated` for any Gate 2 handoff;
- non-expired `expires_at` unless retention policy explicitly allows manual retention;
- visibility compatible with caller role.

Private artifacts:

- are never rendered in chat;
- are never loaded into Knowledge by default;
- are never returned to the LLM as raw prompt context without a Gate 2 projection step;
- require same-context resolver access;
- return typed errors on denial.

Safe artifacts:

- may be summarized in chat only through a whitelist projection;
- may include opaque refs;
- may include counts, blocker codes and readiness labels;
- must not include raw paths, secrets or private normalized content.

## 9. Retention Policy Shape

```json
{
  "mode": "customer_approved_test",
  "ttl_seconds": 1209600,
  "expires_at": "2026-07-22T00:00:00Z",
  "source_delete_cascades": true,
  "chat_delete_cascades": true,
  "keep_redacted_tombstone": true,
  "requires_manual_purge": false
}
```

Allowed modes:

- `synthetic_dev`;
- `api_smoke`;
- `customer_approved_test`;
- `production_case`;
- `manual_purge_required`;
- `expires_after_ttl`.

## 10. Failure Codes

Resolver and persistence code should use typed failure codes:

- `artifact_not_found`;
- `artifact_access_denied`;
- `artifact_expired`;
- `artifact_purged`;
- `artifact_immutable`;
- `artifact_blocked`;
- `artifact_privacy_failed`;
- `artifact_scope_unverified`;
- `source_file_unavailable`;
- `retention_policy_missing`;
- `knowledge_storage_forbidden`.
- `source_upload_vectorized_by_openwebui`;
- `source_upload_extracted_into_openwebui_file_data`;
- `source_upload_cleanup_vector_residue`.

All failure modes are fail-closed.

## 11. Chat Projection Contract

The chat-visible report may include:

- human-readable Russian status;
- file count;
- format summary;
- document role summary;
- blocker/warning summary;
- next-step instruction;
- safe opaque run ref.

The chat-visible report must not include:

- full JSON artifact package as primary output;
- private slice content;
- local paths;
- OpenWebUI raw file ids unless deliberately exposed as an opaque safe ref;
- filenames from customer uploads unless a separate policy permits them;
- extracted rows/text;
- secrets or environment values.

## 12. Gate 2 Handoff

Gate 2 handoff record:

```json
{
  "artifact_type": "gate2_handoff_v0",
  "normalization_run_id": "nr_...",
  "case_id": "case_...",
  "chat_id": "chat_...",
  "user_id": "user_...",
  "validation_status": "validated",
  "handoff_status": "ready_with_safe_refs",
  "safe_refs": ["art_..."],
  "private_slice_refs": ["art_..."],
  "blocker_refs": [],
  "created_at": "2026-07-08T00:00:00Z"
}
```

Gate 2 must resolve `private_slice_refs` through ArtifactStore. It must not parse private data from the chat message.

2026-07-10 handoff clarification: the JSON above is a legacy-minimal example.
The canonical Gate 2 semantic authority is a validated
`domain_context_packet_v0`; `gate2_handoff_v0` is its ArtifactStore resolver
manifest. Source-fact extraction must consume `next_stage_refs`,
`document_issue_refs`, and `private_slice_refs_by_next_stage_bucket`.
`included_document_refs` / the reduced subset is primary compatibility only and
must not be treated as the complete source-ready input. The proposed Gate 2
artifact placement is defined in
`BROKER_REPORTS_GATE2_SOURCE_FACT_EXTRACTION.v0.md`.

## 13. Customer-Approved Readiness Gate

Before any customer-approved package is uploaded, the latest Gate 1 source-intake smoke must prove:

- explicit `customer_approved_test` retention policy is configured;
- Knowledge delta is zero;
- document table delta is zero;
- vector DB collection/file delta for the case is zero;
- uploaded source file data does not contain extracted customer text;
- OpenWebUI file cleanup and ArtifactStore purge behavior are understood and documented;
- Gate 2 receives opaque refs only.

The 2026-07-08 synthetic no-RAG smoke rejected the native per-model candidate:
`file_context=false` did not stop default upload processing/vectorization on the
target route. The follow-up process-false smoke proved the project-owned private
intake fallback with zero vector/Knowledge/document deltas, ArtifactStore
persistence, resolver checks and purge/tombstones. Customer-approved upload is
allowed only through that `process=false` private intake path.

## Full-source private artifacts (2026-07-10)

`private_normalized_source_payload_v0` and
`private_normalized_source_unit_v0` inherit the same source/chat deletion
cascade, TTL/manual purge rules and redacted tombstone policy as other
`private_case` payload artifacts. They are persisted to
`project_artifact_payload`, require Gate 2 resolver access, and are forbidden in
OpenWebUI Knowledge, document extraction and vector storage. Partial parser or
budget status does not relax lifecycle or access checks.
