# STT v2 Backward Compatibility Contract

Status: Gate 1-2 compatibility contract.

Date: 2026-07-02.

Scope: compatibility guarantees for the existing STT/OpenWebUI chat path while
implementing STT v2 Gate 1-2.

## 1. Purpose

Gate 1-2 must preserve the existing user-facing STT behavior while adding
diarization proof and internal structured transcript persistence.

If artifact features fail, ordinary OpenWebUI chat and the existing flat
transcript path must remain usable.

## 2. Existing Behavior To Preserve

The current path is:

```text
OpenWebUI media attachment
-> static loader Transcribe action
-> browser ffmpeg.wasm normalization when needed
-> OpenWebUI Action Function
-> private stage2-stt sidecar
-> LemonFox provider adapter
-> normalized TranscriptResultV1
-> flat Transcript: text returned to chat
```

The user-visible chat result must remain compatible with the existing
`Transcript:` text output unless the user receives a typed, user-safe error.

## 3. Compatibility Rules

Gate 1-2 must not:

- remove flat transcript output;
- require prompt catalog or quick actions;
- require DOCX;
- require a separate transcript UI;
- patch OpenWebUI core;
- expose raw provider payload;
- make normal chat depend on artifact-store success.

Gate 1-2 may:

- add a `transcript_ref` where the Action/result shape safely allows it;
- add internal artifact records;
- add sidecar endpoints for artifact retrieval;
- add tests proving compatibility.

## 4. Artifact Store Failure Behavior

If provider transcription succeeds but artifact store write fails:

- ordinary flat transcript output should still be returned when safe;
- user-safe warning may be included if existing Action warning shape supports it;
- no fake `transcript_ref` is returned;
- post-transcription artifact retrieval returns typed failure.

If artifact retrieval fails:

```text
artifact_not_found
artifact_expired
artifact_access_denied
artifact_scope_unverified
artifact_store_unavailable
```

Normal OpenWebUI chat must remain usable.

## 5. Loader-visible Refs

Loader-visible refs are not trust boundaries.

Rules:

- client-provided `transcript_ref` must be validated by sidecar;
- ref existence does not prove user access;
- malformed refs return typed refusal;
- expired refs return typed refusal;
- wrong user/context returns typed refusal.

## 6. No OpenWebUI Core Patch

Gate 1-2 must stay extension-first:

- OpenWebUI Action;
- static loader only if already part of the existing path;
- private `stage2-stt` sidecar;
- native OpenWebUI APIs only where already proven/needed;
- no core patch without separate ADR.

Open WebUI Functions are server-side plugin extension points, but Gate 1-2 does
not require new Function behavior beyond the existing Action bridge. Reference:
https://docs.openwebui.com/features/extensibility/plugin/functions/

## 7. Regression Proof

Required proof:

- successful ordinary audio still returns flat transcript text;
- video/unsupported media normalization path still reaches sidecar when existing
  MVP path supports it;
- provider error still returns user-safe error;
- artifact-store failure does not corrupt chat;
- no raw provider payload appears in chat/action/loader/logs;
- base chat works when artifact retrieval is unavailable.

## 8. Acceptance Criteria

This contract is satisfied when:

- existing flat transcript output tests pass;
- new artifact behavior is additive;
- no OpenWebUI core patch is present;
- artifact failures fail closed without breaking chat;
- sidecar validates refs instead of trusting loader-visible values.
