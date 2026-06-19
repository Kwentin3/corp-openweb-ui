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

## 3. Current known context

Browser-side ffmpeg preprocessing больше не считается research с нуля. Это technical asset, который
нужно встроить в OpenWebUI-contour. Основной риск - integration, not ffmpeg itself.

ffmpeg workflow is a media-preprocessing asset, not a security boundary.

External browser-side ffmpeg workflow contract is now inspected. The source
workflow uses `@ffmpeg/ffmpeg` v0.12.6, accepts audio/video input, runs
`ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`, returns an MP3 /
`audio/mpeg` browser `Blob` as the source-proven compatibility fallback, uploads
prepared audio through a presigned/internal storage path and leaves backend STT
orchestration to the server side. MP3 is not a permanent architecture
constraint; implementation must use an output profile contract. Opus is the
preferred default candidate if Lemonfox compatibility proof passes.

Operator manual proof reports successful mobile testing with large videos and
large WAV files. Treat this as useful manual evidence, not as a reproducible
proof matrix or universal mobile/file support promise.

Stage 2 transcription work must start from backend/server-side STT proxy boundary, not final
frontend UI.

## 4. Target user workflow

Пользователь загружает audio/video. GUI готовит audio через browser ffmpeg workflow according to the
selected output profile. Prepared audio blob идет в server-side STT proxy and S3/object storage.
Proxy проверяет auth/rights/limits/output profile, выбирает `LemonfoxSttAdapter` as first adapter,
добавляет server-side STT key, вызывает Lemonfox through adapter factory. UI показывает transcript
и templates: протокол, задачи, решения, резюме, follow-up.

Current transferable prepared-audio contract from the source workflow is MP3 /
`audio/mpeg`. Stage 2 keeps it as compatibility fallback. Opus is the preferred
default candidate pending Lemonfox compatibility proof.

## 4.1. Backend-first boundary

First implementation slice should define and test the STT proxy API before building final UI.

Boundary contract:

1. STT proxy contract: input audio blob, metadata, selected output profile,
   output transcript, timestamps/speaker labels where available.
2. Auth/permissions: caller must be authenticated and allowed to use transcription.
3. API key handling: STT provider keys live only server-side.
4. Provider request: Lemonfox is called first through `LemonfoxSttAdapter` behind
   `SttProviderAdapterFactory`.
5. Transcript normalization: provider response becomes a stable internal transcript shape.
6. Error model: unsupported format, too-large file, provider timeout, quota and validation errors
   are explicit.
7. Storage: normalized/prepared audio sent to provider is stored in S3/object storage with
   env-configured bucket, prefix and retention.
8. File size/duration policy: 1 GB browser input limit, 100 MB Lemonfox direct prepared-audio upload
   limit, max duration and fallback behavior are documented.
9. Cancel lifecycle: preprocessing, upload and STT job cancel are supported where technically
   possible.
10. UI/browser integration follows after proxy boundary and runtime smoke.

## 5. Native OpenWebUI first path

- Проверить native STT settings.
- Проверить file upload and chat attachment behavior.
- Использовать native auth/session where possible.
- Использовать workspace scenario and prompts/templates.

## 6. Integration / custom implementation path

- Isolated transcription module.
- Minimal fork-slice only if native extension points insufficient.
- Server-side STT proxy.
- STT Provider Adapter Factory; Lemonfox is the first provider, not hardwired architecture.
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
- STT env/config contract.
- S3/object storage decision for prepared audio.
- Lightweight reproducible proof matrix.
- Lemonfox research.
- OpenWebUI capability research.
- Manager visibility/retention policy.
- Data policy.

## 9. Risks and constraints

- Large files.
- Progress/cancel UX.
- Browser memory on mobile.
- Upload limits/timeouts.
- Error handling.
- STT provider adapter mismatch.
- CDN/self-host ffmpeg asset mode.
- Prepared audio over 100 MB.
- S3/object storage and retention.
- Transcript storage and permissions.
- OpenWebUI update compatibility.

## 10. Open questions

- What file size/duration limits are acceptable?
- Which Opus container does Lemonfox accept well enough for default profile:
  WebM/Opus or OGG/Opus?
- Which self-hosted ffmpeg asset path is approved under portal/internal CDN?
- What S3 bucket/prefix/retention should store prepared audio?
- Is server fallback required in Practical Stage 2?
- Is single-thread ffmpeg.wasm enough, or is multi-thread
  `SharedArrayBuffer` / COOP / COEP support required?
- Where are transcripts stored?
- Is diarization required in first slice?

## 11. Research links

- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](../research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)

## 12. Acceptance signals

- Audio/video test upload produces transcript through server-side proxy.
- Browser bundle/network does not expose STT API key.
- Provider call is routed through documented STT provider adapter boundary.
- Lemonfox is first adapter, but orchestration still goes through factory.
- Output profile is selected and validated; Opus candidate is proven before
  default and MP3 remains compatibility fallback.
- 1 GB browser input and 100 MB Lemonfox direct upload limits are documented.
- Prepared audio is stored in configurable S3/object storage.
- User can apply result templates.
- User can cancel preprocessing/upload/job lifecycle where technically
  possible.
- Unsupported/large files produce clear errors or documented limits.
- STT proxy API contract is documented before final UI work.
- Browser ffmpeg/preprocessing output contract is inspected and lightweight
  proof matrix is captured before implementation acceptance.
- Auth/permissions, provider errors and transcript normalization are covered by runtime proof.

## 13. Implementation readiness

Needs ADR for STT proxy boundary before implementation. ADR-0004 is proposed for
human review. The missing-artifact blocker is removed, but implementation
readiness still requires lightweight proof matrix, production output profile
decision, Lemonfox adapter config, self-hosted ffmpeg asset path, S3 prepared
audio storage config, prepared-audio retention, licensing/ops review, cancel
lifecycle and file-limit policy. Browser/UI work follows after backend
contract, preprocessing contract and runtime proof.
