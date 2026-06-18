# FFMPEG WASM Workflow Inspection Report

Date: 2026-06-18

Scope: transferred source-inspection facts for the external browser-side
ffmpeg workflow used as ADR-0004 input.

## 1. Summary

The external browser-side ffmpeg workflow exists and has an inspectable,
transferable preprocessing contract.

This report records facts supplied for ADR-0004 refinement. It does not copy
source code, media files, wasm/core binaries, provider credentials or `.env`
content into this repository.

## 2. Workflow Contract

Browser input:

- accepts `audio/*`;
- accepts `video/*`;
- source project UI limit: 1 GB;
- confirmed source formats:
  - MP3;
  - WAV;
  - M4A;
  - WebM;
  - MP4 video;
  - MOV video.

ffmpeg package:

- `@ffmpeg/ffmpeg` v0.12.6.

Transformation:

```bash
ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3
```

Output:

- container: MP3;
- codec: `libmp3lame`;
- MIME: `audio/mpeg`;
- browser output: `Blob`.

Handoff:

- browser prepares audio locally;
- browser uploads prepared audio through a presigned/internal-storage path;
- backend STT orchestration continues by object key.

## 3. Security Boundary

Confirmed boundary:

- API keys do not go to the browser;
- browser does not call STT provider directly;
- backend/STT proxy owns provider keys, validation, policy, usage and
  retention.

This matches ADR-0004's required server-side STT proxy boundary.

## 4. Asset Hosting

The source workflow uses CDN-hosted ffmpeg assets through `unpkg.com`.

Production implication:

- public CDN dependency must not be accepted silently;
- Stage 2 should prefer self-hosted or internally cached ffmpeg core assets;
- exact versions must be pinned;
- asset hosting path, cache headers, rollback and license notices must be
  documented before implementation acceptance.

## 5. Operator Manual Proof

Operator reported manual testing:

- workflow was tested on a mobile device;
- large videos were tested;
- large WAV files were tested;
- result: workflow worked correctly in the tested cases.

Engineering interpretation:

- this is useful operator evidence;
- it is not automated repository proof;
- it does not prove universal mobile support;
- it does not prove all file sizes or all files are supported;
- Stage 2 acceptance should capture a reproducible proof matrix.

## 6. Reproducible Proof Matrix Needed

| Test case | Device | Browser | File type | File size | Duration | Output format | Result | Evidence |
| --------- | ------ | ------- | --------- | --------: | -------: | ------------- | ------ | -------- |
| Mobile large video | operator reported | operator reported | video | TBD | TBD | MP3 / `audio/mpeg` | operator reported pass | TBD |
| Mobile large WAV | operator reported | operator reported | WAV | TBD | TBD | MP3 / `audio/mpeg` | operator reported pass | TBD |
| Desktop baseline audio | TBD | TBD | MP3/WAV/M4A/WebM | TBD | TBD | MP3 / `audio/mpeg` | TBD | TBD |
| Desktop baseline video | TBD | TBD | MP4/MOV | TBD | TBD | MP3 / `audio/mpeg` | TBD | TBD |

## 7. Production Decisions Still Needed

- prepared-audio output format: source-proven MP3 / `audio/mpeg` vs
  `audio/webm;codecs=opus`, `audio/ogg;codecs=opus` or `audio/wav`;
- MP3 / `libmp3lame` licensing and ops review;
- CDN vs self-host/internal cache for ffmpeg assets;
- exact package/core versions;
- single-thread vs multi-thread;
- max accepted file size;
- max accepted duration;
- fallback behavior;
- typed errors for unsupported/too-large files.

## 8. Status

`external ffmpeg workflow artifact inspected`

`transferable browser-side preprocessing contract found`

`operator manual proof exists for reported mobile/large-file scenarios`

Implementation acceptance still requires ADR approval, reproducible proof matrix
and production dependency decisions.
