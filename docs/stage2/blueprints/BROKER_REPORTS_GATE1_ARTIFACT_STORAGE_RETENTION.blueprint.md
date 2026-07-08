# Broker Reports Gate 1 Artifact Storage And Retention Blueprint

Status: GATE1_ARTIFACT_STORAGE_RETENTION_BLUEPRINT_READY
Date: 2026-07-08
Scope: storage boundary, visibility, retention and Gate 2 handoff for Broker Reports Gate 1.

## 1. Non-Goals

This blueprint does not implement runtime code.

Out of scope:

- GUI smoke;
- customer document processing;
- tax/source-fact/declaration/XLS generation;
- OCR/VLM;
- automatic customer document loading into Knowledge;
- OpenWebUI core fork or DB migration;
- direct exposure of private slices in chat.

## 2. Ownership Map

| Boundary | Owner | Responsibilities |
|---|---|---|
| OpenWebUI native files | OpenWebUI | Source upload, source file owner, file access, source storage, source deletion and vector cleanup. |
| OpenWebUI chat | OpenWebUI | User-visible messages, source attachments, compact safe Gate 1 report. |
| OpenWebUI Knowledge | OpenWebUI admins / AI methodologist | Approved reusable methodology/reference only. |
| Broker Reports Pipe | Project | Entry orchestration, file-ref collection, byte access, normalizer call, safe chat output. |
| Broker Reports ArtifactStore | Project | Derived artifacts, private payloads, validation state, retention, purge, Gate 2 resolver. |
| Gate 2 extraction | Project | Reads safe/private refs through ArtifactStore with access context, never from chat JSON alone. |

## 3. Core Entities

| Entity | Required fields | Notes |
|---|---|---|
| User | `user_id` | OpenWebUI user id from invocation context. |
| Chat | `chat_id`, optional `message_id` | User-visible workflow context. |
| Case | `case_id` | Project case boundary. In MVP may be derived from chat until explicit case UX exists. |
| Workspace Model | `workspace_model_id` | Native entrypoint context, e.g. Broker Reports Gate 1 model. |
| Source File | `source_file_ref`, `openwebui_file_id`, `hash`, `size`, `content_type` | Native OpenWebUI custody. |
| Normalization Run | `normalization_run_id`, `status`, `created_at` | Project run boundary. |
| Document | `document_id`, `source_file_ref`, `role_candidate`, `profile_ref` | Safe document identity, no raw filename required in chat. |
| Artifact | `artifact_id`, `artifact_type`, `visibility`, `retention_policy`, `purge_status` | Stored in Project ArtifactStore unless explicitly native-safe. |
| Gate 2 Handoff | `handoff_id`, `normalization_run_id`, `safe_refs`, `private_slice_refs`, `blocker_refs` | Resolver validates user/case/workspace before returning payload. |

## 4. Target Flow

1. User attaches broker-report files in OpenWebUI chat.
2. Workspace Model routes to `broker_reports_gate1_pipe`.
3. Pipe receives OpenWebUI file refs and access context.
4. Pipe reads source bytes through supported native access path.
5. Normalizer builds safe and private Gate 1 artifact package.
6. ArtifactStore persists derived artifacts with retention policy.
7. Pipe returns compact Russian safe report to chat.
8. Gate 2 receives only safe refs and private opaque refs.
9. Gate 2 resolves refs through ArtifactStore using the same user/case/workspace access context.

## 5. Artifact Classes

| Artifact type | Visibility | Storage backend | Retention default | Gate 2 use |
|---|---|---|---|---|
| `source_file_ref_v0` | `safe_internal` | OpenWebUI file + ArtifactStore metadata | Follows source file plus case policy | Source provenance only. |
| `normalization_run_v0` | `safe_internal` | Project ArtifactStore | Case policy | Root of handoff. |
| `document_inventory_v0` | `chat_visible` subset, full safe internal | Project ArtifactStore | Case policy | Document list and readiness. |
| `technical_readability_profile_v0` | `safe_internal` | Project ArtifactStore | Case policy | Parser planning. |
| `taxonomy_candidates_v0` | `safe_internal` | Project ArtifactStore | Case policy | Gate 2 extraction hints. |
| `normalization_blockers_v0` | `chat_visible` summary, full safe internal | Project ArtifactStore | Case policy | Blocks or routes review. |
| `private_normalized_text_slice_v0` | `private_case` | Project ArtifactStore payload | Short TTL or case policy | Gate 2 private input. |
| `private_normalized_table_slice_v0` | `private_case` | Project ArtifactStore payload | Short TTL or case policy | Gate 2 private input. |
| `chat_visible_normalization_report_v0` | `chat_visible` | OpenWebUI chat + ArtifactStore safe copy | Chat plus case policy | User-facing result. |
| `validation_result_v0` | `safe_internal` | Project ArtifactStore | Case policy | Privacy and readiness gate. |
| `debug_diagnostic_v0` | `debug_ephemeral` | Project ArtifactStore payload or disabled | 24h max in non-production | Developer diagnosis only. |

## 6. Visibility Modes

| Visibility | Meaning | Allowed in chat |
|---|---|---|
| `chat_visible` | Safe, compact, user-facing summary. | Yes. |
| `safe_internal` | Safe metadata usable by Gate 2 and admin tooling. | Only safe refs or summarized fields. |
| `private_case` | Case-scoped private content, including normalized slices. | No. |
| `debug_ephemeral` | Temporary diagnostics for development or failed validation. | No. |
| `forbidden` | Payload category that must not be persisted. | No. |

## 7. Retention Modes

| Retention mode | Default behavior |
|---|---|
| `synthetic_dev` | Synthetic-only data. TTL 7 days unless explicitly purged sooner. |
| `api_smoke` | Smoke/proof data. Source uploads should be deleted immediately when smoke policy says so; derived artifacts TTL 24h to 7 days. |
| `customer_approved_test` | Customer-approved test package. TTL and purge window must be written before first run; suggested initial TTL 14 days. |
| `production_case` | Case policy from customer contract or internal retention rule. No silent indefinite storage. |
| `manual_purge_required` | Payloads stay blocked from auto hard-delete until operator decision is recorded. |
| `expires_after_ttl` | Generic expiry by `expires_at`; purge worker deletes payload and records tombstone. |

## 8. Deletion And Purge Triggers

| Trigger | Required behavior |
|---|---|
| Source file deleted in OpenWebUI | Mark `source_file_ref_v0` unavailable. If policy says source delete cascades, purge derived private slices. If not, keep only allowed tombstone/safe metadata and block rerun requiring source bytes. |
| Chat deleted in OpenWebUI | ArtifactStore must not assume artifacts are gone. If no `case_id` retention overrides chat, purge all artifacts scoped only to that chat. Otherwise detach from chat and keep case-scoped tombstone. |
| Case deleted | Purge project artifacts for the case and record redacted tombstones if audit policy allows. Optionally call OpenWebUI files API for source-file deletion only when integration has proven permission. |
| Run purge requested | Set `purge_pending`, delete private payloads, delete safe payloads allowed by policy, then set `purged`. |
| Retention expired | Expiry job moves expired artifacts to `purge_pending`, removes payloads, then sets `purged` or `expired` tombstone. |
| Privacy validation fails | Do not publish full report to chat. Persist only minimal failure state or short-lived diagnostic if enabled; mark run `privacy_failed`. |
| User access revoked | Resolver denies private/safe artifact access even if refs exist. |

## 9. Gate 2 Handoff Contract

Gate 2 may receive:

- `normalization_run_id`;
- safe `document_id` values;
- safe profile refs;
- safe taxonomy candidate refs;
- blocker refs;
- private slice refs as opaque ids only;
- `validation_status=validated`;
- `gate2_handoff_status=ready_with_safe_refs` or `blocked`.

Gate 2 must not receive:

- raw OpenWebUI file ids from chat text as authoritative input;
- raw filenames, paths, ZIP member names or sheet names in prompt text;
- private normalized slice content in chat;
- unvalidated slices;
- Knowledge chunks as substitute for ArtifactStore refs.

## 10. Resolver Rules

ArtifactStore resolver must validate:

- `user_id`;
- `case_id` or `chat_id`;
- `workspace_model_id` when available;
- `normalization_run_id`;
- artifact visibility;
- lifecycle status;
- expiration;
- purge status;
- validation status;
- source-file availability when the request needs source bytes.

Default failure behavior is fail-closed: return a typed error, not partial private content.

## 11. Implementation Slices

| Slice | Work | Exit proof |
|---|---|---|
| 1. Schema and contract | Add Broker Reports ArtifactStore records and lifecycle fields. | Unit tests for create/resolve/expire/purge. |
| 2. Gate 1 persistence | Persist current normalizer package into ArtifactStore. | API smoke shows safe chat report and persisted refs. |
| 3. Compact UX | Replace primary full JSON chat output with Russian compact report. | Snapshot or API assertion for no private/raw fields. |
| 4. Retention worker | Implement expire and purge transitions. | Tests for TTL, source-delete, chat-delete, run-purge. |
| 5. Gate 2 resolver | Add resolver path for safe/private refs. | Gate 2 can read only validated same-context refs. |
| 6. Customer-approved test guard | Add policy gate requiring retention mode before customer data. | Smoke refuses missing retention policy. |

## 12. Validation Plan

Required before customer-approved package:

- source upload resolves through OpenWebUI native file access;
- derived private slices are stored only in Project ArtifactStore;
- chat output contains no private slices, raw paths or secrets;
- source-file deletion is reconciled;
- chat deletion behavior is proven;
- run purge deletes private payloads and leaves only allowed tombstone;
- Knowledge remains unchanged for customer source docs;
- Gate 2 rejects stale, expired, purged, wrong-user and wrong-case refs.
