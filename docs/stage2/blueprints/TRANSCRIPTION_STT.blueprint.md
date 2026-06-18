# Transcription STT Blueprint

## 1. Purpose

Спланировать priority transcription scenario для audio/video на базе existing ffmpeg workflow и
server-side STT proxy.

## 2. PRD-1 requirements covered

- Транскрибация - приоритетный сценарий заказчика.
- Есть существующий рабочий проект аудио/видео-транскрибации.
- ffmpeg workflow проверен на desktop and mobile.
- API keys не должны попадать в браузер.
- STT provider priority: Lemonfox.

## 3. Current known context

Browser-side ffmpeg preprocessing больше не считается research с нуля. Это technical asset, который
нужно встроить в OpenWebUI-contour. Основной риск - integration, not ffmpeg itself.

ffmpeg workflow is a media-preprocessing asset, not a security boundary.

Actual ffmpeg workflow artifact is not present in this repository. The Stage 2
contract can define the expected boundary, but implementation remains blocked
until the real artifact output format, MIME/content type, browser/mobile support,
worker model, progress/cancel behavior and limits are inspected.

Stage 2 transcription work must start from backend/server-side STT proxy boundary, not final
frontend UI.

## 4. Target user workflow

Пользователь загружает audio/video. GUI готовит audio через browser ffmpeg workflow. Prepared audio
blob идет в server-side STT proxy. Proxy проверяет auth/rights/limits, добавляет STT key, вызывает
Lemonfox/selected provider. UI показывает transcript и templates: протокол, задачи, решения, резюме,
follow-up.

## 4.1. Backend-first boundary

First implementation slice should define and test the STT proxy API before building final UI.

Boundary contract:

1. STT proxy contract: input audio blob, metadata, output transcript, timestamps/speaker labels
   where available.
2. Auth/permissions: caller must be authenticated and allowed to use transcription.
3. API key handling: STT provider keys live only server-side.
4. Provider request: Lemonfox or selected STT provider is called only by proxy/server.
5. Transcript normalization: provider response becomes a stable internal transcript shape.
6. Error model: unsupported format, too-large file, provider timeout, quota and validation errors
   are explicit.
7. Optional persistence/audit: source file, audio blob and transcript retention are controlled by
   policy.
8. File size/duration policy: max duration, max upload and mobile/browser limits are documented.
9. UI/browser integration follows after proxy boundary and runtime smoke.

## 5. Native OpenWebUI first path

- Проверить native STT settings.
- Проверить file upload and chat attachment behavior.
- Использовать native auth/session where possible.
- Использовать workspace scenario and prompts/templates.

## 6. Integration / custom implementation path

- Isolated transcription module.
- Minimal fork-slice only if native extension points insufficient.
- Server-side STT proxy.
- Server-side fallback for large files if browser limits hit.
- Storage/retention handling for source file, audio blob, transcript.

## 7. Data and security notes

STT API keys stay server-side. Browser calls only internal proxy. Transcripts may contain sensitive
meeting data; retention and visibility must be explicit.

Frontend must not decide provider keys, data policy, retention or access rules.

## 8. Dependencies

- Existing ffmpeg project details.
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
- Transcript storage and permissions.
- OpenWebUI update compatibility.

## 10. Open questions

- What file size/duration limits are acceptable?
- Is server fallback required in Practical Stage 2?
- Where are transcripts stored?
- Is diarization required in first slice?

## 11. Research links

- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)

## 12. Acceptance signals

- Audio/video test upload produces transcript through server-side proxy.
- Browser bundle/network does not expose STT API key.
- User can apply result templates.
- Unsupported/large files produce clear errors or documented limits.
- STT proxy API contract is documented before final UI work.
- Auth/permissions, provider errors and transcript normalization are covered by runtime proof.

## 13. Implementation readiness

Needs ADR for STT proxy boundary before implementation. ADR-0004 is proposed for
human review, but implementation readiness is still blocked by missing ffmpeg
artifact inspection. Browser/UI work follows after backend contract, artifact
contract and runtime proof.
