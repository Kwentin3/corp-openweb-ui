# FFMPEG Workflow Artifact Inspection

## 1. Purpose

Record what was actually found for the existing audio/video transcription
workflow and define the ffmpeg.wasm dependency strategy before implementation.

This document is a contract/inspection note. It is not production code and does
not vendor ffmpeg, wasm binaries, provider keys or media assets.

## 2. Artifact Source

Current repo:

- Path: `D:\Users\Roman\Desktop\Проекты\corp-openweb ui`
- Result: no ffmpeg workflow implementation artifact found.
- Evidence: repository search found documentation references only. No
  `ffmpeg`, `ffmpeg.wasm`, `@ffmpeg/*`, `SharedArrayBuffer`, browser
  preprocessing implementation, package dependency or demo source was found
  outside docs.

External local candidate inspected:

- Path: `D:\Users\Roman\Desktop\Проекты\AutoProtokol`
- Result: external STT/upload context found; browser ffmpeg preprocessing
  artifact not found.
- Inspected files:
  - `stt/test-transcription-flow.ts.txt`
  - `data/stt-providers.json`
  - `presentation/gemini.service.ts.txt`
  - `presentation/google-file.service.ts.txt`
  - `s3_plan.md`
  - `cors/cors-config.json`
  - `next.config.js`
- Skipped intentionally:
  - `secret env GCS/`
  - any `.env` file
  - binary media samples
- Code copied into this repo: no.
- Binaries copied into this repo: no.

Inspection status:

- `artifact external only`
- `needs runtime/browser proof`
- ffmpeg preprocessing itself remains `not found`.

## 3. What The Workflow Does

Confirmed from the external candidate:

- There is STT/provider test flow that reads `public/test-audio.mp3`.
- Providers include `lemonfox` and `googleai` in config.
- STT adapters expect audio references and normalize provider responses into
  transcript text / speakers.
- Google/Gemini adapter resolves audio MIME from file metadata, filename or URI.
- S3 upload planning exists for large media files and includes direct upload,
  multipart upload, upload progress and abort/cleanup concepts.

Not confirmed:

- Browser-side ffmpeg preprocessing.
- Audio extraction from video in the browser.
- A concrete ffmpeg command.
- Prepared audio blob shape from ffmpeg.
- Desktop/mobile browser proof for ffmpeg preprocessing.

Stage 2 interpretation:

- The external candidate is useful evidence for STT/provider/upload boundary
  planning.
- It does not remove the ffmpeg preprocessing proof gap.
- ADR-0004 can reference this artifact as external STT/upload context, but must
  still require browser ffmpeg runtime proof before acceptance.

## 4. Supported Input Formats

Only values observed in the external candidate or existing Stage 2 research are
listed here. They are not proof that browser ffmpeg preprocessing supports all
formats.

| Format | Supported | Evidence |
| ------ | --------- | -------- |
| `mp3` | STT/upload context: yes; ffmpeg preprocessing: unknown | `test-audio.mp3`; MIME mapping to `audio/mpeg`; Lemonfox research |
| `wav` | STT/upload context: yes; ffmpeg preprocessing: unknown | MIME mapping to `audio/wav`; Lemonfox research |
| `m4a` | STT/upload context: yes; ffmpeg preprocessing: unknown | MIME mapping to `audio/mp4`; Lemonfox research |
| `webm` | STT/upload context: yes; ffmpeg preprocessing: unknown | MIME allowlist and default fallback to `audio/webm`; Lemonfox research |
| `ogg` | STT/upload context: yes; ffmpeg preprocessing: unknown | MIME allowlist; Lemonfox research |
| `flac` | STT/upload context: yes; ffmpeg preprocessing: unknown | MIME allowlist; Lemonfox research |
| `aac` | STT/upload context: yes; ffmpeg preprocessing: unknown | MIME allowlist; Lemonfox research |
| `mp4` | Upload/provider context: yes; ffmpeg preprocessing: unknown | MIME mapping to `video/mp4`; Lemonfox research |
| `mov` | Upload/provider context: yes; ffmpeg preprocessing: unknown | MIME mapping to `video/quicktime`; Lemonfox research |

Unsupported / unknown:

- Any format not listed above is `unknown / needs proof`.
- Browser ffmpeg support for all listed formats remains `needs proof`.

## 5. Output Contract

Confirmed output contract from the actual ffmpeg preprocessing artifact:

- Not found.

Observed external STT/upload contract:

- `GoogleFileRef`-like object:
  - `internalUri`
  - `name`
  - `mimeType`
  - optional `expireTime`
- STT adapter requires an `audio/*` MIME type.
- MIME allowlist includes:
  - `audio/webm`
  - `audio/webm;codecs=opus`
  - `audio/ogg`
  - `audio/ogg;codecs=opus`
  - `audio/wav`
  - `audio/x-wav`
  - `audio/mpeg`
  - `audio/mp3`
  - `audio/flac`
  - `audio/aac`
  - `audio/mp4`
- Fallback MIME in the inspected adapter is `audio/webm`.

Proposed Stage 2 prepared-audio contract for review:

- Browser submits prepared audio to Stage 2 backend as:
  - binary blob/file;
  - `source_file_name`;
  - `source_mime_type`;
  - `prepared_audio_mime_type`;
  - optional `duration_seconds`;
  - optional `preprocessing_profile`.
- Preferred first candidate output:
  - `audio/webm;codecs=opus` or `audio/webm`
  - reason: observed adapter fallback and browser-friendly audio container.
- Required fallback candidates:
  - `audio/mpeg` / `.mp3`
  - `audio/wav` / `.wav`
  - `audio/mp4` / `.m4a`

Open contract gap:

- The real ffmpeg command and resulting codec/container are not known.
- Do not promise one output type until browser smoke verifies that Lemonfox or
  another selected STT provider accepts it through the Stage 2 proxy.

## 6. Browser/Mobile Support

| Platform/browser | Status | Evidence |
| ---------------- | ------ | -------- |
| Desktop Chrome/Edge | needs proof | PRD says workflow exists, but no runnable artifact was found |
| Mobile browser | needs proof | PRD says workflow exists, but no runnable artifact was found |
| Safari/iOS | unknown | no artifact evidence |
| Android Chrome | unknown | no artifact evidence |

Do not write "works everywhere" until the actual workflow is run against target
desktop/mobile browsers.

## 7. Size And Duration Limits

Observed from external candidate:

- S3 / Google-file bridge contains `MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024`
  as an upper guard for a provider upload path.
- S3 plan discusses direct upload and multipart upload for media files over
  100 MB.
- ffmpeg.wasm FAQ states a 2 GB WebAssembly hard input limit.

Stage 2 limits that still need proof:

- max browser-local file size;
- max browser-local duration;
- mobile memory behavior;
- ffmpeg preprocessing timeout;
- upload timeout to Stage 2 proxy;
- selected provider direct-upload limit;
- selected provider URL-upload limit, if URL handoff is approved.

Conservative planning stance:

- treat browser ffmpeg as a small/medium-file preprocessing path until real
  mobile proof exists;
- define server-side validation independent of browser claims;
- keep large-file server fallback or URL-upload design as a separate approved
  path, not an implicit browser requirement.

## 8. Progress / Cancel / Retry

Observed from external candidate:

- S3 plan includes client upload progress through `xhr.upload.onprogress`.
- S3 plan includes retry and multipart abort concepts.
- AI service architecture notes timeout, retry, circuit breaker and
  `AbortController` for provider calls.

Observed from official ffmpeg.wasm API/docs:

- `ffmpeg.exec(args, timeout?)` supports a timeout and returns non-zero for
  timeout/error.
- `ffmpeg.on("progress", ({ progress, time }) => ...)` exists, but official API
  docs warn progress accuracy depends on input/output media length being the
  same.
- `ffmpeg.terminate()` exists and terminates the worker and ongoing progress.

Stage 2 contract:

- Browser preprocessing progress is advisory UI state, not authoritative backend
  job progress.
- Cancel must have two layers:
  - browser-side cancel/terminate for local preprocessing;
  - Stage 2 backend cancel for upload/provider/job lifecycle.
- Retry must not re-use stale prepared blobs unless the backend validates
  correlation/job ownership.

## 9. ffmpeg.wasm Dependency Strategy

Current official/package facts checked on 2026-06-18:

- `@ffmpeg/ffmpeg`
  - npm current version: `0.12.15`
  - license: `MIT`
  - role: JavaScript/TypeScript wrapper.
- `@ffmpeg/core`
  - npm current version: `0.12.10`
  - license: `GPL-2.0-or-later`
  - unpacked size: about 64.7 MB.
  - role: single-thread ffmpeg core.
- `@ffmpeg/core-mt`
  - npm current version: `0.12.10`
  - license: `GPL-2.0-or-later`
  - unpacked size: about 65.7 MB.
  - role: multi-thread ffmpeg core.

Strategy:

- Treat ffmpeg.wasm as an implementation dependency, not a provider boundary.
- Pin exact package versions in implementation planning.
- Prefer single-thread `@ffmpeg/core` for first proof unless performance tests
  require multi-thread.
- Prefer self-hosted, version-pinned core assets for corporate deployment if
  implementation chooses ffmpeg.wasm.
- Avoid public CDN dependency for production/corporate runtime unless explicitly
  accepted.
- Do not commit heavy core wasm assets or FFmpeg source into this repo without
  a separate ADR.
- If core assets are self-hosted, define:
  - asset path;
  - cache headers;
  - integrity/version metadata;
  - rollback path;
  - license notice location.
- If multi-thread `@ffmpeg/core-mt` is used, require SharedArrayBuffer proof and
  cross-origin isolation review.

Cross-origin isolation requirements:

- Multi-thread ffmpeg.wasm requires `SharedArrayBuffer`.
- `SharedArrayBuffer` requires a secure context and cross-origin isolation.
- This can affect Traefik/OpenWebUI headers, embedded resources and third-party
  scripts.
- Any COOP/COEP header change must be reviewed as an infra/browser behavior
  change before implementation.

## 10. Security And Privacy Notes

- Media preprocessing may happen browser-side, but it is not a security
  boundary.
- Browser must not receive STT provider API keys.
- Prepared audio goes only to Stage 2 backend / STT proxy.
- Stage 2 backend validates MIME, size, duration, auth/session, policy and
  retention even if browser already checked them.
- Source video should not be uploaded unless a fallback path is explicitly
  approved.
- The inspected external `AutoProtokol/next.config.js` shows provider key names
  in a build-time `env` block. No values were read, but this pattern is unsafe
  for Stage 2 if it exposes provider keys to browser bundles.
- Stage 2 must keep provider keys server-side and avoid build-time public
  exposure except for deliberately public `NEXT_PUBLIC_*` values.

## 11. Licensing Notes

- `@ffmpeg/ffmpeg` wrapper is MIT according to the official FAQ and npm
  metadata.
- `@ffmpeg/core` and `@ffmpeg/core-mt` are GPL-2.0-or-later according to npm
  metadata.
- Official ffmpeg.wasm FAQ states the core contains WebAssembly code transpiled
  from FFmpeg C code and follows FFmpeg and external library licenses.
- Core asset vendoring requires legal/license review and license notices.
- Do not vendor full FFmpeg source or heavy wasm/core assets without a separate
  ADR and explicit approval.

## 12. Gaps

- No actual browser ffmpeg workflow source was found.
- No ffmpeg command was found.
- No prepared audio output file was found.
- No proof of desktop/mobile browser execution was found.
- No max tested ffmpeg file size/duration was found.
- No browser memory profile was found.
- No COOP/COEP / SharedArrayBuffer proof was found.
- No direct Lemonfox smoke was performed.
- No API keys were used.

## 13. Recommended ADR Impact

Update ADR-0004 to state:

- current repo still lacks the actual ffmpeg preprocessing artifact;
- external `AutoProtokol` STT/upload artifact was inspected and remains
  external-only;
- inspected external artifact provides useful STT/upload/MIME boundary evidence
  but not ffmpeg preprocessing proof;
- implementation readiness should move from generic `missing artifact` to
  `external artifact inspected with ffmpeg preprocessing gaps`;
- dependency strategy should prefer pinned packages, self-hosted core assets and
  single-thread first;
- multi-thread requires SharedArrayBuffer / cross-origin isolation proof;
- no heavy wasm/core binaries or FFmpeg source should be committed without a
  separate ADR.

## 14. Sources

Local/external:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `D:\Users\Roman\Desktop\Проекты\AutoProtokol\stt\test-transcription-flow.ts.txt`
- `D:\Users\Roman\Desktop\Проекты\AutoProtokol\data\stt-providers.json`
- `D:\Users\Roman\Desktop\Проекты\AutoProtokol\presentation\gemini.service.ts.txt`
- `D:\Users\Roman\Desktop\Проекты\AutoProtokol\presentation\google-file.service.ts.txt`
- `D:\Users\Roman\Desktop\Проекты\AutoProtokol\s3_plan.md`
- `D:\Users\Roman\Desktop\Проекты\AutoProtokol\cors\cors-config.json`
- `D:\Users\Roman\Desktop\Проекты\AutoProtokol\next.config.js`

Official:

- https://ffmpegwasm.netlify.app/docs/overview/
- https://ffmpegwasm.netlify.app/docs/getting-started/usage/
- https://ffmpegwasm.netlify.app/docs/api/ffmpeg/classes/ffmpeg/
- https://ffmpegwasm.netlify.app/docs/faq/
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer
- https://www.npmjs.com/package/@ffmpeg/ffmpeg
- https://www.npmjs.com/package/@ffmpeg/core
- https://www.npmjs.com/package/@ffmpeg/core-mt

## 15. Status

`artifact external only`

`needs runtime/browser proof`

ADR-0004 can be reviewed with improved artifact/dependency context, but should
not be accepted until the real browser ffmpeg preprocessing workflow or a
replacement preprocessing implementation is proven.
