# STT v2 Gate 1-2 Implementation Boundary

Status: implementation boundary contract.

Date: 2026-07-02.

Scope: allowed and forbidden implementation areas for STT v2 Gate 1-2.

## 1. Purpose

Give the implementation agent a narrow file/module boundary so Gate 1-2 does
not drift into the full STT v2 epic.

## 2. Allowed Likely Code Paths

Likely existing files:

- `services/stage2-stt/stage2_stt/contracts.py`
- `services/stage2-stt/stage2_stt/config.py`
- `services/stage2-stt/stage2_stt/runtime.py`
- `services/stage2-stt/stage2_stt/lemonfox.py`
- `services/stage2-stt/stage2_stt/app.py`
- `services/stage2-stt/stage2_stt/job_store.py`
- `services/stage2-stt/stage2_stt/storage.py`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`

Likely new modules:

- `services/stage2-stt/stage2_stt/artifact_store.py`
- `services/stage2-stt/stage2_stt/transcript_store.py`
- `services/stage2-stt/stage2_stt/transcript_projection.py` only if needed for
  Gate 1 speaker-labeled proof.

Likely tests:

- `services/stage2-stt/tests/test_stt_v2_artifact_contracts.py`
- `services/stage2-stt/tests/test_stt_v2_artifact_store.py`
- `services/stage2-stt/tests/test_stt_v2_transcript_store.py`
- `services/stage2-stt/tests/test_stt_v2_diarization.py`
- focused Action compatibility tests if `transcript_ref` is exposed through the
  Action.

## 3. Allowed Behavior Changes

Allowed:

- enable/test LemonFox speaker labels through config;
- require verbose JSON when speaker labels are enabled;
- preserve normalized speaker labels;
- introduce opaque `transcript_ref`;
- persist normalized transcript artifacts;
- add internal artifact retrieval endpoint if needed;
- add storage/retention config;
- preserve flat transcript output.

## 4. Forbidden Areas

Forbidden in Gate 1-2:

- DOCX implementation;
- prompt catalog implementation;
- quick actions implementation;
- auto-run post-processing;
- model execution for transcript processing;
- long transcript chunking;
- CRM/task tracker integration;
- separate Meetings app;
- separate transcript history UI;
- public object-storage URL provider upload path;
- OpenWebUI core patch.

## 5. Action Boundary

OpenWebUI Action may be touched only to:

- preserve existing flat transcript output;
- carry or expose `transcript_ref` if the result shape safely allows it;
- surface user-safe artifact warning when persistence fails.

Action must not:

- include raw provider JSON;
- include artifact payloads;
- execute prompts;
- create DOCX;
- trust loader-visible refs as access proof.

## 6. Storage Boundary

ArtifactStore is internal technical storage only.

It must not:

- serve a browser-accessible transcript archive;
- expose SQLite/volume path;
- log transcript payloads;
- become a workflow engine;
- become a tenant/multitenant authorization model.

## 7. Review Checklist

Review fails if:

- any OpenWebUI core file is patched without ADR;
- DOCX/prompt/quick-action code appears;
- `ArtifactScopeV1` includes result refs as scope fields;
- raw LemonFox JSON is stored in product artifacts;
- product path depends on diagnostic provider payload;
- flat transcript output regresses;
- artifact refs are sequential or guessable;
- storage path is browser-accessible.
