# Transcription STT Blueprint

## 1. Purpose

Спланировать priority transcription scenario для audio/video на базе existing ffmpeg workflow и
server-side STT proxy.

## 2. PRD-1 requirements covered

- Транскрибация - приоритетный сценарий заказчика.
- Есть существующий рабочий проект аудио/видео-транскрибации.
- ffmpeg workflow проверен на desktop and mobile.
- API keys не должны попадать в браузер.
- First STT provider: Lemonfox through `LemonfoxSttAdapter`.
- User-facing STT UX must live inside OpenWebUI. The sidecar is a
  backend/domain service, not a separate user-facing transcription GUI.
- MVP STT UX is an OpenWebUI-native media attachment `Transcribe` action.

## 3. Current known context

Browser-side ffmpeg preprocessing больше не считается research с нуля. Это technical asset, который
нужно встроить в OpenWebUI-contour. Основной риск - integration, not ffmpeg itself.

ffmpeg workflow is a media-preprocessing asset, not a security boundary.

External browser-side ffmpeg workflow contract is now inspected. The source
workflow uses `@ffmpeg/ffmpeg` v0.12.6, accepts audio/video candidates, runs
`ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`, returns an MP3 /
`audio/mpeg` browser `Blob` as the source-proven compatibility fallback, uploads
prepared audio through a presigned/internal storage path and leaves backend STT
orchestration to the server side. MP3 is not a permanent architecture
constraint; implementation must use an output profile contract. Opus is the
preferred default candidate if Lemonfox compatibility proof passes.

Input compatibility is ffmpeg.wasm capability-based. The product may offer a
normalization attempt for broad media candidates, but actual support depends on
the configured ffmpeg.wasm build, browser/runtime memory, file size, duration,
container, codec and successful audio-stream detection. This is not a guarantee
that every upstream FFmpeg-supported format is supported in production.

Lemonfox official docs list `mp3`, `wav`, `flac`, `aac`, `opus`, `ogg`, `m4a`,
`mp4`, `mpeg`, `mov`, `webm` and more, but do not explicitly prove the exact
Stage 2 WebM/Opus or OGG/Opus ffmpeg output profiles. The docs state 100 MB
direct upload and 1 GB public URL input limits. Maximum duration and
provider-side cancellation are not documented and need runtime proof or explicit
TBD handling.

Owner/operator proof accepts the ffmpeg workflow for ADR planning: it is
reported proven in two projects with the same stack/architecture, including
mobile and large-file cases. Optional implementation smoke can still run during
implementation/debug.

Stage 2 transcription work must start from backend/server-side STT proxy
boundary and the OpenWebUI media attachment action contract, not from a separate
STT frontend.

Implementation baseline, 2026-06-19:

- Backend sidecar/job routes, `LemonfoxSttAdapter`, runtime capabilities,
  OpenWebUI attachment `Transcribe` action patch and browser ffmpeg.wasm
  normalization are implemented.
- Stage 2 STT MVP is implemented/proven/current-stage closed and ready for
  broader testing. Remaining work is testing/hardening, not architectural
  discovery.
- Prepared MP3, MP4 with audio and WebM generated proof media reach the
  Action/sidecar path; unsupported/decode-failed and no-audio media fail with
  safe visible errors before provider handoff.
- The current static browser output profile is `mp3_high_compat`. Opus remains
  a production default candidate, not a proven deployed default.

## 4. Target user workflow

MVP workflow:

```text
Attach media candidate -> explicit Transcribe action -> ffmpeg probe ->
browser normalization -> prepared audio -> sidecar job -> Lemonfox ->
transcript in current OpenWebUI chat UX
```

Пользователь прикрепляет audio/video inside OpenWebUI chat/workspace UX.
Prepared MP3 and generated broad media normalization are current proven paths:
the UI shows `Transcribe` for audio/video candidates, then runs ffmpeg
probe/normalization before provider handoff. This action is the
user intent contract for browser-side ffmpeg.wasm normalization, prepared-audio
upload/job creation, backend/provider transcription and transcript return into
the current OpenWebUI chat/message/artifact UX. Prepared audio blob идет в
server-side STT proxy and storage lifecycle according to `auto|s3|none`.
Proxy проверяет auth/rights/limits/output profile, выбирает `LemonfoxSttAdapter` as first adapter,
добавляет server-side STT key, вызывает Lemonfox through adapter factory. UI показывает transcript
inside OpenWebUI as chat/message/file/artifact output, then templates:
протокол, задачи, решения, резюме, follow-up.

Future workflow:

```text
Dedicated transcription workspace/history/export/protocol flow is future.
```

Current transferable prepared-audio contract from the source workflow is MP3 /
`audio/mpeg`. Stage 2 keeps it as compatibility fallback. Opus is the preferred
default candidate pending Lemonfox compatibility proof.

Input-side contract candidate:

```text
SttMediaInputProfileV1 -> PreparedAudioMetadataV1
```

See:

- [STT Media Input Normalization Contract](../contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md)

## 4.1. Backend-first boundary

First implementation slice should define and test the STT proxy API before building final UI.

Boundary contract:

1. STT proxy contract: prepared audio blob, source input profile metadata,
   selected output profile, output transcript, timestamps/speaker labels where
   available.
2. Auth/permissions: caller must be authenticated and allowed to use transcription.
3. API key handling: STT provider keys live only server-side.
4. Provider request: Lemonfox is called first through `LemonfoxSttAdapter` behind
   `SttProviderAdapterFactory`.
5. Transcript normalization: provider response becomes a stable internal transcript shape.
6. Error model: ffmpeg probe/decode failure, no audio stream, too-large file,
   provider timeout, quota and validation errors are explicit.
7. Runtime capabilities: UI reads
   `GET /stage2-api/transcription/capabilities` /
   `TranscriptionRuntimeCapabilitiesV1` for input affordance hints, output
   profiles, limits, storage mode/health and provider capability flags.
8. Storage: normalized/prepared audio sent to provider follows
   `auto|s3|none`; `s3` fails fast if required storage is unavailable.
9. File size/duration policy: 1 GB browser input limit, 100 MB Lemonfox direct prepared-audio upload
   limit, max duration and fallback behavior are documented.
10. `>100 MB` warning/fail/fallback behavior uses stable reason codes.
11. Cancel lifecycle: preprocessing, upload and STT job cancel are supported where technically
   possible.
12. UI/browser integration uses the selected OpenWebUI-native static loader
    Action path for the MVP implementation; future work should harden that path
    rather than re-plan a separate STT GUI.
13. Future OpenWebUI-facing changes follow the extension-first implementation
    pattern: native mechanisms, Functions/Actions/Tools, thin static/UI shim,
    private sidecar, then fork only after proof and owner/ADR approval.

## 5. Native OpenWebUI first path

- Prefer an OpenWebUI Action Function/media attachment action for MVP if
  runtime probe confirms access to uploaded file references or bytes, `__user__`
  and status/events on the pinned OpenWebUI version.
- Fully implicit/magic LLM-triggered transcription is rejected for MVP. If a
  user types "транскрибируй" while a media attachment is present, OpenWebUI may
  surface or invoke the same explicit attachment action path.
- Keep OpenAPI Tool Server as the sidecar-friendly production candidate after
  schema, file handoff, auth headers and progress/cancel behavior are proven.
- Проверить native STT settings, file upload/chat attachment behavior,
  workspace model actions/tools, RBAC/groups and permissions.
- Использовать native auth/session where possible.
- Использовать workspace scenario and prompts/templates.
- Do not build or recommend a separate user-facing STT GUI.

## 6. Integration / custom implementation path

- Isolated transcription module.
- Minimal fork-slice only if native extension points insufficient.
- Server-side STT proxy.
- STT Provider Adapter Factory; Lemonfox is the first provider, not hardwired architecture.
- STT Provider Capability Profile and
  `TranscriptionRuntimeCapabilitiesV1` endpoint.
- Draft STT env/config contract for provider, output profile, ffmpeg assets, limits, storage and
  cancel behavior.
- Server-side fallback for large files if browser limits hit.
- Storage/retention handling for source file, audio blob, transcript.
- Thin UI can reuse the browser preprocessing pattern and call internal Stage 2
  APIs, but must not own provider keys, data policy or retention.

## 7. Data and security notes

STT API keys stay server-side. Browser calls only internal proxy. Transcripts may contain sensitive
meeting data; retention and visibility must be explicit.

Frontend must not decide provider keys, data policy, retention or access rules.

## 8. Dependencies

- Existing ffmpeg project details.
- FFMPEG workflow artifact inspection and ffmpeg asset loading mode decision.
- Output profile decision and Lemonfox compatibility proof.
- Lemonfox capability profile review: direct upload, URL upload, duration TBD,
  timestamps, speaker labels, callback and provider cancel unknown.
- STT env/config contract.
- Storage mode decision for prepared audio: `auto`, `s3` or `none`.
- Optional implementation smoke checklist; not a blocking ADR or
  implementation-planning gate.
- Lemonfox research.
- OpenWebUI capability research.
- OpenWebUI-native STT UX integration proof: static media attachment action,
  prepared upload handoff, sidecar call and transcript return are implemented
  for the MVP path; richer progress/cancel/access-policy hardening remains.
- Manager visibility/retention policy.
- Data policy.

## 9. Risks and constraints

- Large files.
- Media containers/codecs that the configured browser ffmpeg.wasm build cannot
  decode.
- Files with no audio stream.
- Progress/cancel UX.
- Browser memory on mobile.
- Upload limits/timeouts.
- Error handling.
- STT provider adapter mismatch.
- CDN/self-host ffmpeg asset mode.
- Prepared audio over 100 MB.
- Storage mode, storage health and retention.
- Provider maximum duration unknown until proof.
- Provider-side cancellation not documented until proof.
- Transcript storage and permissions.
- OpenWebUI update compatibility.
- OpenWebUI Action/Tool/OpenAPI behavior may differ from latest docs on the
  pinned deployment until runtime proof is captured.

## 10. Open questions

- What file size/duration limits are acceptable?
- Which ffmpeg.wasm build/assets and browser environments are accepted as the
  production capability baseline?
- Which Opus container does Lemonfox accept well enough for default profile:
  WebM/Opus or OGG/Opus?
- Does Lemonfox expose provider-side cancellation or only local cancellation is
  possible?
- What maximum provider/internal duration should Stage 2 enforce?
- Which self-hosted ffmpeg asset path is approved under portal/internal CDN?
- Should prepared audio storage mode be `auto`, `s3` or `none`, and what
  bucket/prefix/retention applies when S3 is used?
- Is server fallback required in Practical Stage 2?
- Is single-thread ffmpeg.wasm enough, or is multi-thread
  `SharedArrayBuffer` / COOP / COEP support required?
- Where are transcripts stored?
- Is diarization required in first slice?
- Which exact transcript persistence/history/export workflow is accepted after
  the MVP composer/chat return path?

## 11. Research links

- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](../research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)

## 12. Acceptance signals

- Audio/video test upload produces transcript through server-side proxy.
- Broad source-media support is presented as an ffmpeg normalization attempt,
  not a guarantee for every upstream FFmpeg format.
- Source MIME/extension is treated as a hint until ffmpeg probe/decode detects
  an audio stream.
- Browser bundle/network does not expose STT API key.
- Provider call is routed through documented STT provider adapter boundary.
- Lemonfox is first adapter, but orchestration still goes through factory.
- Provider capability profile is reviewed and runtime capabilities endpoint
  returns effective limits without secrets.
- Output profile is selected and validated; Opus candidate is proven before
  default and MP3 remains compatibility fallback.
- 1 GB browser input and 100 MB Lemonfox direct upload limits are documented.
- Prepared audio storage follows configured `auto|s3|none` semantics.
- Prepared audio over 100 MB produces warning/fail/fallback reason codes.
- Max duration and provider-side cancellation are either proven or exposed as
  `TBD`/unsupported in runtime capabilities.
- User can apply result templates.
- User can cancel preprocessing/upload/job lifecycle where technically
  possible.
- Unsupported/large/no-audio files produce clear errors or documented limits.
- STT proxy API contract is documented and implemented for the initial sidecar
  slice.
- Browser ffmpeg/preprocessing output contract is inspected and owner/operator
  proof is accepted for planning.
- Auth/permissions, provider errors and transcript normalization are covered by runtime proof.
- User launches and consumes transcription inside OpenWebUI; no separate
  user-facing STT GUI is accepted.
- Media attachment shows an explicit `Transcribe` action for supported
  audio/video, and unsupported files either do not show the action or return a
  safe error.
- Selected media attachment action path is implemented for the MVP static
  loader path; remaining work is hardening and product workflow acceptance.

## 13. Implementation readiness

ADR-0004 is still proposed for human review, but the initial implementation
path is no longer only planned. Backend sidecar/job routes, the OpenWebUI media
attachment Action path and browser ffmpeg.wasm normalization have been
implemented/proven. The current STT MVP implementation stage is closed; future
work starts from testing/hardening and product acceptance, not from
architecture discovery. Remaining readiness items are production output-profile
decision, Opus provider proof if selected, storage mode/config,
prepared-audio/transcript retention, licensing/ops review, cancel UX, duration
and file-limit policy, mobile/large-file acceptance and transcript
history/export workflow.
