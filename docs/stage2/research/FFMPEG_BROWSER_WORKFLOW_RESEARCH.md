# FFMPEG Browser Workflow Research

## 1. Question

How should the existing browser ffmpeg workflow be embedded into the OpenWebUI contour?

## 2. Research status

Status: researched from ffmpeg.wasm official docs on 2026-06-18 and updated
after external artifact/operator proof input on 2026-06-18.

Result type: integration boundary. The browser ffmpeg source code is not copied
into this repo, but the external workflow contract is now inspected and
transferable for ADR review.

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
- External workflow inspection confirms the transferable browser-side
  preprocessing contract: `@ffmpeg/ffmpeg` v0.12.6, audio/video input, command
  `ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`, output MP3 /
  `audio/mpeg` as a browser `Blob`, then presigned/internal upload to backend
  STT orchestration.
- Operator manual proof reports success on a mobile device with large videos and
  large WAV files. This should be treated as useful manual evidence, not as a
  reproducible proof matrix.

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
- prepared audio format accepted by Lemonfox or selected STT proxy.
- browser workflow output contract matches the backend proxy input contract.
- ffmpeg.wasm package/core version and asset hosting path are decided.
- source CDN use through `unpkg.com` is replaced, accepted or rejected for
  production.
- operator mobile/large-file proof is converted into a reproducible matrix with
  device/browser/file metadata.
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

Research complete for integration planning. External browser ffmpeg workflow
contract is inspected and transferable. ADR-0004 can use MP3 / `audio/mpeg` as
the source contract for review, while implementation acceptance still requires a
reproducible proof matrix and production dependency decisions.
