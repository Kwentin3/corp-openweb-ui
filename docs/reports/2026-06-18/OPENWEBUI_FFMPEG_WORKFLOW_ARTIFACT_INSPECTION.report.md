# OpenWebUI FFMPEG Workflow Artifact Inspection Report

Date: 2026-06-18

Scope: ADR-0004 STT proxy boundary, ffmpeg workflow artifact inspection and
ffmpeg.wasm dependency strategy.

Update note:

- This report records the first inspection pass.
- Later operator/source-inspection input updated the artifact status from
  "browser preprocessing artifact not found" to "external ffmpeg workflow
  artifact inspected; transferable MP3 / `audio/mpeg` contract found; operator
  manual proof exists for reported mobile/large-file scenarios".
- Current status is tracked in
  [OPENWEBUI_ADR0004_FFMPEG_OPERATOR_PROOF_UPDATE.report.md](OPENWEBUI_ADR0004_FFMPEG_OPERATOR_PROOF_UPDATE.report.md)
  and
  [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md](../../stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md).

## 1. Executive Summary

ADR-0004 was refined with a stricter and more precise ffmpeg artifact status.

Current verdict:

- `ADR-0004` remains `Status: Proposed`;
- direct browser-to-provider STT calls remain rejected;
- STT provider API keys remain server-side only;
- external STT/upload context was found and inspected;
- the actual browser ffmpeg preprocessing artifact was not found;
- implementation readiness remains blocked until browser ffmpeg preprocessing is
  proven or a replacement preprocessing contract is approved.

The work does not start production implementation. No frontend/backend code,
compose files, scripts, environment files, wasm binaries, full FFmpeg assets or
provider keys were added or changed.

## 2. Artifact Search Result

Current repository:

- result: no browser ffmpeg workflow implementation artifact found;
- evidence: repository has documentation references to ffmpeg/STT/transcription,
  but no implementation code, demo, package dependency, wasm asset, ffmpeg
  command or runtime proof;
- status impact: current repo cannot prove the expected prepared-audio output.

External local context inspected:

- `<external-project-root>`;
- `stt/test-transcription-flow.ts.txt`;
- `data/stt-providers.json`;
- `presentation/gemini.service.ts.txt`;
- `presentation/google-file.service.ts.txt`;
- `s3_plan.md`;
- `cors/cors-config.json`;
- `next.config.js`.

External artifact verdict:

- STT/upload context exists;
- provider-side and upload-side MIME handling exists;
- S3/direct-upload planning exists;
- browser ffmpeg preprocessing implementation does not exist in the inspected
  files;
- no `@ffmpeg/ffmpeg`, `@ffmpeg/core` or `@ffmpeg/core-mt` dependency was found;
- no concrete ffmpeg command was found;
- no desktop/mobile browser proof was found;
- no COOP/COEP or `SharedArrayBuffer` proof was found.

This is therefore an external-only context inspection, not a usable ffmpeg
workflow import.

## 3. Output Contract

Confirmed output contract from the real browser ffmpeg preprocessing artifact:

- not found.

Observed STT/upload contract signals from external context:

- audio MIME allowlist includes WebM/Opus, OGG/Opus, WAV, MP3/MPEG, FLAC, AAC and
  MP4/M4A audio variants;
- upload/provider context maps MP3, WAV, M4A, MP4 and MOV file types;
- server-side adapter fallback uses `audio/webm` when audio MIME metadata is
  missing or weak;
- large media upload planning exists outside this repo, including progress,
  retry and abort semantics.

ADR review contract proposed for Stage 2:

- browser prepares an audio blob/file;
- first candidate output: `audio/webm;codecs=opus` or `audio/webm`;
- fallback candidates for review: `audio/mpeg`, `audio/wav`, `audio/mp4`;
- metadata should include source filename, source MIME, prepared MIME, optional
  duration and preprocessing profile;
- backend must validate size, duration, MIME/container and policy before calling
  provider;
- source video fallback is not allowed silently and must be an explicit review
  decision.

This proposed contract is not runtime proof.

## 4. Formats And Limits

Formats confirmed in STT/upload context, not in browser ffmpeg preprocessing:

| Format | Current status |
| ------ | -------------- |
| MP3 | STT/upload context yes; browser ffmpeg support unknown |
| WAV | STT/upload context yes; browser ffmpeg support unknown |
| M4A/MP4 audio | STT/upload context yes; browser ffmpeg support unknown |
| WebM/Opus | STT/upload context yes; browser ffmpeg support unknown |
| OGG/Opus | STT/upload context yes; browser ffmpeg support unknown |
| FLAC | STT/upload context yes; browser ffmpeg support unknown |
| AAC | STT/upload context yes; browser ffmpeg support unknown |
| MP4 video | Upload/provider context yes; preprocessing fallback unknown |
| MOV video | Upload/provider context yes; preprocessing fallback unknown |

Limits observed:

- external provider/upload context has a 2 GB server-side guard in inspected
  code;
- upload planning mentions multipart/direct-upload path for media larger than
  100 MB;
- official ffmpeg.wasm FAQ states a 2 GB hard input limit from WebAssembly;
- real browser/mobile memory, duration, timeout and thermal limits are unknown.

Stage 2 should treat browser ffmpeg as a small/medium-file preprocessing path
until proof says otherwise.

## 5. Progress, Cancel And Retry

External upload context:

- upload progress is planned through client upload progress events;
- retry and multipart abort are part of the upload planning;
- this does not prove ffmpeg preprocessing progress or cancel behavior.

Official ffmpeg.wasm API:

- `ffmpeg.exec(args, timeout?)` supports a timeout parameter;
- `ffmpeg.on("progress", ...)` supports progress events, with documented caveats;
- `ffmpeg.terminate()` terminates the worker and ongoing execution.

Required Stage 2 proof:

- local preprocessing progress UX;
- cancel during local preprocessing;
- retry after failed preprocessing;
- cancel/retry during server-side STT job;
- typed errors for unsupported format, too large, timeout, quota and provider
  failures.

## 6. ffmpeg.wasm Dependency Strategy

Verified package facts on 2026-06-18:

- `@ffmpeg/ffmpeg`: version `0.12.15`, MIT, wrapper package, unpacked size about
  72 KB;
- `@ffmpeg/core`: version `0.12.10`, GPL-2.0-or-later, single-thread core,
  unpacked size about 64.7 MB;
- `@ffmpeg/core-mt`: version `0.12.10`, GPL-2.0-or-later, multi-thread core,
  unpacked size about 65.7 MB.

Recommended strategy:

- treat ffmpeg.wasm as an implementation dependency, not a provider boundary;
- prefer single-thread `@ffmpeg/core` for first proof;
- pin package and core versions exactly in any implementation slice;
- prefer self-hosted/cached core assets for corporate deployment;
- do not depend on a public CDN in production unless explicitly accepted;
- do not vendor full FFmpeg source, heavy wasm/core binaries or generated assets
  into the repo without a separate ADR/implementation decision;
- select `@ffmpeg/core-mt` only after `SharedArrayBuffer`, COOP/COEP, Traefik and
  OpenWebUI embedding impacts are reviewed.

Licensing impact:

- the wrapper being MIT is not enough for a product decision;
- the WebAssembly core packages are GPL-2.0-or-later according to npm metadata;
- Stage 2 needs an explicit licensing/ops decision before shipping self-hosted
  core assets.

## 7. Security And Privacy Notes

Security constraints preserved:

- browser never receives STT provider API keys;
- browser never calls STT provider directly;
- backend remains the authority for auth, policy, limits, validation, provider
  key handling, provider call and audit/usage;
- frontend can own user interaction, local preprocessing and upload/progress UX
  only;
- ffmpeg preprocessing is not a security boundary.

External context warning:

- inspected external `next.config.js` exposes provider-key names through a
  build-time environment block; no values were read or used;
- Stage 2 must not copy this pattern if it exposes provider secrets to browser
  bundles.

## 8. ADR Impact

Updated `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`:

- preserved `Status: Proposed`;
- kept `Option B. Server-side STT proxy/job service` as recommended;
- kept direct browser-to-provider rejected;
- added `external artifact inspected with ffmpeg preprocessing gaps`;
- added explicit artifact source and found/not-found evidence;
- added prepared-audio candidate contract;
- added ffmpeg.wasm package/dependency strategy;
- added SharedArrayBuffer/COOP/COEP proof condition for multi-thread;
- added licensing and heavy-asset constraints;
- clarified that implementation readiness remains blocked by missing browser
  ffmpeg preprocessing proof.

Synchronized related docs:

- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`;
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`;
- `docs/stage2/CONTRACT_BOUNDARIES.md`;
- `docs/stage2/IMPLEMENTATION_GATES.md`;
- `docs/stage2/ENGINEERING_BACKLOG.md`;
- `docs/stage2/CONTEXT_INDEX.md`;
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`;
- `docs/stage2/README.md`;
- `README.md`.

## 9. Remaining Unknowns

- exact browser ffmpeg source location;
- exact ffmpeg command;
- exact output container/codec/MIME;
- browser worker model;
- package/core hosting path;
- desktop Chrome/Edge smoke;
- mobile browser smoke;
- real max file size and duration;
- cancellation behavior under load;
- memory behavior on low-memory mobile devices;
- whether source video fallback is allowed in Stage 2;
- whether self-hosted ffmpeg core assets are acceptable from licensing and ops
  perspective.

## 10. Gate Status

Gate 2, STT Proxy Boundary:

- ADR review: still required;
- ffmpeg artifact: external STT/upload context inspected, but browser
  preprocessing proof missing;
- output contract: proposed only, not runtime-proven;
- dependency strategy: documented, still requires review decision;
- implementation readiness: blocked.

Final status:

`ADR-0004 needs runtime proof before acceptance`

More precise operational wording:

`ADR-0004 is reviewable as a Proposed boundary decision, but must not be treated
as implementation-ready until browser ffmpeg preprocessing or a replacement
preprocessing contract is proven.`

## 11. Repository Validation

Validation run before commit:

- `git diff --check`: passed;
- changed files check: only `README.md` and `docs/**/*.md`;
- ADR invariant check: `Status: Proposed` is preserved;
- ADR invariant check: direct browser-to-provider remains rejected;
- ADR invariant check: provider keys remain server-side only;
- ADR invariant check: no backend/frontend implementation, no real API keys, no
  compose/env/scripts change and no heavy wasm/core vendoring;
- `npm view` package metadata check confirmed:
  - `@ffmpeg/ffmpeg` version `0.12.15`, MIT, unpacked size `71999`;
  - `@ffmpeg/core` version `0.12.10`, GPL-2.0-or-later, unpacked size
    `64689644`;
  - `@ffmpeg/core-mt` version `0.12.10`, GPL-2.0-or-later, unpacked size
    `65700111`.

Runtime proof not run:

- no browser smoke;
- no Lemonfox/provider call;
- no real API keys;
- no media/binary artifacts added.

## 12. Official Sources Checked

- https://ffmpegwasm.netlify.app/docs/overview/
- https://ffmpegwasm.netlify.app/docs/getting-started/usage/
- https://ffmpegwasm.netlify.app/docs/api/ffmpeg/classes/ffmpeg/
- https://ffmpegwasm.netlify.app/docs/faq/
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer
- https://www.npmjs.com/package/@ffmpeg/ffmpeg
- https://www.npmjs.com/package/@ffmpeg/core
- https://www.npmjs.com/package/@ffmpeg/core-mt
