# Native MP3 preparation candidate, 20 October 2026

Status: implementation and offline qualification; ordinary-user paid STT and
production release are not accepted by this report.

## Outcome and scope

Large MP3 uploads previously bypassed preparation. A 121,057,465-byte recording
was accepted as uploaded, then rejected by the STT service's 104,857,600-byte
limit. The Filter incorrectly presented this size rejection as a format error.

The candidate sends MP3 through the existing Event Function and media preparation
endpoint before Send. OpenWebUI remains the sole native File/Storage owner;
the STT service retains FFmpeg, byte-limit validation and provider ownership.
No URL publication, calculator, new service, storage backend or core patch is
introduced. Prepared files and saved transcripts are reused without preparing
the same File again. Existing legacy MP3 files are not bulk migrated.

## Contracts and bounded implementation

| Requirement | Owner and observable result |
| --- | --- |
| R1: prepare MP3 | Event v0.1.3 uses existing `/media/prepare`, mono/16 kHz/64 kbit/s MP3 profile. |
| R2: preserve native identity | Separate output blob; same File ID and display name; native path/hash/size commit before deleting the source. |
| R3: preserve failures and recovery | Existing retry/reconciler owner; third preparation failure keeps original path/bytes with native failed status. |
| R4: avoid repeated work | Durable preparation marker or saved transcript prevents repeat preparation; Filter's transcript cache remains unchanged. |
| R5: exact error meaning | Filter v0.2.7 maps both size-rejection codes to the same safe explanation in UI events and LLM context; no raw provider payload. |
| R6: ordinary-user acceptance | Separate test chat, actual upload/Send, complete transcript after reload, source comparison and cached reuse with no new STT. Pending. |

Implementation was split between intake and error-semantics agents. A separate
native-runtime harness exercises actual candidate Function source, native File
SQLite sessions and LocalStorage in the exact deployed WebUI image, with only
the HTTP preparation boundary replaced. The installed-STT harness independently
uses real FFmpeg for MP4, M4A and stereo 320 kbit/s MP3. These checks complement
each other; neither substitutes for R6.

Local STT behavior tests: **153 passed**. Both offline runtime checks passed,
including native same-ID replacement, collision handling, repeated-event no-op,
three preparation failures preserving the source, cached transcript reuse and
Event reconciler enable/disable. The HTTP fixture makes two successful calls
and three deliberate failures; it makes no external calls.

Verified unchanged deployment image identities:

- WebUI: `sha256:a0f5752afafd24ae065190ef28d88717e9a29c739ccb23be1e2d3e7ff7bfe424`.
- STT: `sha256:ead2a4df9ea157ba1ee2f402c2363b76851dfc1f4609339d7de25dbb7a0a70b8`.

## Representative recording rehearsal, no paid provider calls

The existing production media preparation endpoint converted the unchanged
source recording to 24,175,052 bytes in 54.363 seconds. Output SHA-256:
`28c20c85612800f529c32b280d3255fb5e2588a1f234e21be181c4c1204d4d03`.
The native source File and original chat were not modified.

The source reports 3,026.436625 seconds in its MP3 metadata but contains a damaged
frame (`Header missing`) near the end. Full tolerant source decoding and strict
prepared decoding both yield 48,347,904 mono samples at 16 kHz (3,021.744 seconds).
The prepared file passes full strict decoding. Three 15-second windows at 15,
1,500 and 2,990 seconds have waveform correlations 0.999753, 0.999861 and
0.999691. This establishes matching decoded duration and strong acoustic
similarity in those windows, not transcript accuracy or absence of defects in
the original recording.

## Release and remaining acceptance

Only the two native Functions need installation; service images and core are
unchanged. Preserve their current source, Valves and activation. With no pending
media, disable the Event through the native API, update it, and enable it so
the previous reconciler stops and the candidate reconciler starts. Filter source
is updated through the same API. Rollback restores Function source and settings,
preserving new chats/files; it does not restore an old database.

Final acceptance still requires an authorized paid ordinary-user run and source
comparison of the transcript, reload and cached reuse. A healthy container,
offline tests or successful media preparation alone do not close this GOAL.

See the [native media runbook](../../stage2/operations/STT_NATIVE_MEDIA_TRANSCRIPTION_RUNBOOK.md).
