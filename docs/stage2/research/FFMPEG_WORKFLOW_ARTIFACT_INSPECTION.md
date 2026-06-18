# FFMPEG Workflow Artifact Inspection

## 1. Purpose

Record the current Stage 2 understanding of the external browser-side ffmpeg
workflow that prepares audio/video files for STT.

This document is a contract/inspection note. It is not production code and does
not vendor ffmpeg, wasm binaries, provider keys or media assets.

## 2. Artifact Source

Current repo:

- Path: `D:\Users\Roman\Desktop\Проекты\corp-openweb ui`
- Result: planning docs only; the external workflow source code is not copied
  into this repo.
- Code copied into this repo: no.
- Binaries copied into this repo: no.

Earlier local context inspected:

- Path: `D:\Users\Roman\Desktop\Проекты\AutoProtokol`
- Result: useful STT/upload context, but not the browser ffmpeg source itself.
- Inspected context included STT provider config, provider adapters, S3/direct
  upload planning and MIME handling.
- Skipped intentionally:
  - `secret env GCS/`
  - any `.env` file
  - binary media samples

Later operator-provided/source inspection input:

- external browser-side ffmpeg workflow exists;
- source workflow uses `@ffmpeg/ffmpeg` v0.12.6;
- source workflow loads ffmpeg assets from `unpkg.com`;
- output contract is MP3 / `audio/mpeg`;
- command is
  `ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`;
- backend STT/upload pipeline exists;
- API keys do not go to the browser;
- handoff pattern is browser -> prepared audio blob -> presigned/internal
  upload -> backend STT orchestration.

Inspection status:

- `external ffmpeg workflow artifact inspected`;
- `transferable browser-side preprocessing contract found`;
- `operator manual proof confirms reported mobile and large-file scenarios`;
- implementation still requires reproducible proof matrix and production
  dependency decisions.

## 3. What The Workflow Does

Confirmed transferable flow:

1. User selects audio or video in the browser.
2. Browser-side ffmpeg extracts/converts audio locally.
3. The workflow writes an MP3 output through ffmpeg.wasm.
4. Browser receives a prepared audio `Blob`.
5. Prepared audio is uploaded through a presigned/internal-storage path.
6. Backend STT orchestration continues by object key.
7. Backend owns provider call, provider keys, validation, policy, usage and
   retention.

The workflow remains media preprocessing only. It is not a security boundary.

## 4. Transferable Contract

Browser input:

- accepts `audio/*`;
- accepts `video/*`;
- source project UI limit: 1 GB;
- source-confirmed formats:
  - MP3;
  - WAV;
  - M4A;
  - WebM;
  - MP4 video;
  - MOV video.

Transformation:

```bash
ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3
```

Output:

- container: MP3;
- codec: `libmp3lame`;
- MIME: `audio/mpeg`;
- browser output: `Blob`;
- handoff: presigned/internal upload, then backend STT orchestration by object
  key.

Security:

- no API keys in browser;
- browser does not call STT provider;
- backend/STT proxy owns provider keys, validation, policy, usage and retention.

## 5. Supported Input Formats

These are source workflow / operator-provided inspection facts, not a promise
that every possible file with these extensions will succeed under every device.

| Format | Current status | Evidence |
| ------ | -------------- | -------- |
| `mp3` | source workflow supported | source inspection input |
| `wav` | source workflow supported; large WAV operator-tested | source inspection input; operator manual proof |
| `m4a` | source workflow supported | source inspection input |
| `webm` | source workflow supported | source inspection input |
| `mp4` | source workflow supported; large video operator-tested | source inspection input; operator manual proof |
| `mov` | source workflow supported | source inspection input |

Unknown:

- exact browser/device matrix;
- exact tested file sizes;
- exact tested durations;
- memory behavior on low-memory mobile devices;
- failure behavior for corrupt, unsupported or too-large files.

## 6. Operator Manual Proof

Operator reported manual testing:

- workflow was tested on a mobile device;
- large videos were tested;
- large WAV files were tested;
- result: workflow worked correctly in the tested cases.

Engineering interpretation:

- this is useful operator evidence;
- it removes the absolute "missing ffmpeg artifact" blocker;
- it does not equal automated repository proof;
- it does not prove universal mobile support;
- it does not prove all files are supported;
- Stage 2 acceptance should still capture a reproducible proof matrix with
  device/browser/file metadata.

Proof matrix to capture before implementation acceptance:

| Test case | Device | Browser | File type | File size | Duration | Output format | Result | Evidence |
| --------- | ------ | ------- | --------- | --------: | -------: | ------------- | ------ | -------- |
| Mobile large video | operator reported | operator reported | video | TBD | TBD | MP3 / `audio/mpeg` | operator reported pass | TBD |
| Mobile large WAV | operator reported | operator reported | WAV | TBD | TBD | MP3 / `audio/mpeg` | operator reported pass | TBD |
| Desktop baseline audio | TBD | TBD | MP3/WAV/M4A/WebM | TBD | TBD | MP3 / `audio/mpeg` | TBD | TBD |
| Desktop baseline video | TBD | TBD | MP4/MOV | TBD | TBD | MP3 / `audio/mpeg` | TBD | TBD |

## 7. Size And Duration Limits

Current facts:

- source project UI limit: 1 GB;
- operator manually tested large videos and large WAV files successfully;
- previous provider/upload context included a 2 GB server-side guard in an
  external upload path;
- ffmpeg.wasm has a WebAssembly hard input limit documented as 2 GB.

Stage 2 still needs production policy:

- max accepted file size;
- max accepted duration;
- device/browser support matrix;
- fallback behavior for files over limit;
- typed error for unsupported or too-large files;
- whether server-side fallback is needed for practical Stage 2.

## 8. Progress / Cancel / Retry

Known:

- source workflow handoff uses a prepared blob and presigned/internal upload;
- earlier upload context included progress, retry and multipart abort concepts;
- official ffmpeg.wasm API supports `exec(args, timeout?)`, progress events and
  `terminate()`.

Still required:

- reproducible local preprocessing progress proof;
- cancel during local preprocessing;
- retry after failed local preprocessing;
- cancel/retry during server-side STT job;
- typed errors for timeout, quota, provider failure, unsupported format and
  too-large files.

## 9. ffmpeg.wasm Dependency Strategy

Source workflow facts:

- source package: `@ffmpeg/ffmpeg` v0.12.6;
- source asset hosting: `unpkg.com`;
- source output format: MP3 / `audio/mpeg`;
- source command uses `libmp3lame`.

Production strategy:

- treat ffmpeg.wasm as an implementation dependency, not a provider boundary;
- pin exact package/core versions for Stage 2 implementation;
- prefer single-thread first unless performance evidence requires multi-thread;
- do not accept public CDN dependency silently for corporate production;
- prefer self-hosted or internally cached core assets;
- define asset path, cache headers, rollback and license notices;
- do not commit heavy wasm/core binaries or FFmpeg source into this repo without
  a separate ADR/decision;
- select production prepared-audio format after STT provider compatibility and
  licensing/ops review.

Multi-thread caveat:

- multi-thread ffmpeg.wasm requires `SharedArrayBuffer`;
- `SharedArrayBuffer` requires secure context and cross-origin isolation;
- COOP/COEP changes require Traefik/header and OpenWebUI embedding review.

## 10. Output Format Decision

Source workflow proves MP3 / `audio/mpeg` as the transferable contract.

MP3 is not automatically the final production decision. Stage 2 should decide
the production prepared-audio format after:

- STT provider compatibility smoke;
- licensing review for MP3 / `libmp3lame`;
- size/cost/quality comparison;
- browser support review;
- operations decision for asset hosting.

Alternatives that remain available for review:

- `audio/webm;codecs=opus`;
- `audio/ogg;codecs=opus`;
- `audio/wav`, if size is acceptable.

## 11. Security And Privacy Notes

- Browser preprocessing is not a security boundary.
- Browser must not receive STT provider API keys.
- Browser must not call STT provider directly.
- Prepared audio goes to internal storage / Stage 2 backend.
- Backend validates MIME, size, duration, auth/session, policy and retention
  even when browser preprocessing succeeds.
- Source video upload fallback is not allowed silently; it requires explicit
  approval.
- No API keys were read or used for this docs update.

## 12. Gaps

- No source code was copied into this repo.
- No wasm/core binaries were added.
- No automated proof matrix is captured yet.
- Exact mobile device and browser metadata are TBD.
- Exact tested large-file sizes and durations are TBD.
- Production output format is not final.
- Production ffmpeg asset hosting is not final.
- Licensing/ops review is not final.
- Lemonfox/provider compatibility smoke is still required.
- No API keys were used.

## 13. Recommended ADR Impact

Update ADR-0004 to state:

- previous `missing ffmpeg artifact` blocker is removed;
- external ffmpeg workflow artifact was inspected;
- transferable browser-side preprocessing contract is MP3 / `audio/mpeg`;
- operator manual proof exists for reported mobile and large-file cases;
- operator proof is manual evidence, not automated repository proof;
- implementation readiness still requires ADR approval, reproducible proof
  matrix and production dependency decisions;
- production caveats remain visible: output format, self-host/CDN, licensing and
  file limits.

## 14. Sources

Local/repo:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/reports/2026-06-18/OPENWEBUI_FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.report.md`
- `docs/reports/2026-06-18/FFMPEG_WASM_WORKFLOW_INSPECTION.report.md`

Operator/source inspection input:

- `FFMPEG_WASM_WORKFLOW_INSPECTION.report.md` facts provided in the task text;
- operator manual proof for mobile device, large videos and large WAV files.

Official/reference context from earlier inspection:

- https://ffmpegwasm.netlify.app/docs/overview/
- https://ffmpegwasm.netlify.app/docs/getting-started/usage/
- https://ffmpegwasm.netlify.app/docs/api/ffmpeg/classes/ffmpeg/
- https://ffmpegwasm.netlify.app/docs/faq/
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer
- https://www.npmjs.com/package/@ffmpeg/ffmpeg
- https://www.npmjs.com/package/@ffmpeg/core
- https://www.npmjs.com/package/@ffmpeg/core-mt

## 15. Status

`external ffmpeg workflow artifact inspected`

`transferable browser-side preprocessing contract found`

`operator manual proof exists for reported mobile/large-file scenarios`

ADR-0004 is reviewable with the inspected transferable ffmpeg contract.
Implementation still requires ADR approval, reproducible proof matrix and
production dependency decisions.
