# STT v2 Transcript Post-processing Blueprint

Status: refined implementation blueprint candidate.

Date: 2026-07-02.

Scope: native-first / extension-first implementation path for transcript
post-processing, artifact-chain preservation, diarization, managed OpenWebUI
Prompts, auto-run quick actions and later DOCX export.

Non-code note: this document is a design blueprint. It does not implement STT
v2 behavior by itself.

## 1. Purpose

Design the smallest safe STT v2 layer above the existing Stage 2 STT MVP.

The target is to let users:

1. Transcribe audio/video inside OpenWebUI.
2. Preserve the normalized structured transcript.
3. Preserve enough artifact lineage from source file to processed result.
4. Use speaker labels when provider diarization is enabled and proven.
5. Run approved OpenWebUI Prompts as transcript quick actions.
6. Return processed results to the same OpenWebUI chat.
7. Later, export stable processed results to simple DOCX.

The architecture must keep OpenWebUI update-safe:

- no heavy OpenWebUI fork;
- no OpenWebUI core patch unless extension points are demonstrably
  insufficient;
- STT v2 behavior lives as an isolated extension layer;
- all extension integration goes through strict contracts, factories and
  adapters.

## 2. Current Known Context

Current implemented STT path:

```text
OpenWebUI media attachment
-> static loader Transcribe action
-> browser ffmpeg.wasm normalization when needed
-> OpenWebUI Action Function
-> private stage2-stt sidecar
-> Lemonfox provider adapter
-> normalized TranscriptResultV1
-> flat transcript text returned into OpenWebUI chat workflow
```

Current audit findings:

- `TranscriptResultV1` already models `text`, `segments`, `words`, speaker
  labels, timestamps and warnings.
- The sidecar preserves the normalized `TranscriptResultV1` while the job stays
  in its current in-memory store.
- The current OpenWebUI Action collapses the result to flat text before
  returning content to chat, so structured transcript data is lost at the
  OpenWebUI Action/loader boundary.
- The Lemonfox adapter can request and normalize speaker labels, but runtime
  diarization is currently disabled by default.
- Lemonfox documentation currently states direct upload is limited to 100 MB,
  URL input to 1 GB, and `speaker_labels=true` requires `verbose_json`.
- OpenWebUI Prompts are the preferred native editable catalog, but STT v2 prompt
  templates are not yet created on runtime.
- Native-only UX is weak for post-transcript quick actions; a minimal static
  loader helper is justified if it degrades safely.
- DOCX artifact delivery through Action is not proven and is not part of the
  immediate implementation slice.
- Long transcript behavior is not currently defined.

Accepted product decisions:

- `TranscriptResultV1` is the canonical product transcript artifact.
- Quick action click means template selection, user confirmation and permission
  to create a native OpenWebUI user prompt turn for the selected template.
- Target quick-action UX is native chat submission: draft prompt, submit through
  the ordinary composer, receive a normal assistant message. Server-side
  execution remains a compatibility/fallback path.
- DOCX is a future final export gate after structured transcript preservation,
  artifact lineage, prompt routing, prompt execution and `PostProcessingResultV1`
  are stable.
- Raw Lemonfox JSON is not a product artifact and must never enter prompt input,
  chat output, DOCX, browser-visible state or ordinary logs.

## 3. Architectural Constraints

1. Do not patch OpenWebUI core if Action, native Prompts, file API, static loader
   helper and sidecar are sufficient.
2. Keep OpenWebUI as the upstream application.
3. Keep STT v2 as an isolated extension layer.
4. Use strict contracts at every boundary.
5. Use factories and adapters for provider, artifact storage, prompt catalog,
   post-processing execution, UI action presentation and future DOCX export.
6. Preserve `TranscriptResultV1`; never rebuild prompt input from raw provider
   payloads.
7. Do not expose raw Lemonfox JSON in prompt input, DOCX, chat output, browser
   state, ordinary storage or ordinary logs.
8. Treat OpenWebUI Prompts as template source of truth.
9. Treat quick actions as shortcuts to prompts, not as duplicated templates.
10. Export DOCX only from processed results, and only in the final export gate.
11. Make long transcript behavior explicit: single-pass, approved chunking or
    typed refusal.
12. STT v2 failures must not break normal chat or base OpenWebUI behavior.
13. Loader helper must be minimal, optional and safe to fail.
14. Diagnostic raw provider storage is not MVP scope. If added later, it must be
    disabled by default, operator/admin-only, short-retention and isolated from
    prompt/chat/DOCX/browser/logs.

## 4. Target Architecture

### 4.1. Ownership Map

OpenWebUI owns:

- chat UX;
- uploaded source file lifecycle and file metadata;
- native Prompts catalog;
- prompt visibility and group/resource sharing;
- normal model execution UX;
- upstream application updates.

`stage2-stt` sidecar owns:

- STT provider adapters;
- normalized transcript contracts;
- artifact-chain records and refs;
- transcript projections;
- prompt catalog adapter;
- post-processing request/result contracts;
- long transcript policy;
- future DOCX generation endpoint.

Static loader helper owns only:

- detecting successful STT transcript insertion where possible;
- showing compact quick-action controls;
- requesting UI-safe action catalog from sidecar;
- forwarding selected action identifiers and artifact refs;
- safe no-op behavior when DOM/API assumptions fail.

OpenWebUI Action owns:

- authenticated bridge between OpenWebUI runtime and sidecar;
- file handoff to sidecar;
- chat-safe transcript response;
- returning or exposing `transcript_ref` / `artifact_ref` where OpenWebUI result
  shape allows.

### 4.2. Runtime Shape

```text
Browser/OpenWebUI
  -> static loader helper
  -> OpenWebUI Action Function
  -> stage2-stt sidecar
       -> ProviderAdapterFactory -> LemonfoxProviderAdapter
       -> ArtifactStoreAdapter -> SQLite/volume MVP store
       -> TranscriptStoreAdapter -> TranscriptResultV1 facade
       -> TranscriptProjectionFactory
       -> PromptCatalogAdapter -> OpenWebUI Prompts API
       -> PostProcessingExecutorAdapter
       -> UiActionAdapter
       -> future DocxExportAdapter
  -> OpenWebUI chat/file surfaces
```

The sidecar is the extension boundary. OpenWebUI remains replaceable by upstream
OpenWebUI plus our extension artifacts.

### 4.3. Target Artifact Lineage

The design target is enough artifact lineage for safe post-processing, review
and troubleshooting, not a separate transcript product:

```text
source OpenWebUI file
-> prepared audio after ffmpeg normalization
-> STT job
-> normalized TranscriptResultV1
-> speaker-labeled / timestamped / plain projection
-> prompt input
-> selected OpenWebUI Prompt/template version
-> PostProcessingResultV1
-> later DOCX export
```

Why this matters:

- source media and prepared audio explain ingestion and normalization choices;
- STT job records provider/profile/capability decisions;
- `TranscriptResultV1` preserves text, segments, words, timestamps, speaker
  labels and warnings;
- projections make prompt input reproducible without exposing provider payloads;
- selected prompt metadata/version makes later result review possible after a
  prompt changes;
- `PostProcessingResultV1` is the only source for future DOCX export.

If the chain is flattened to chat text, these semantics are lost:

- speaker attribution;
- word/segment timestamps;
- provider warnings;
- prompt input shape;
- prompt version/hash;
- long transcript refusal/chunking decisions;
- safe auditability for post-processing output.

ArtifactStore is an internal technical store. It is not a separate Meetings app,
not a separate transcript history UI, and must not create a new user-facing
archive outside OpenWebUI chat. User-facing durable context remains OpenWebUI
chat.

### 4.4. Recommended MVP Delivery Order

1. Accept refined blueprint.
2. Prove runtime diarization.
3. Preserve enough artifact lineage and structured transcript.
4. Seed and route two OpenWebUI post-processing prompts.
5. Add two quick actions with auto-run target UX.
6. Prove prompt access/version behavior.
7. Add refusal-only long transcript policy.
8. Add selected chunking support for approved templates.
9. Add DOCX export as the final gate.

Do not start DOCX before `PostProcessingResultV1` and artifact-chain storage are
stable.

Do not implement chunking before single-pass prompt behavior is accepted.

## 5. Scenario Workflows

### 5.1. Ordinary Audio

```text
User attaches prepared audio
-> Transcribe
-> Action sends bytes and envelope to sidecar
-> sidecar validates profile, size and available artifact/context scope
-> sidecar creates source/prepared_audio/STT job artifact records
-> ProviderAdapter transcribes
-> sidecar stores normalized TranscriptResultV1 artifact
-> Action returns transcript text plus transcript_ref when possible
-> loader shows quick actions if catalog is available
```

Failure behavior:

- typed error returned to Action;
- ordinary chat remains available;
- no quick actions are shown without `transcript_ref`.

Scope behavior:

- missing `tenant_id` is not an error;
- partial scope is acceptable when only file/user/job identifiers are available;
- do not invent workspace/client/project identifiers when OpenWebUI does not
  expose them;
- if ownership or access for a requested artifact cannot be proven,
  post-processing must fail closed.

### 5.2. Video Or Unsupported Format Through ffmpeg

```text
User attaches video or unsupported media
-> browser loader validates media-type/size policy
-> ffmpeg.wasm extracts and normalizes audio
-> prepared audio gets checksum/profile metadata
-> Action sends prepared audio
-> sidecar records source file ref plus prepared audio artifact
-> normal STT flow continues
```

Artifact lineage must preserve refs/metadata for both:

- source OpenWebUI file identity;
- prepared audio profile/checksum/size/duration when available;
- normalization profile used for provider submission.

Access identity rule:

- if normalization creates a prepared OpenWebUI upload, the prepared upload id
  is the `openwebui_file_id` that creates `transcript_ref`;
- post-processing quick actions must use that same prepared file id;
- the original source attachment id must remain lineage metadata only and must
  not be substituted into `ArtifactAccessContextV1.openwebui_file_id`.

The prepared audio artifact is not a product transcript. Its retention can be
shorter than the transcript/result retention. Source media lifecycle remains
owned by OpenWebUI unless a separate storage policy is accepted. The sidecar
should not copy source media or prepared audio by default.

### 5.3. Transcript With Diarization

```text
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
-> ProviderAdapter sends speaker_labels=true and verbose_json
-> provider returns speaker labels
-> adapter normalizes labels into TranscriptResultV1.segments[].speaker and
   TranscriptResultV1.segments[].words[].speaker
-> sidecar stores normalized transcript artifact
-> projection builder creates speaker-labeled prompt input
-> speaker-aware quick actions are enabled
```

Prompt input may contain generic labels such as `Speaker 1` / `Speaker 2`.

It must not:

- use raw provider JSON;
- invent real participant names;
- claim semantic roles unless marked `inferred`.

### 5.4. Transcript Without Diarization

```text
supports_speaker_labels=false or result has no speakers
-> transcript is still valid
-> prompt projection uses plain or timestamped text
-> result includes warning speaker_labels_absent when template expects speakers
```

Post-actions remain available unless a specific template has
`requires_speakers=true`.

### 5.5. Artifact Persistence

```text
sidecar receives file/job/result event
-> ArtifactStoreAdapter writes ArtifactRecordV1
-> ArtifactChainV1 links parent/child records
-> TranscriptStoreAdapter indexes TranscriptResultV1 by transcript_ref
-> retention policy assigns expiry and deletion behavior
```

MVP must store at least:

- source file reference;
- prepared audio reference/checksum/profile;
- STT job record;
- normalized `TranscriptResultV1`;
- `TranscriptProjectionV1` for executed post-processing or prompt draft proof;
- `PromptInputVariablesV1`;
- `PromptExecutionSnapshotV1`;
- selected prompt metadata/version/hash;
- `PostProcessingRequestV1`;
- `PostProcessingPromptDraftV1`;
- `PostProcessingResultV1`.

### 5.6. Quick Action Auto-run

```text
loader requests UI-safe quick-action catalog
-> user clicks "Краткий пересказ" or "Протокол встречи"
-> click confirms selected template and native chat submission intent
-> loader/action sends transcript_ref + template_id + user/chat context + the
   same OpenWebUI file id that created transcript_ref
-> sidecar resolves OpenWebUI Prompt metadata and access
-> sidecar builds prompt input from normalized TranscriptResultV1
-> sidecar returns PostProcessingPromptDraftV1 with rendered prompt_text
-> loader places prompt_text into the ordinary OpenWebUI composer
-> loader submits through native OpenWebUI send control when available
-> normal assistant response appears as the next chat message
```

Quick action must never carry prompt body. It carries only a stable prompt/action
reference and UI-safe metadata before the user clicks. After click, the rendered
prompt draft becomes the visible user prompt sent through OpenWebUI chat.

If native send cannot be found safely, the loader may leave the prompt draft in
the composer with an explicit status instead of silently falling back to
server-side execution.

### 5.7. Missing Prompt

```text
quick action references template_id
-> PromptCatalogAdapter cannot resolve prompt by id/command/tags
-> sidecar returns typed prompt_not_found
-> loader hides or disables that action
-> normal chat remains usable
```

User-facing message:

```text
Шаблон постобработки недоступен. Обратитесь к администратору или выберите другой шаблон.
```

### 5.8. Prompt Changed After Previous Result

```text
Prompt body or metadata changes in OpenWebUI
-> new executions capture new prompt_version and prompt_body_hash
-> previous PostProcessingResultV1 keeps captured version/hash
-> old result is not silently reinterpreted as if produced by the new prompt
```

If OpenWebUI does not expose a stable revision id, the sidecar should compute a
body hash at execution time and store safe prompt metadata plus hash in the
result artifact. The production prompt body itself should not be duplicated in
ordinary sidecar config or loader state.

### 5.9. Browser Reload

```text
browser reloads chat
-> loader attempts to recover transcript_ref/action anchors from visible message
   metadata, sidecar refs or minimal hidden state
-> sidecar validates ref and user scope
-> quick actions reappear only if ref is valid
```

Fallback:

- if `transcript_ref` cannot be recovered, normal chat remains unchanged;
- no quick actions are shown;
- user can rerun transcription if post-processing is needed.

### 5.10. Sidecar Restart

```text
sidecar restarts
-> persistent SQLite/volume store is reopened
-> artifact refs and transcript refs remain valid until expiry/deletion
```

If a transient proof store is used before runtime MVP:

```text
transcript_ref lookup
-> transcript_ref_not_found
-> loader disables post-actions for that transcript
```

Runtime MVP should not rely on the current in-memory job store.

### 5.11. Long Transcript

```text
sidecar computes normalized transcript size and estimated prompt tokens
-> if within single-pass threshold: execute once
-> else if chunking is enabled and template.chunkable=true: use approved
   speaker/timestamp-aware chunking
-> else: typed refusal, no silent truncation
```

Refusal must be explicit and chat-safe:

```text
Транскрипт слишком длинный для выбранного шаблона без разбиения. Выберите шаблон с поддержкой разбиения или сократите материал.
```

Gate 6 should implement refusal-only behavior first. Gate 7 may add selected
chunking for approved templates.

### 5.12. Provider Error

```text
ProviderAdapter returns timeout/rate_limit/provider_error/size_error
-> sidecar stores safe job failure artifact
-> Action returns user-safe error
-> ordinary chat remains usable
```

No raw provider response in chat, prompt input, DOCX, browser or ordinary logs.

### 5.13. OpenWebUI Upgrade Scenario

```text
Upgrade upstream OpenWebUI
-> reinstall/verify Action Function and static loader helper
-> smoke transcribe path
-> smoke PromptCatalogAdapter
-> smoke quick-action no-op behavior
-> smoke base chat with loader disabled
```

If loader assumptions break, disable quick actions and keep normal chat plus
native Prompts. Core OpenWebUI patches remain out of scope unless a separate
ADR proves necessity.

### 5.14. Future DOCX Export

```text
User selects DOCX export on a processed result
-> sidecar loads PostProcessingResultV1 by artifact_ref
-> DocxExportAdapter generates simple DOCX
-> sidecar returns short-lived download URL or uploads through proven OpenWebUI
   file API
```

DOCX source is processed result only. Raw transcript export is not MVP scope.

## 6. Contract Model

### 6.0. Contract Tiers

MVP required for Gate 1-2:

- `TranscriptResultV1`;
- `ArtifactScopeV1`;
- `ArtifactRefV1`;
- `ArtifactRecordV1`;
- minimal `ArtifactChainV1`;
- `ArtifactRetentionPolicyV1`;
- `TranscriptProjectionV1` only when needed for speaker-labeled proof;
- `TranscriptStoreAdapter` as a typed facade over `ArtifactStoreAdapter`.

Needed from Gate 3-5:

- `PostProcessingTemplateV1`;
- `PromptInputVariablesV1`;
- `PromptExecutionSnapshotV1`;
- `PostProcessingRequestV1`;
- `PostProcessingResultV1`.

Future:

- `DocxExportRequestV1`;
- `DocxExportResultV1`;
- `DocxExportAdapter`;
- full chunking map/reduce artifact contracts.

Rule: Gate 1-2 implementation should not build the whole post-processing/export
surface before the structured transcript and artifact-store proof is stable.

### 6.1. TranscriptResultV1 Preservation

Existing `TranscriptResultV1` remains the canonical product transcript contract.

Required fields for STT v2:

```text
job_id
text
language
duration_seconds
segments[]
segments[].text
segments[].start_seconds
segments[].end_seconds
segments[].speaker
segments[].words[]
segments[].words[].text
segments[].words[].start_seconds
segments[].words[].end_seconds
segments[].words[].speaker
output_profile
provider_id
adapter_id
warnings[]
safe_provider_metadata
transcript_hash
artifact_scope
source_links
internal_provider_response_ref | null
```

Rules:

- `safe_provider_metadata` may include provider/profile/capability identifiers,
  not raw provider payloads.
- `transcript_hash` is computed from normalized transcript content and safe
  metadata required for reproducibility.
- `TranscriptResultV1` must not depend on tenant semantics. It needs enough
  context links for safe retrieval, post-processing and audit.
- `internal_provider_response_ref` is optional diagnostic-only metadata. It may
  be absent/null when diagnostic mode is disabled.
- product flow must work without `internal_provider_response_ref`.
- `internal_provider_response_ref` must not be dereferenced for prompt input,
  chat output, DOCX export or browser-visible state.

Raw transcript chat display:

- derive only from normalized `TranscriptResultV1`;
- if segment speaker labels exist, render a speaker-labeled raw transcript in
  chat;
- use stable generic labels such as `Спикер 1`, not inferred real names;
- merge adjacent same-speaker segments where it improves readability;
- fall back to current flat `text` when speaker labels are absent.

### 6.2. ArtifactScopeV1

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

- `ArtifactScopeV1` is context binding, not an authorization system.
- `ArtifactScopeV1` is not an ACL, not an ownership proof and not a security
  boundary. It is context metadata used to help resolve, audit and validate
  artifact access.
- `tenant_id` is nullable optional/future metadata only. Do not assert tenant or
  organization boundaries unless the runtime exposes them and a separate design
  accepts them.
- `workspace_id`, `client_label`, `project_label` and `external_context_id` are
  nullable and require runtime/product proof.
- Do not invent identifiers that are unavailable in the Action/loader/sidecar
  path.
- Every product or transformation artifact should carry the available scope.
- Authorization must defer to OpenWebUI identity/session/group/resource access
  where available.
- Artifact lineage belongs in `ArtifactRecordV1`, `ArtifactChainV1` and indexes,
  not in `ArtifactScopeV1`.
- Loader-visible refs are not trust boundaries.
- If browser normalization creates a prepared OpenWebUI upload, that prepared
  upload id is the file identity for the transcript artifact and all later
  post-processing access checks.
- `access_context_hash` is helper metadata, not a substitute for access checks.
- When artifact access cannot be proven, refuse post-processing rather than
  leaking an artifact.

### 6.3. ArtifactRefV1

```text
artifact_ref: string
artifact_type:
   "source_file"
   | "prepared_audio"
   | "stt_job"
   | "transcript_result"
   | "projection"
   | "prompt_variables"
   | "prompt_execution_snapshot"
   | "prompt_selection"
   | "post_processing_request"
   | "post_processing_result"
   | "docx_export"
   | "diagnostic_provider_payload"
version: "v1"
artifact_scope: ArtifactScopeV1
created_at: string
expires_at: string | null
```

`transcript_ref` is a stable alias for an `ArtifactRefV1` where
`artifact_type="transcript_result"`.

### 6.4. ArtifactRecordV1

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

Product artifact classes:

- normalized transcript: stored as `TranscriptResultV1`;
- transformation artifacts: stored as contracts or reconstructible records;
- diagnostic raw provider payload: disabled by default and never used as product
  input.

### 6.5. ArtifactChainV1

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
      | "build_prompt_variables"
      | "select_prompt"
      | "execute_prompt"
      | "export_docx"
    created_at: string
```

Rules:

- `ArtifactChainV1` records lineage only;
- it does not orchestrate execution;
- it does not replace job status;
- it does not replace access checks;
- it does not become a business workflow engine;
- `latest_refs` is optional/derived convenience metadata, not source of truth;
- chain edges are append-only until expiry/deletion;
- replacing a prompt or rerunning post-processing creates a new child artifact;
- old processed results keep their original prompt version/hash.

### 6.6. ArtifactRetentionPolicyV1

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

Recommended MVP defaults:

- product normalized transcript: 14 days;
- post-processing request/result and projections: 14 days;
- prepared audio: 24 hours unless an approved policy requires longer;
- diagnostic raw provider payload: disabled; if enabled later, 24 hours max by
  default;
- rotation: daily cleanup job;
- expired artifacts return typed `artifact_expired`.

### 6.7. TranscriptProjectionV1

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

- projection is derived only from normalized `TranscriptResultV1`;
- speaker-labeled projection must use normalized speaker fields only;
- chat display projection is presentation-only and must not rewrite transcript
  meaning;
- projection may be stored as a transformation artifact for executed results.

### 6.8. PromptInputVariablesV1

```text
prompt_variables_ref: string
transcript_ref: string
projection_ref: string
template_id: string
language: string | null
speaker_mode: "auto" | "require" | "ignore"
long_policy: "single_pass" | "chunk_if_needed" | "fail_if_too_long"
user_context: string | null
variables: object
artifact_scope: ArtifactScopeV1
created_at: string
```

Rules:

- this contract stores data passed into the prompt, not the full rendered prompt
  body;
- variables must not contain provider payloads, secrets or hidden config.

### 6.9. PromptExecutionSnapshotV1

```text
snapshot_ref: string
openwebui_prompt_id: string
command: string
template_id: string
prompt_version: string | null
prompt_body_hash: string | null
model_id: string | null
executed_at: string
warnings: string[]
artifact_scope: ArtifactScopeV1
```

Rules:

- OpenWebUI Prompt body remains the source of truth.
- Do not store the full rendered prompt body by default.
- If rendered prompt snapshots are required for debugging, store them only as a
  restricted transformation/diagnostic artifact with explicit enablement,
  retention no longer than transformation TTL, and no browser exposure unless it
  is intentionally user-visible.

### 6.10. PostProcessingTemplateV1

```text
template_id: string
openwebui_prompt_id: string
command: string
prompt_version: string | null
prompt_body_hash: string | null
title: string
description: string
tags: string[]
meta: object
access_grants: string[]
input_projection: "plain" | "timestamped" | "speaker_labeled"
requires_speakers: bool
chunkable: bool
default_long_policy: "single_pass" | "chunk_if_needed" | "fail_if_too_long"
enabled: bool
owner: string | null
updated_at: string | null
```

Ownership:

- OpenWebUI Prompt body is source of truth.
- Sidecar owns only catalog projection, routing and action metadata.
- Loader and Action must not embed production prompt bodies.

### 6.11. PostProcessingRequestV1

```text
request_id: string
transcript_ref: string
template_id: string
prompt_ref: string
prompt_version: string | null
prompt_body_hash: string | null
projection_ref: string | null
prompt_variables_ref: string | null
prompt_execution_snapshot_ref: string | null
artifact_scope: ArtifactScopeV1
speaker_mode: "auto" | "require" | "ignore"
long_policy: "single_pass" | "chunk_if_needed" | "fail_if_too_long"
user_context: string | null
```

Validation:

- `transcript_ref` must resolve to normalized `TranscriptResultV1`;
- `template_id` must resolve through `PromptCatalogAdapter`;
- prompt access must be proven for the requesting user/context;
- prompt input must be built only from normalized transcript/projection data.

### 6.12. PostProcessingPromptDraftV1

```text
transcript_ref: string
template_id: string
command: string
label: string
openwebui_prompt_id: string
prompt_version: string | null
prompt_body_hash: string
transcript_hash: string | null
prompt_text: string
warnings: string[]
artifact_scope: ArtifactScopeV1 | null
```

Rules:

- draft is render-only and does not create `PostProcessingResultV1`;
- draft uses the same prompt access, artifact access, long transcript and
  speaker-required checks as server-side execution;
- `prompt_text` is the visible native user prompt submitted through OpenWebUI;
- `prompt_text` must be built from normalized transcript projection only;
- loader must not hardcode prompt bodies.

### 6.13. PostProcessingResultV1

```text
result_id: string
request_id: string
artifact_ref: string
transcript_ref: string
template_id: string
openwebui_prompt_id: string
prompt_version: string | null
prompt_body_hash: string | null
projection_ref: string
prompt_variables_ref: string
prompt_execution_snapshot_ref: string
transcript_hash: string
text: string
sections: object
warnings: string[]
uncertainty_notes: string[]
model_id: string | null
artifact_scope: ArtifactScopeV1
created_at: string
```

Rules:

- `text` is user-visible processed output.
- `sections` is optional structured representation for future DOCX.
- `warnings` includes draft/uncertainty, missing speaker and long transcript
  notices.
- No provider payloads, logs, tokens, internal URLs or hidden config.

### 6.13. Future DocxExportRequestV1

```text
export_id: string
processed_result_ref: string
layout: "simple_business_doc"
safe_metadata: object
include_warnings: bool
requested_by: string | null
artifact_scope: ArtifactScopeV1
```

Allowed safe metadata:

- template label;
- export timestamp;
- safe chat title only if policy allows;
- synthetic/user-visible meeting title;
- non-secret result warnings.

### 6.14. Future DocxExportResultV1

```text
export_id: string
processed_result_ref: string
artifact_ref: string
file_id: string | null
download_url: string | null
filename: string
content_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
size_bytes: int
checksum_sha256: string
warnings: string[]
artifact_scope: ArtifactScopeV1
created_at: string
```

Rule:

- exactly one of `file_id` or `download_url` should be present in the response;
- `download_url` must be short-lived if used.

## 7. Adapter And Factory Model

### 7.1. ProviderAdapter

Existing role:

- calls provider;
- normalizes into `TranscriptResultV1`;
- exposes capability profile.

Future rule:

```text
ProviderAdapterFactory.from_config(profile) -> ProviderAdapter
ProviderAdapter.transcribe(input, options) -> TranscriptResultV1
ProviderAdapter.capabilities() -> ProviderCapabilitiesV1
```

Lemonfox adapter must expose:

- `supports_word_timestamps`;
- `supports_segment_timestamps`;
- `supports_speaker_labels`;
- `max_direct_upload_bytes`;
- `max_url_input_bytes`;
- `requires_verbose_json_for_speakers`.

### 7.2. ArtifactStoreAdapter

Interface:

```text
put_artifact(record) -> ArtifactRefV1
get_artifact(artifact_ref, user_context) -> ArtifactRecordV1
link_artifacts(from_ref, to_ref, transform) -> ArtifactChainV1
list_chain(root_or_ref, user_context) -> ArtifactChainV1
expire_artifact(artifact_ref, reason)
delete_scope(scope, reason)
```

MVP implementation:

- `SqliteArtifactStoreAdapter` backed by a mounted sidecar volume.

Test implementation:

- `InMemoryArtifactStoreAdapter`, but only for unit tests and early local proof.

### 7.3. TranscriptStoreAdapter

Transcript store should be a typed facade over `ArtifactStoreAdapter`, not a
separate competing source of truth.

Interface:

```text
put_transcript(result, links) -> transcript_ref
get_transcript(transcript_ref, user_context) -> TranscriptResultV1
link_to_chat(transcript_ref, chat_id, message_id, file_id)
expire(transcript_ref)
```

Runtime MVP must not rely on the current in-memory job store.

### 7.4. PromptCatalogAdapter

Interface:

```text
list_templates(user_context) -> list[PostProcessingTemplateV1]
get_template(template_id, user_context) -> PostProcessingTemplateV1
resolve_command(command, user_context) -> PostProcessingTemplateV1
resolve_prompt(prompt_id, user_context) -> PostProcessingTemplateV1
```

Primary implementation:

- `OpenWebUIPromptCatalogAdapter`.

Responsibilities:

- read OpenWebUI Prompts by id, command, tags and metadata;
- expose only UI-safe metadata;
- preserve OpenWebUI Prompt as editable source of truth;
- not copy prompt bodies into loader config or sidecar config;
- prove prompt visibility for user/group/resource context where possible;
- refuse when access cannot be proven.

### 7.5. PostProcessingExecutorAdapter

Interface:

```text
execute(request, template, prompt_variables) -> PostProcessingResultV1
draft_prompt(request, template, prompt_variables) -> PostProcessingPromptDraftV1
```

Implementation options:

1. Render-only prompt draft plus native OpenWebUI composer submission.
2. Sidecar-to-OpenWebUI internal API path if auth, model selection and output
   capture are approved.
3. Server-side execution fallback through OpenAI-compatible executor.

Recommendation:

- product target is native chat submission;
- server-side execution may unblock proof/fallback, but must not be presented as
  the primary quick-action UX.

Auto-run proof plan:

1. Render selected Prompt into `PostProcessingPromptDraftV1`.
2. Submit `prompt_text` through the ordinary OpenWebUI composer when the native
   send control is available.
3. If native send is unavailable, leave a visible draft and keep normal chat
   usable.
4. Keep server-side `PostProcessingResultV1` execution as compatibility/fallback
   only.
5. Prove execution failure behavior: typed error, no partial hidden result, base
   chat unaffected.

### 7.6. UiActionAdapter

Interface:

```text
list_quick_actions(transcript_ref, user_context) -> UIAction[]
submit_quick_action(action_id, transcript_ref, options) -> native chat prompt turn
```

Implementation:

- static loader helper;
- no prompt bodies;
- no provider details;
- safe hidden state only for refs and action ids;
- no-op when loader cannot attach to the page safely.

### 7.7. Future DocxExportAdapter

Interface:

```text
export_docx(request, processed_result) -> DocxExportResultV1
```

MVP export implementation, when reached:

- sidecar `python-docx` generation after dependency proof;
- sidecar download endpoint;
- optional OpenWebUI file API upload only after runtime proof.

## 8. Storage, Retention And Artifact Scope Strategy

### 8.1. Backend Recommendation

Recommended runtime MVP backend:

- sidecar SQLite database on a mounted volume for artifact records, chain edges,
  transcript indexes, prompt run records and retention metadata;
- optional local volume files for payloads too large for inline JSON;
- object storage only later, after access, expiry and URL-safety policy is
  approved.

ArtifactStore is an internal technical store for post-processing,
reproducibility, safety and troubleshooting. It is not a user-facing transcript
history product and must not create a parallel archive outside OpenWebUI chat.

Why not current in-memory job store:

- browser reload cannot recover structured refs reliably;
- sidecar restart loses post-processing prerequisites;
- prompt execution cannot audit prompt version/input/result;
- retention and deletion policy cannot be enforced;
- context-scope bindings are not durable.

### 8.2. Schema Sketch

Minimum tables/records:

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

processed_result_index(
  result_ref,
  request_ref,
  transcript_ref,
  chain_id,
  artifact_ref,
  created_at,
  expires_at
)

prompt_run_index(
  result_ref,
  request_ref,
  transcript_ref,
  template_id,
  openwebui_prompt_id,
  prompt_version,
  prompt_body_hash,
  created_at
)
```

Schema options:

1. Explicit nullable columns for common identifiers.
2. `scope_json` plus indexed common fields.

Recommendation for MVP:

- use explicit nullable columns for lookup, deletion, retention and debugging;
- also keep `scope_json` so the scope model can evolve without immediate schema
  churn;
- keep `tenant_id` nullable and optional/future only;
- use indexes for transcript/result lookup instead of putting result refs inside
  `ArtifactScopeV1`;
- record which identifiers were actually available in Gate 2 proof.

### 8.3. Artifact Types

Product normalized artifact:

- `TranscriptResultV1`;
- text, segments, words, timestamps, speaker labels and warnings;
- safe provider/profile metadata;
- transcript hash;
- available artifact-scope links: user/chat/message/file/job, plus
  workspace/project/client/tenant only if runtime exposes them.

Transformation artifacts:

- speaker-labeled, timestamped or plain projection;
- prompt input variables;
- prompt execution snapshot metadata;
- selected prompt metadata/version/hash;
- post-processing request;
- post-processing result;
- warnings and uncertainty notes.

MVP should store projection, prompt variables and execution snapshot metadata for
executed results. Non-executed projections can be recomputed.

Full rendered prompt body is not stored by default because OpenWebUI Prompts are
the source of truth. If a rendered prompt snapshot is needed for debugging, it
must be a restricted transformation/diagnostic artifact with explicit enablement
and retention no longer than transformation TTL.

Diagnostic raw provider artifact:

- not required for MVP;
- disabled by default;
- operator/admin toggle only;
- restricted access;
- short retention;
- never used for prompt input, chat output, DOCX, browser state or ordinary
  logs;
- no-secrets/no-provider-leak checks required before enabling.

### 8.4. Source And Prepared Audio Policy

For MVP, artifact lineage stores media refs and metadata first, not media
copies:

- source OpenWebUI file ref;
- prepared audio file ref only if it is actually persisted;
- checksum;
- media profile;
- size;
- duration when available;
- normalization profile.

Source media lifecycle remains owned by OpenWebUI. Do not copy source media into
sidecar storage by default.

Prepared audio:

- short TTL;
- persisted only if already uploaded/stored by the OpenWebUI flow or explicitly
  needed for retry/debug policy;
- no sidecar media copy by default.

### 8.5. Access Model

`ArtifactScopeV1` is context binding, not an authorization system.

Access rules:

- defer authorization to OpenWebUI identity/session/group/resource access where
  available;
- sidecar must validate requested artifact access using available user/session,
  file, chat and prompt context;
- loader-visible refs are opaque identifiers, not trust boundaries;
- `access_context_hash` is helper metadata, not proof of access;
- if access cannot be proven, refuse.

### 8.6. Reload, Restart, Deletion, Expiry And Rotation

Browser reload:

- recover `transcript_ref` when possible;
- validate artifact scope and access through sidecar;
- show quick actions only for valid refs.

Sidecar restart:

- reopen SQLite/volume store;
- refs survive until expiry/deletion;
- if store is unavailable, quick actions fail closed and normal chat continues.

OpenWebUI chat deletion:

- preferred: best-effort `delete_scope(chat_id)` if deletion event/API is
  available;
- fallback: daily reconciliation/expiry;
- artifacts become inaccessible immediately if scope can no longer be proven.

Source file deletion:

- source file artifact is marked missing/deleted;
- prepared audio cannot be regenerated from the source;
- transcript/result artifacts remain only until retention if policy allows;
- `cascade_on_source_file_delete=true` may be required by customer policy.

Expiry:

- expired refs return typed `artifact_expired`;
- expired artifact payloads are hard-deleted by rotation when
  `hard_delete_after_expiry=true`;
- chain edges can keep redacted tombstones for audit counts if policy allows.

Rotation:

- daily cleanup job for MVP;
- deletes expired payloads first, then unreferenced records/tombstones according
  to policy;
- logs only counts and safe refs, not payloads.

### 8.7. Forbidden Data

Do not store in product artifacts:

- raw Lemonfox JSON;
- provider headers;
- provider request bodies;
- API keys;
- OpenWebUI internal auth tokens;
- signed internal URLs beyond short-lived delivery;
- hidden loader state as source of truth;
- full production prompt bodies duplicated outside OpenWebUI Prompts.

Store only under explicit policy:

- diagnostic raw provider payloads;
- source media copies;
- prepared audio beyond short TTL;
- chat titles or user-entered meeting titles if sensitivity policy restricts
  them.

## 9. Prompt Catalog Strategy

### 9.1. OpenWebUI Prompts As Source Of Truth

Create managed OpenWebUI Prompts for initial STT v2 templates:

1. `Краткий пересказ`
2. `Протокол встречи`

Prompt body ownership:

- prompt body lives in OpenWebUI Prompts;
- sidecar stores only ids, commands, tags, metadata, access projection and
  execution-time version/hash;
- loader stores only UI-safe labels/action ids;
- Action stores no production prompt bodies.

### 9.2. Prompt Input And Prompt Body Storage

Separate three concerns:

1. `TranscriptProjectionV1`: safe derived transcript text in `plain`,
   `timestamped` or `speaker_labeled` form.
2. `PromptInputVariablesV1`: variables passed into the selected prompt,
   including projection ref, language, speaker mode, long transcript policy and
   optional user context.
3. `PromptExecutionSnapshotV1`: execution metadata such as prompt id, command,
   prompt version/hash, model id, execution time and warnings.

Raw chat output can use the same normalized projection principle, but it remains
presentation-only. It must help a user inspect the raw transcript before applying
prompt templates, not become a post-processed result.

Do not store the full rendered prompt body by default. That would duplicate the
production prompt body outside OpenWebUI and weaken the source-of-truth rule.

Prompt reproducibility in MVP means:

- know which prompt was used;
- know which prompt version/hash was used;
- know which transcript projection and variables were supplied;
- do not duplicate the full production prompt body outside OpenWebUI by default.

If a rendered prompt snapshot is later required for debugging/reproducibility,
it must be explicitly enabled as a restricted transformation/diagnostic artifact
with short retention, no secrets/internal config and no browser exposure unless
it is intentionally user-visible.

### 9.3. Required Tags And Metadata

Required tags:

```text
stage2
stage2-stt-v2
transcript
post-processing
```

Recommended metadata:

```text
template_kind=post_processing
template_id=stage2.stt.summary.v1 | stage2.stt.meeting_protocol.v1
command=stt-summary | stt-meeting-protocol
input_projection=plain | timestamped | speaker_labeled
chunkable=true | false
requires_speakers=true | false
default_long_policy=single_pass | chunk_if_needed | fail_if_too_long
owner=<admin/group>
version=<explicit prompt version if OpenWebUI supports it>
```

If OpenWebUI does not expose metadata fields cleanly, use tags plus command/id
mapping and record the limitation in Gate 3/5 evidence.

### 9.4. Lookup And Routing

Resolution order:

1. exact `openwebui_prompt_id`;
2. exact `template_id` metadata;
3. exact command;
4. required tag set plus known action mapping.

Quick actions should be generated from resolved prompt metadata. They should not
exist as separate hardcoded prompt copies.

### 9.5. Access, Caching And Versioning

Access:

- use OpenWebUI user/session/API context where available;
- check group/resource visibility before listing/executing;
- refuse if prompt access cannot be proven;
- never let a loader-visible action bypass sidecar access checks.

Caching:

- cache prompt metadata briefly, for example 60-300 seconds;
- do not cache production prompt body in loader or long-lived sidecar config;
- body may be read at execution time only through the approved execution path;
- capture `prompt_version` or `prompt_body_hash` on each result.

Changed prompt:

- new runs capture new version/hash;
- old results remain tied to old version/hash;
- no silent retroactive reinterpretation.

Deleted prompt:

- hide/disable action;
- return typed `prompt_not_found` for existing action ids;
- previously stored processed results remain readable until retention.

Renamed prompt:

- `openwebui_prompt_id` and `template_id` should continue to resolve;
- display label can update on next metadata refresh.

### 9.6. Seed Strategy

Gate 3 should seed or document creation of exactly two MVP prompts:

- `Краткий пересказ`: compact summary, decisions, risks, next steps.
- `Протокол встречи`: meeting-style protocol with topics, decisions, tasks,
  open questions and speaker-aware attribution when available.

Seed scripts may contain initial prompt text, but runtime source of truth becomes
OpenWebUI Prompts after creation.

## 10. Diarization Proof Plan

### 10.1. Runtime Toggle

Set in test runtime:

```text
STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true
```

Provider request must use:

```text
speaker_labels=true
response_format=verbose_json
```

### 10.2. Synthetic Audio Proof

Use synthetic two-speaker audio with known alternating segments.

Evidence required:

- provider request includes speaker labels;
- adapter capabilities show speaker support;
- normalized `TranscriptResultV1.segments[].speaker` is populated;
- normalized word speaker labels are populated when provider returns them;
- speaker-labeled projection contains speaker labels;
- raw provider JSON does not appear in prompt input/chat/logs.

### 10.3. Capability Checks

If provider capabilities say speaker labels are unsupported:

- keep diarization disabled;
- continue ordinary transcript path;
- mark speaker-aware templates unavailable when `requires_speakers=true`.

### 10.4. Speaker Policy

Prompts may refer to:

- `Speaker 1`;
- `Speaker 2`;
- `Unknown speaker`;
- semantic roles only with explicit `inferred` wording.

Prompts must not invent real names unless the transcript text itself provides
them.

## 11. Long Transcript Policy

### 11.1. Thresholds

Recommended configurable MVP thresholds:

```text
STT_V2_SINGLE_PASS_MAX_CHARS=60000
STT_V2_CHUNK_TARGET_CHARS=30000
STT_V2_CHUNK_OVERLAP_CHARS=1200
STT_V2_CHUNKING_MAX_CHARS=400000
```

These are defaults for policy and tests, not permanent product limits. Tune by
approved model context and runtime latency evidence.

### 11.2. Behavior

Single-pass:

- allowed when transcript is within `single_pass_max_chars`;
- stores one projection, one prompt variables artifact, one execution snapshot
  and one result.

Refusal-only first:

- Gate 6 should implement explicit refusal before chunking;
- no silent truncation;
- no partial processed result after refusal.

Chunking:

- Gate 7 only;
- allowed only when `template.chunkable=true`;
- chunk boundaries should prefer segment boundaries, then speaker turns, then
  timestamp windows;
- reduce prompt must preserve decisions, tasks, speaker labels and uncertainty
  notes;
- each chunk input/result is a transformation artifact linked to final result.

Hard refusal:

- transcript exceeds `chunking_max_chars`;
- template is not chunkable;
- speaker-required template is used with no speaker labels and no graceful
  fallback is defined.

### 11.3. Tests

Required tests:

- single-pass below threshold;
- refusal above threshold when `chunkable=false`;
- no silent truncation;
- speaker/timestamp-aware chunk boundary unit tests;
- chunk map/reduce contract tests for selected templates;
- no partial DOCX or processed-result export after refusal.

## 12. Future DOCX Export Blueprint

DOCX is the final export gate, not an immediate implementation slice.

### 12.1. Endpoint/File API Path

Preferred first path:

```text
POST /api/stt-v2/docx
Body: DocxExportRequestV1
Response: DocxExportResultV1 with short-lived download_url
```

Alternative after proof:

```text
sidecar generates DOCX
-> uploads through OpenWebUI file API
-> returns file_id
```

Do not assume OpenWebUI Action can safely return binary artifacts until runtime
proof exists.

### 12.2. Source And Layout

Source:

- only `PostProcessingResultV1`;
- never raw provider payload;
- never diagnostic artifacts;
- never hidden config or internal URLs.

Minimal layout:

- title;
- safe metadata;
- processed text/sections;
- optional warnings;
- export timestamp.

### 12.3. No-secrets Checks

Proof must unzip DOCX and scan XML/text for:

- API keys;
- provider payload fragments;
- internal URLs;
- auth tokens;
- raw Lemonfox JSON markers;
- hidden loader/config values.

## 13. Test And Proof Plan

### 13.1. Unit Tests

Cover:

- contract validation for `TranscriptResultV1`;
- artifact ref/record/chain validation;
- `ArtifactScopeV1` nullable-field and partial-scope behavior;
- retention policy decisions;
- projection builder;
- prompt variables and execution snapshot contracts;
- prompt catalog mapping;
- prompt missing/deleted/changed behavior;
- post-processing request/result contracts;
- product path without `internal_provider_response_ref`;
- source/prepared audio refs/metadata without default media copy;
- long transcript policy.

### 13.2. Action Tests

Cover:

- Action returns backwards-compatible flat text;
- Action carries or exposes `transcript_ref` where possible;
- sidecar failures return safe errors;
- no raw provider payload in Action output;
- product flow works when diagnostic provider refs are absent/null.

### 13.3. Loader Degradation Tests

Cover:

- loader disabled: base chat works;
- DOM hook missing: no-op;
- catalog unavailable: no quick actions;
- prompt action failure: user-safe error;
- no prompt bodies or provider payloads in loader-visible config.

### 13.4. Synthetic Diarization Proof

Evidence:

- `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true`;
- provider capabilities;
- two-speaker synthetic audio;
- normalized speaker labels in `TranscriptResultV1`;
- speaker-labeled projection/prompt variables;
- no raw provider leak.

### 13.5. DOCX Openability Proof

Future Gate 8 only.

Evidence:

- generated DOCX opens with `python-docx`;
- optional LibreOffice/Word manual proof;
- zip/XML no-secrets scan;
- size and checksum recorded;
- source `PostProcessingResultV1` id recorded.

### 13.6. OpenWebUI Upgrade-safety Checks

Checks:

- no OpenWebUI core file changes beyond accepted extension injection;
- Action still loads on pinned/upgraded runtime;
- Prompts API still returns catalog;
- file API path still works if used;
- base chat works with loader disabled;
- quick actions disappear safely if loader cannot attach.

## 14. Implementation Gates

### Gate 0. Refined Blueprint Accepted

Exit criteria:

- DOCX is explicitly deferred;
- artifact lineage is the central design object;
- storage/retention/artifact-scope policy is accepted for MVP;
- auto-run quick-action UX is accepted;
- no OpenWebUI core patch is planned.

### Gate 1. Runtime Diarization Proof

Exit criteria:

- `STAGE2_LEMONFOX_ENABLE_SPEAKER_LABELS=true` deployed in test runtime;
- capabilities show speaker support;
- synthetic two-speaker audio returns normalized speaker labels;
- projection and prompt variables use normalized speakers;
- no raw provider leak.

### Gate 2. Artifact Chain / Structured Transcript Preservation

Exit criteria:

- `transcript_ref` exists as alias to transcript `ArtifactRefV1`;
- persistent or explicitly MVP-approved artifact store exists;
- full `TranscriptResultV1` is retrievable by ref;
- artifact lineage links source file, prepared audio ref/metadata, STT job and
  transcript;
- durable artifact record carries recoverable `ArtifactScopeV1`;
- Gate 2 proof lists which identifiers are actually available in
  Action/loader/sidecar;
- available scope identifiers are captured: user/chat/message/file/job;
- workspace/project/client/tenant are captured only if runtime exposes them;
- fail-closed behavior works when scope/access cannot be proven;
- artifact payloads do not appear in ordinary logs;
- SQLite/volume path is not browser-accessible;
- artifact refs are opaque and unguessable;
- expired artifacts are not retrievable;
- access failure returns typed refusal;
- loader-visible refs are not sufficient for access;
- product path works without diagnostic raw provider payload;
- product path works without full rendered prompt snapshot;
- reload/restart behavior is proven or explicitly limited;
- flat transcript chat output remains backwards compatible.

### Gate 3. Prompt Catalog Seed And Routing

Exit criteria:

- two OpenWebUI Prompts exist or are seeded:
  `Краткий пересказ`, `Протокол встречи`;
- prompts carry required tags/meta or documented equivalent;
- sidecar resolves prompt id/command/template id;
- quick actions reference prompts, not prompt bodies.

### Gate 4. Two MVP Quick Actions With Auto-run

Exit criteria:

- quick actions are visible after successful transcript;
- click confirms template selection and native prompt submission intent;
- selected prompt is rendered as `PostProcessingPromptDraftV1`;
- prompt draft is submitted through ordinary OpenWebUI chat when possible;
- assistant response returns as the next normal chat message;
- server-side post-processing execution, if used in proof, is labelled fallback;
- failure path is safe.

### Gate 5. Prompt Catalog Access Proof

Exit criteria:

- group/resource visibility is tested;
- unauthorized user cannot see/use restricted prompt;
- prompt missing/deleted/changed behavior is tested;
- `prompt_version` or `prompt_body_hash` is captured in
  `PostProcessingResultV1`;
- metadata cache invalidation is proven.

### Gate 6. Long Transcript Refusal-only Behavior

Exit criteria:

- thresholds configured;
- refusal path tested;
- no silent truncation;
- no partial processed result/DOCX after refusal;
- user-facing refusal text accepted.

### Gate 7. Selected Chunking Support

Exit criteria:

- chunking enabled only for approved `chunkable=true` templates;
- speaker/timestamp-aware boundaries tested;
- map/reduce artifacts are linked in artifact lineage;
- final result preserves warnings and uncertainty notes.

### Gate 8. DOCX Final Export

Exit criteria:

- sidecar endpoint exports DOCX from `PostProcessingResultV1`;
- DOCX opens;
- no-secrets scan passes;
- no raw transcript/provider JSON/logs/internal URLs included by default;
- OpenWebUI file API upload is either proven or deferred explicitly.

## 15. Risks

- OpenWebUI internal prompt/file/action APIs may change across upgrades.
- Loader DOM hooks are brittle.
- OpenWebUI Action return shape may not support durable hidden metadata.
- Persistent artifact store introduces retention, deletion and access-control
  responsibility.
- Artifact/context identifiers may be incomplete if OpenWebUI context is not
  fully available to Action/loader/sidecar.
- Over-modeling tenant/multitenant semantics may overcomplicate STT v2 if
  OpenWebUI runtime does not expose tenant/org boundaries.
- Over-rich artifact contracts may delay the first useful Gate 1-2
  implementation if MVP-required and future fields are not separated.
- Speaker labels may be incomplete or inaccurate.
- Prompt catalog access may be hard to prove for all group/resource
  combinations.
- Auto-run prompt execution path may require more runtime proof than composer
  fallback.
- Long transcript chunking can distort decisions/tasks if reduce prompt is weak.
- DOCX file delivery path through OpenWebUI file API may require more runtime
  proof.
- Artifact leakage risk increases if diagnostic raw payload mode is enabled.

## 16. Open Questions

1. Which OpenWebUI Prompt fields can safely carry STT v2 metadata on target
   runtime?
2. Which OpenWebUI API path should execute prompts for auto-run and capture
   output safely?
3. Which artifact/context identifiers are actually available to Action, loader
   and sidecar in production?
4. Which artifact fields are truly required for Gate 1-2 proof, and which can
   remain nullable/future until post-processing execution starts?
5. Should chat deletion cascade artifact deletion immediately, or mark artifacts
   inaccessible and let TTL cleanup remove them?
6. Should source file deletion cascade transcript/result deletion by default?
7. What retention period is acceptable for transcripts and processed results
   after MVP?
8. Should project/client labels be user-supplied metadata, derived from chat
   title, or deferred entirely?
9. Which users/groups own STT v2 prompt edits?
10. Should speaker diarization be default-on after proof, or an operator toggle?
11. Which post-processing model is approved for long meeting transcripts?
12. Should DOCX include chat title by default when Gate 8 starts?

## 17. Non-goals

- Heavy OpenWebUI fork.
- OpenWebUI core patch without a separate accepted ADR.
- Separate Meetings app.
- Separate transcription portal.
- Full multitenant isolation model unless separately proven and accepted.
- `ArtifactChainV1` as a workflow engine or user-facing history product.
- DOCX in the immediate implementation slice.
- Raw provider JSON in prompt input, chat output, DOCX, browser state or product
  storage.
- CRM/task tracker integration.
- PDF export.
- Public URL/object-storage provider upload path until storage/access/expiry
  proof is complete.

## 18. Files Likely To Change Later

Likely code/config paths:

- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/job_store.py`
- `services/stage2-stt/stage2_stt/storage.py`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
- `deploy/openwebui-static/loader.js`
- `compose/openwebui.compose.yml`
- `.env.example`

Likely new modules:

- `services/stage2-stt/stage2_stt/artifact_store.py`
- `services/stage2-stt/stage2_stt/transcript_store.py`
- `services/stage2-stt/stage2_stt/transcript_projection.py`
- `services/stage2-stt/stage2_stt/prompt_catalog.py`
- `services/stage2-stt/stage2_stt/post_processing.py`
- `services/stage2-stt/stage2_stt/long_transcript.py`
- `services/stage2-stt/stage2_stt/docx_export.py`

Likely tests:

- `services/stage2-stt/tests/test_artifact_contracts.py`
- `services/stage2-stt/tests/test_artifact_store.py`
- `services/stage2-stt/tests/test_post_processing_contracts.py`
- `services/stage2-stt/tests/test_prompt_catalog.py`
- `services/stage2-stt/tests/test_transcript_store.py`
- `services/stage2-stt/tests/test_transcript_projection.py`
- `services/stage2-stt/tests/test_long_transcript_policy.py`
- `services/stage2-stt/tests/test_docx_export.py`
- loader smoke/degradation checks.

Likely docs:

- `docs/stage2/contracts/`
- `docs/stage2/config/STT_ENV_CONTRACT.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/context/`

## 19. Recommended Sequence

Recommended sequence:

1. Gate 0: accept this refined blueprint.
2. Gate 1: diarization proof on synthetic two-speaker audio.
3. Gate 2: artifact store, `transcript_ref` and structured transcript
   preservation.
4. Gate 3: OpenWebUI Prompt seed/routing for two MVP templates.
5. Gate 4: two auto-run quick actions.
6. Gate 5: prompt access/version proof.
7. Gate 6: refusal-only long transcript policy.
8. Gate 7: chunking for selected templates.
9. Gate 8: DOCX export from processed result.

Trade-offs:

- Putting artifact-store/lineage proof before quick actions makes the first
  slice less flashy, but prevents losing speaker/timestamp/prompt-version
  semantics.
- Putting prompt seed before auto-run keeps quick actions as prompt references,
  not duplicated templates.
- Refusal-only long transcript behavior before chunking prevents silent
  truncation while chunking quality is still unproven.
- Deferring DOCX avoids building export around unstable processed-result and
  storage contracts.
