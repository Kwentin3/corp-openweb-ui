# OpenWebUI ADR-0004 FFMPEG Operator Proof Update Report

Date: 2026-06-18

Scope: ADR-0004 STT proxy boundary update after external ffmpeg workflow
contract inspection and operator manual proof for mobile/large-file cases.

## 1. Summary

ADR-0004 was updated from "missing ffmpeg artifact" to a more precise status:

- external ffmpeg workflow artifact inspected;
- transferable browser-side preprocessing contract found;
- operator manual proof exists for reported mobile and large-file scenarios;
- implementation still requires ADR approval, reproducible proof matrix and
  production dependency decisions.

ADR-0004 remains `Status: Proposed`.

No production implementation was started.

## 2. New Input

New source-inspection facts:

- browser-side ffmpeg workflow exists;
- source uses `@ffmpeg/ffmpeg` v0.12.6;
- output contract is MP3 / `audio/mpeg`;
- command is
  `ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3`;
- backend STT/upload pipeline exists;
- API keys do not go to the browser;
- handoff pattern is browser -> prepared audio blob -> presigned/internal
  upload -> backend STT orchestration;
- source workflow uses CDN-hosted ffmpeg assets through `unpkg.com`.

New operator input:

- operator manually tested the workflow on a mobile device;
- large videos were tested;
- large WAV files were tested;
- operator reported correct workflow behavior in those cases.

## 3. Artifact Status Update

Previous status:

- actual browser ffmpeg preprocessing artifact was not found in this repo;
- implementation readiness waited for browser ffmpeg preprocessing evidence.

Updated status:

- missing-artifact blocker is removed;
- source workflow contract is inspected and transferable;
- MP3 / `audio/mpeg` is the source-proven prepared-audio output;
- operator manual proof exists for reported mobile and large-file cases;
- implementation acceptance still requires a reproducible proof matrix and
  production dependency decisions.

## 4. Operator Manual Proof

Operator proof is recorded as manual evidence:

| Test case | Device | Browser | File type | File size | Duration | Output format | Result | Evidence |
| --------- | ------ | ------- | --------- | --------: | -------: | ------------- | ------ | -------- |
| Mobile large video | operator reported | operator reported | video | TBD | TBD | MP3 / `audio/mpeg` | operator reported pass | TBD |
| Mobile large WAV | operator reported | operator reported | WAV | TBD | TBD | MP3 / `audio/mpeg` | operator reported pass | TBD |

This proof should not be described as:

- automated repository proof;
- universal mobile support;
- all-file support;
- production readiness.

Correct wording:

`Mobile and large-file behavior has operator manual proof, but Stage 2
acceptance should still capture a reproducible proof matrix with
device/browser/file metadata.`

## 5. Contract Now Considered Transferable

Browser input:

- `audio/*`;
- `video/*`;
- source project UI limit: 1 GB;
- source-confirmed formats: MP3, WAV, M4A, WebM, MP4 video and MOV video.

Transformation:

```bash
ffmpeg -i input.media -vn -c:a libmp3lame -q:a 2 output.mp3
```

Output:

- MP3 container;
- `libmp3lame` codec;
- `audio/mpeg` MIME;
- browser `Blob`;
- upload by presigned/internal-storage path;
- backend STT orchestration by object key.

Security:

- no API keys in browser;
- browser does not call STT provider;
- STT proxy remains the backend boundary for provider keys, validation, policy,
  usage and retention.

## 6. Remaining Production Decisions

Output format:

- MP3 / `audio/mpeg` is source-proven, but not automatically final for
  production;
- alternatives remain `audio/webm;codecs=opus`, `audio/ogg;codecs=opus` and
  `audio/wav` if size is acceptable.

Asset hosting:

- source workflow uses `unpkg.com`;
- corporate production should prefer self-hosted or internally cached assets;
- exact versions, asset path, cache headers and rollback must be documented.

Licensing/ops:

- MP3 / `libmp3lame` needs licensing/ops review;
- ffmpeg core assets need license notices if self-hosted;
- heavy wasm/core binaries and full FFmpeg source were not vendored.

Runtime limits:

- define max accepted file size;
- define max accepted duration;
- define fallback behavior;
- define typed errors for unsupported/too-large files.

Threading:

- first implementation path remains single-thread unless ADR approves
  multi-thread;
- multi-thread requires `SharedArrayBuffer`, COOP/COEP, Traefik/header review
  and OpenWebUI embedding impact review.

## 7. ADR-0004 Changes

ADR-0004 was updated to:

- preserve `Status: Proposed`;
- remove the previous `missing ffmpeg artifact` blocker;
- record inspected external ffmpeg workflow artifact;
- record MP3 / `audio/mpeg` transferable contract;
- record operator manual proof for reported mobile/large-file scenarios;
- keep direct browser-to-provider rejected;
- keep provider API keys server-side only;
- preserve production caveats for output format, CDN/self-hosting, licensing and
  file limits;
- require reproducible proof matrix before implementation acceptance.

## 8. Related Docs Updated

Updated:

- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`;
- `docs/stage2/research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md`;
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`;
- `docs/stage2/CONTRACT_BOUNDARIES.md`;
- `docs/stage2/IMPLEMENTATION_GATES.md`;
- `docs/stage2/ENGINEERING_BACKLOG.md`;
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`;
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`;
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`;
- `docs/stage2/README.md`;
- `docs/stage2/CONTEXT_INDEX.md`;
- `README.md`;
- `docs/reports/2026-06-18/OPENWEBUI_FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.report.md`.

Created:

- `docs/reports/2026-06-18/FFMPEG_WASM_WORKFLOW_INSPECTION.report.md`;
- `docs/reports/2026-06-18/OPENWEBUI_ADR0004_FFMPEG_OPERATOR_PROOF_UPDATE.report.md`.

## 9. Remaining Runtime Proofs

- reproducible proof matrix for mobile large video;
- reproducible proof matrix for mobile large WAV;
- desktop baseline audio proof;
- desktop baseline video proof;
- prepared-audio output proof against Stage 2 proxy input contract;
- Lemonfox or selected STT provider compatibility proof;
- no API key in browser bundle/storage/network proof;
- progress/cancel/retry behavior;
- typed error behavior for unsupported, too-large, timeout, quota and provider
  failures.

## 10. Final Status

`ADR-0004 reviewable with inspected transferable ffmpeg contract; implementation
still requires ADR approval, reproducible proof matrix and production dependency
decisions.`
