# Transcription STT Blueprint

## 1. Purpose

Спланировать priority transcription scenario для audio/video на базе existing ffmpeg workflow и server-side STT proxy.

## 2. PRD-1 requirements covered

- Транскрибация - приоритетный сценарий заказчика.
- Есть существующий рабочий проект аудио/видео-транскрибации.
- ffmpeg workflow проверен на desktop and mobile.
- API keys не должны попадать в браузер.
- STT provider priority: Lemonfox.

## 3. Current known context

Browser-side ffmpeg preprocessing больше не считается research с нуля. Это technical asset, который нужно встроить в OpenWebUI-contour. Основной риск - integration, not ffmpeg itself.

## 4. Target user workflow

Пользователь загружает audio/video. GUI готовит audio через browser ffmpeg workflow. Prepared audio blob идет в server-side STT proxy. Proxy проверяет auth/rights/limits, добавляет STT key, вызывает Lemonfox/selected provider. UI показывает transcript и templates: протокол, задачи, решения, резюме, follow-up.

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

STT API keys stay server-side. Browser calls only internal proxy. Transcripts may contain sensitive meeting data; retention and visibility must be explicit.

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

## 13. Implementation readiness

Needs research and ADR for STT proxy design before implementation.
