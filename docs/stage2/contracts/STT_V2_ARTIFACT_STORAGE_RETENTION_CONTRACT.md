# STT v2 Artifact Storage / Retention Contract

Status: Gate 1-2 storage contract.

Date: 2026-07-02.

Scope: internal artifact store, retention and storage-safety rules for STT v2
Gate 2.

## 1. Purpose

Gate 2 needs a durable internal artifact store so the structured transcript is
not lost after the Action returns flat chat text.

The store exists for:

- safe post-transcription retrieval;
- reproducibility of transcript preservation;
- storage-safety proof;
- troubleshooting with scoped metadata.

The store is not:

- a user-facing transcript history;
- a Meetings app;
- a workflow engine;
- a replacement for OpenWebUI chat;
- a replacement for authorization checks.

## 2. Backend Recommendation

Runtime MVP:

- SQLite database on a sidecar-mounted volume;
- optional local payload directory only for internal payloads too large for
  inline JSON;
- no object storage in Gate 1-2 unless separately approved.

The current in-memory job store is not enough because it cannot prove:

- restart survival;
- retention/expiry;
- durable `transcript_ref`;
- access fail-closed behavior;
- no ordinary payload logging.

## 3. Store Boundaries

Allowed:

- normalized `TranscriptResultV1`;
- artifact records;
- artifact edges;
- transcript index;
- safe metadata;
- checksums;
- source/prepared audio refs and metadata;
- proof-only `TranscriptProjectionV1` when needed.

Forbidden in product storage:

- raw LemonFox JSON;
- provider headers;
- provider request body;
- API keys;
- OpenWebUI internal auth tokens;
- signed internal URLs beyond short-lived delivery;
- full rendered prompt body;
- browser-visible hidden state as source of truth.

Diagnostic raw provider payload storage is disabled in Gate 1-2.

## 4. Schema Sketch

```text
artifact_records(
  artifact_ref,
  artifact_type,
  version,
  scope_id,
  workspace_id nullable,
  user_id nullable,
  chat_id nullable,
  message_id nullable,
  openwebui_file_id nullable,
  stage2_job_id nullable,
  client_label nullable,
  project_label nullable,
  external_context_id nullable,
  tenant_id nullable,
  access_context_hash nullable,
  scope_json,
  payload_kind,
  payload_ref,
  payload_inline_json,
  checksum_sha256,
  size_bytes,
  safe_metadata_json,
  warnings_json,
  retention_class,
  created_at,
  expires_at,
  deleted_at
)

artifact_edges(
  chain_id,
  from_ref,
  to_ref,
  transform,
  created_at
)

transcript_index(
  transcript_ref,
  transcript_hash,
  chain_id,
  artifact_ref,
  created_at,
  expires_at
)
```

Future-ready optional index, not required for Gate 2:

```text
processed_result_index(
  result_ref,
  request_ref,
  transcript_ref,
  chain_id,
  artifact_ref,
  created_at,
  expires_at
)
```

Rules:

- Do not put `transcript_ref` or `post_processing_result_ref` into
  `ArtifactScopeV1`.
- Use indexes for lookup.
- Keep `tenant_id` nullable optional/future.
- Keep `scope_json` for future context identifiers without immediate schema
  churn.

## 5. Reference Generation

Artifact refs must be:

- opaque;
- unguessable;
- non-sequential from the browser perspective;
- safe to log only as refs, never with payloads;
- insufficient for access by themselves.

Recommended proof:

- generate many refs in test;
- assert no simple incrementing pattern;
- assert malformed refs fail with typed refusal;
- assert valid ref plus wrong user/context fails.

## 6. Source / Prepared Audio Policy

For Gate 1-2, store media refs and metadata first, not media copies.

Source media:

- owned by OpenWebUI lifecycle;
- stored in artifact records as `openwebui_file_id` plus safe metadata;
- not copied into sidecar storage by default.

Prepared audio:

- record file ref only if already persisted by existing flow or explicitly
  needed for retry/debug;
- record checksum, size, duration when available, media profile and
  normalization profile;
- short TTL;
- no sidecar media copy by default.

Provider direct upload remains constrained by provider documented limits.
LemonFox currently documents direct upload as 100 MB and URL input as 1 GB:
https://www.lemonfox.ai/apis/speech-to-text

## 7. Retention Defaults

Recommended Gate 2 defaults:

```text
product_transcript_ttl_days=14
transformation_ttl_days=14
prepared_audio_ttl_hours=24
diagnostic_payload_ttl_hours=0
rotation_interval_hours=24
hard_delete_after_expiry=true
```

Diagnostic raw provider payload storage remains disabled, so
`diagnostic_payload_ttl_hours=0` means no diagnostic payload is persisted.

## 8. Expiry And Rotation

Expiry behavior:

- expired transcript ref returns typed `artifact_expired`;
- expired payload is not retrievable;
- expired metadata may remain only as redacted tombstone if policy allows;
- expired payload deletion must run before final proof.

Rotation behavior:

- daily cleanup for MVP;
- logs counts and refs only;
- never logs payload text or provider JSON;
- handles already-deleted files idempotently.

## 9. Access Fail-closed

`ArtifactScopeV1` helps resolve context; it is not authorization.

Access read path must validate:

- current user/session context if available;
- chat/message/file context if available;
- artifact ref existence and expiry;
- prompt access only in later gates.

Fail closed when:

- user context is missing and policy requires it;
- ref is malformed;
- ref is expired;
- scope cannot be matched to available context;
- artifact payload is missing unexpectedly.

Typed refusals:

```text
artifact_not_found
artifact_expired
artifact_access_denied
artifact_scope_unverified
artifact_payload_unavailable
```

## 10. Storage Safety Checks

Gate 2 must prove:

- SQLite/volume path is not browser-accessible;
- sidecar does not serve the storage directory as static files;
- artifact payloads do not appear in ordinary logs;
- raw provider payload is absent from product artifact rows;
- loader-visible refs are not sufficient for access;
- product path works without diagnostic raw provider payload;
- product path works without full rendered prompt snapshot.

## 11. Acceptance Criteria

This contract is satisfied when:

- artifact records and transcript index are created for a successful STT job;
- `TranscriptResultV1` is retrievable by `transcript_ref`;
- restart behavior is proven or explicitly limited by accepted proof mode;
- expired refs cannot be retrieved;
- storage path is not browser-accessible;
- ordinary logs contain no transcript payload or raw provider JSON;
- source/prepared audio are refs/metadata-first;
- flat transcript output remains backward compatible.
