# STT v2 Artifact Contracts

Status: Gate 1-2 contract.

Date: 2026-07-02.

Scope: MVP-required artifact contracts for STT v2 Gate 1-2 only.

## 1. Purpose

Define the minimum contracts needed to prove:

- runtime diarization enters normalized transcript structures;
- structured transcripts survive beyond flat chat text;
- artifacts are internally addressable by opaque refs;
- artifact scope is context metadata, not authorization or tenancy;
- lineage is recorded without creating a workflow engine.

Future post-processing contracts are deliberately out of this document.

## 2. Contract Tiers

Gate 1-2 required:

- `TranscriptResultV1`;
- `ArtifactScopeV1`;
- `ArtifactRefV1`;
- `ArtifactRecordV1`;
- minimal `ArtifactChainV1`;
- `ArtifactRetentionPolicyV1`;
- `TranscriptProjectionV1` only for speaker-labeled proof;
- `TranscriptStoreAdapter` facade over `ArtifactStoreAdapter`.

Gate 3+ only:

- prompt catalog contracts;
- quick action contracts;
- prompt execution contracts;
- `PostProcessingRequestV1`;
- `PostProcessingResultV1`;
- chunking map/reduce contracts;
- DOCX contracts.

## 3. TranscriptResultV1 Preservation

`TranscriptResultV1` remains the canonical product transcript artifact.

Required Gate 1-2 fields:

```text
job_id: string
text: string
language: string | null
duration_seconds: float | null
segments: TranscriptSegmentV1[]
segments[].text: string
segments[].start_seconds: float | null
segments[].end_seconds: float | null
segments[].speaker: string | null
segments[].words: TranscriptWordV1[]
segments[].words[].text: string
segments[].words[].start_seconds: float | null
segments[].words[].end_seconds: float | null
segments[].words[].speaker: string | null
output_profile: string
provider_id: string
adapter_id: string
warnings: string[]
safe_provider_metadata: object
transcript_hash: string
artifact_scope: ArtifactScopeV1
source_links: object
internal_provider_response_ref: string | null
```

Rules:

- Preserve `text`, `segments`, `words`, timestamps, speakers and warnings.
- Build prompt/projection inputs only from normalized structures.
- Do not use raw provider JSON as product data.
- `internal_provider_response_ref` is optional diagnostic-only metadata.
- Product flow must work when `internal_provider_response_ref` is absent/null.

## 4. ArtifactScopeV1

`ArtifactScopeV1` binds an artifact to available context.

```text
scope_id: string
workspace_id: string | null
user_id: string | null
chat_id: string | null
message_id: string | null
openwebui_file_id: string | null
stage2_job_id: string | null
client_label: string | null
project_label: string | null
external_context_id: string | null
tenant_id: string | null
access_context_hash: string | null
```

Rules:

- Not an ACL.
- Not ownership proof.
- Not a security boundary.
- Not a tenant/multitenant model.
- `tenant_id` is nullable optional/future only.
- Missing workspace/client/project/tenant identifiers are not errors.
- Do not invent identifiers unavailable to Action/loader/sidecar.
- Artifact access must be validated separately through available OpenWebUI
  user/session/chat/file/prompt context.
- Loader-visible refs are not trust boundaries.
- Lineage belongs in artifact records, artifact edges and indexes, not in scope.

### 4.1. OpenWebUI File Identity Continuity

Any consumer that dereferences `transcript_ref` must present an
`ArtifactAccessContextV1.openwebui_file_id` that matches the OpenWebUI file id
stored in the transcript artifact scope.

If browser normalization creates a prepared OpenWebUI upload, that prepared
upload becomes the file identity for the transcript artifact. The Action
envelope that creates `transcript_ref` and every later post-processing access
context must use the same prepared `openwebui_file_id`.

Rules:

- source attachment id and prepared upload id are not interchangeable;
- loader quick actions must bind to the file object used by
  `callTranscriptionAction`;
- Action code must forward the supplied file id without inventing a fallback;
- missing or mismatched `openwebui_file_id` must fail closed through typed
  artifact access refusal.

## 5. ArtifactRefV1

```text
artifact_ref: string
artifact_type:
  "source_file"
  | "prepared_audio"
  | "stt_job"
  | "transcript_result"
  | "projection"
  | "diagnostic_provider_payload"
version: "v1"
artifact_scope: ArtifactScopeV1
created_at: string
expires_at: string | null
```

Gate 1-2 rules:

- `artifact_ref` must be opaque and unguessable.
- `transcript_ref` is an alias for an `artifact_ref` where
  `artifact_type="transcript_result"`.
- `artifact_ref` alone never proves access.

## 6. ArtifactRecordV1

```text
artifact_ref: ArtifactRefV1
parent_refs: string[]
payload_kind: "inline_json" | "file_ref" | "object_ref" | "redacted" | "external_ref"
payload_ref: string | null
payload_inline: object | null
checksum_sha256: string | null
size_bytes: int | null
safe_metadata: object
warnings: string[]
retention_class: string
created_by: string | null
```

Rules:

- normalized transcript can be stored as inline JSON or an internal payload ref;
- source media is a ref/metadata artifact, not a sidecar media copy by default;
- prepared audio is a ref/metadata artifact unless explicitly persisted;
- no API keys, tokens, provider headers or raw provider payloads in product
  records;
- ordinary logs may include safe refs/counts, not payloads.

## 7. Minimal ArtifactChainV1

```text
chain_id: string
root_ref: string
latest_refs: string[] | null
edges:
  - from_ref: string
    to_ref: string
    transform:
      "normalize_audio"
      | "transcribe"
      | "project_transcript"
    created_at: string
```

Rules:

- lineage only;
- no orchestration;
- no job-status replacement;
- no authorization replacement;
- no workflow engine;
- `latest_refs` is optional/derived convenience metadata.

## 8. ArtifactRetentionPolicyV1

```text
policy_id: string
product_transcript_ttl_days: int
transformation_ttl_days: int
prepared_audio_ttl_hours: int
diagnostic_payload_ttl_hours: int
cascade_on_chat_delete: bool
cascade_on_source_file_delete: bool
rotation_interval_hours: int
hard_delete_after_expiry: bool
```

Recommended Gate 1-2 defaults:

- transcript artifacts: 14 days;
- projection artifacts used for proof: 14 days;
- prepared audio refs/metadata: 24 hours unless runtime policy says otherwise;
- diagnostic raw provider payload: disabled;
- rotation: daily cleanup;
- expired refs return typed `artifact_expired`.

## 9. TranscriptProjectionV1

Only needed in Gate 1-2 if used for speaker-labeled proof.

```text
projection_ref: string
transcript_ref: string
projection_kind: "plain" | "timestamped" | "speaker_labeled"
text: string
segment_refs: string[]
speaker_mode: "auto" | "require" | "ignore"
warnings: string[]
artifact_scope: ArtifactScopeV1
created_at: string
```

Rules:

- derived only from normalized `TranscriptResultV1`;
- speaker labels come only from normalized fields;
- no raw provider JSON.

## 10. ArtifactStoreAdapter

Gate 2 uses `ArtifactStoreAdapter` as the technical persistence boundary. It is
internal-only and must not be exposed as a browser-visible storage API.

```text
put_artifact(record) -> ArtifactRefV1
get_artifact(artifact_ref, user_context) -> ArtifactRecordV1
link_artifacts(from_ref, to_ref, transform) -> ArtifactChainV1
list_chain(root_or_ref, user_context) -> ArtifactChainV1
expire_artifact(artifact_ref, reason)
delete_scope(scope, reason)
```

Rules:

- implementation may be `SqliteArtifactStoreAdapter` for runtime MVP;
- process-memory implementation is allowed only for unit tests and explicit
  local proof;
- every read validates `user_context` against stored `ArtifactScopeV1`;
- artifact refs are opaque identifiers, not authorization tokens;
- loader-visible refs are not sufficient for access;
- post-processing access uses the same `openwebui_file_id` that created the
  `transcript_ref`;
- product path must not require diagnostic raw provider payload.

## 11. TranscriptStoreAdapter

Gate 2 uses `TranscriptStoreAdapter` as a typed facade over `ArtifactStoreAdapter`.

```text
put_transcript(result, links) -> transcript_ref
get_transcript(transcript_ref, user_context) -> TranscriptResultV1
link_to_chat(transcript_ref, chat_id, message_id, file_id)
expire(transcript_ref)
```

Rules:

- no competing transcript store source of truth;
- access validation is required on read;
- missing/expired refs return typed failures;
- current in-memory job store is not runtime-sufficient for Gate 2 Done.

## 12. Acceptance Criteria

This contract is satisfied when:

- contract tests validate required fields and nullability;
- `TranscriptResultV1` stores speaker labels when provider returns them;
- `transcript_ref` resolves to the normalized transcript;
- `ArtifactScopeV1` contains only available identifiers;
- post-processing access preserves OpenWebUI file identity continuity across
  browser normalization;
- `ArtifactChainV1` records lineage without execution behavior;
- product path works without diagnostic provider payload;
- no future prompt/DOCX contracts are required for Gate 1-2.
