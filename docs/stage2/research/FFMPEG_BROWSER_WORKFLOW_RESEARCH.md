# FFMPEG Browser Workflow Research

## 1. Question

How should the existing browser ffmpeg workflow be embedded into the OpenWebUI contour?

## 2. Research status

Status: researched from ffmpeg.wasm official docs on 2026-06-18 and updated
after local/external artifact inspection on 2026-06-18.

Result type: integration boundary. Existing customer/executor ffmpeg project was not present in this
repo. External `D:\Users\Roman\Desktop\Проекты\AutoProtokol` STT/upload context
was inspected, but it does not contain the browser ffmpeg preprocessing
implementation, command, `@ffmpeg/*` dependency or browser/mobile proof.

## 3. Findings

- `ffmpeg.wasm` is a WebAssembly/JavaScript port of FFmpeg that runs media processing in the
  browser.
- It runs transcoding work in a web worker by default because multimedia processing is
  resource-intensive.
- Input files must be written into the ffmpeg core virtual filesystem, commands executed, and output
  files read back from that filesystem.
- Current 0.12+ API uses `new FFmpeg()`, `ffmpeg.load()`, `writeFile()`, `exec()`, `readFile()` and
  `terminate()`.
- The official usage example loads a core around 31 MB from CDN. Production integration should
  decide whether core assets are self-hosted, cached and version-pinned.
- Multi-thread mode requires `SharedArrayBuffer` and browser security requirements/cross-origin
  isolation. Single-thread mode is simpler but may be slower.
- The official docs include abort/progress patterns, but UX still needs project-specific
  timeout/cancel handling.
- Current npm package state checked for planning: `@ffmpeg/ffmpeg` wrapper is
  MIT, while `@ffmpeg/core` and `@ffmpeg/core-mt` are GPL-2.0-or-later
  WebAssembly core packages with large unpacked sizes. Production use needs
  explicit version pinning, asset hosting and licensing review.
- The inspected external artifact confirms STT/upload patterns and audio MIME
  handling, but not the actual local ffmpeg output contract.

## 4. Integration recommendation

Do not fork OpenWebUI just to host ffmpeg first.

Preferred shape for Stage 2 planning:

- separate transcription UI/module or sidecar page behind the same corporate auth boundary;
- browser ffmpeg converts/extracts audio locally;
- server-side STT proxy receives only prepared audio;
- proxy applies size/duration/format limits and provider key;
- transcript is returned to user and can be pasted/sent into OpenWebUI scenario templates.

A deeper OpenWebUI integration can be considered only after the sidecar/proxy path proves user value
and acceptance.

Backend-first clarification:

- ffmpeg workflow is media preprocessing only;
- it must not own provider keys, data policy, access control or retention;
- STT proxy contract and runtime smoke must be defined before final UI integration.

## 5. Open questions

- Where is the existing ffmpeg workflow artifact and what exact formats does it output?
- Does it already work in target mobile browsers under corporate domain headers?
- Is multi-thread performance required, or is single-thread enough for pilot?
- Should ffmpeg core be vendored/self-hosted to avoid CDN dependency?
- What max local file size is acceptable for low-memory mobile devices?

## 6. Acceptance proof needed

- desktop Chrome/Edge smoke;
- one mobile browser smoke;
- large file cancel/timeout behavior;
- no raw media upload before user starts STT proxy call;
- prepared audio format accepted by Lemonfox proxy.
- browser workflow output contract matches the backend proxy input contract.
- ffmpeg.wasm package/core version and asset hosting path are decided.
- `SharedArrayBuffer` / COOP / COEP requirements are proven only if
  multi-thread mode is selected.

## 7. Sources

- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- https://ffmpegwasm.netlify.app/docs/overview/
- https://ffmpegwasm.netlify.app/docs/getting-started/usage/
- https://ffmpegwasm.netlify.app/docs/api/ffmpeg/classes/ffmpeg/
- https://ffmpegwasm.netlify.app/docs/migration/
- https://ffmpegwasm.netlify.app/docs/faq/
- https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer
- https://www.npmjs.com/package/@ffmpeg/ffmpeg
- https://www.npmjs.com/package/@ffmpeg/core
- https://www.npmjs.com/package/@ffmpeg/core-mt

## 8. Status

Research complete for integration planning. External STT/upload context was
inspected, but browser ffmpeg preprocessing remains unproven. Blocked on the
actual browser ffmpeg workflow artifact, a replacement preprocessing contract
or browser smoke proof.
