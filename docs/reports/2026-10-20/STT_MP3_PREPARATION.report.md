# Native MP3 preparation, 20 October 2026

Status: implementation, offline qualification and production functional
acceptance passed. The quality boundary below remains explicit.

## Outcome and scope

Large MP3 uploads previously bypassed preparation. A 121,057,465-byte recording
was accepted as uploaded, then rejected by the STT service's 104,857,600-byte
limit. The Filter incorrectly presented this size rejection as a format error.

The change sends MP3 through the existing Event Function and media preparation
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
| R6: ordinary-user acceptance | Separate ordinary-user chat; real source upload/Send; full transcript after reload; source-to-prepared fidelity and timestamp coverage; cached regeneration with no new STT. Passed within the stated quality boundary. |

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

## Production release and ordinary-user acceptance

Source commit `17a373fe0826965d55658fcfe4559e6d1f9f326a` passed
[exact-head Active CI](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/39411567919)
before deployment. At 11:06:14 UTC the two Functions were installed through the
native API after confirming no active chat tasks or pending media. The Event
was disabled, updated and enabled to stop its previous reconciler. Owner,
activation/global state and Valves were preserved. Installed LF source hashes:

- Event v0.1.3: `f770078b4749bb502057d9263a84fa94a7857634211e4f4e14bff7df2b499a1a`.
- Filter v0.2.7: `77ee57800ef2b92cea5dacf374047ea3bf8fe944ec82c7cecfcc1a61485be588`.

An isolated browser context signed in through the native password form as a
normal user. The actual 121,057,465-byte source was selected through the file
input. One Enter queued the message while preparation ran; OpenWebUI sent it
automatically once ready. The same native File became the 24,175,052-byte
prepared MP3 in one attempt; its SHA matched the rehearsal exactly.

One Lemonfox STT job completed with 43,671 transcript characters and 577 segments.
The result reports 3,021.744 seconds and its last segment ends at 3,021.14 seconds.
The complete saved display (47,920 characters) was present exactly once in both
native message content and structured output. Its heading and rendered text
remained visible after a real page reload. Native **Regenerate → Try again**
produced the second completed answer from the same File/cache, again surviving
reload. Independent DB/disk/artifact/log checks confirmed one preparation call,
one STT job and one transcript artifact, with unchanged File timestamp, bytes,
transcript and display checksums after regeneration.

Both primary requests selected the ordinary existing Gemini model, with
`max_tokens=512`, minimal reasoning, legacy function calling and no selected
tools/search or background title/tag/follow-up tasks. No paid STT retry ran.
The operator approved a USD 1 budget. Duration-based STT cost is approximately
USD 0.139896 at the [published tariff](https://www.lemonfox.ai/apis/speech-to-text).
Both native model usage fields are null and the gateway log has no token/cost
receipt; actual total provider billing is not established.

The original chat and both original uploads retain their timestamps and byte
hashes. WebUI/STT retain their original container/image IDs, healthy state and
zero restarts; OOMKilled is false. No service restart, new image, publication or
core change was needed. The native-source rollback backup remains private;
rollback restores Functions without restoring old DB/files.

The temporary ordinary-user browser context was closed after acceptance. Its
account was moved to pending and all sessions revoked; the previous session
receives HTTP 401. The private test chat and native File remain available to
the administrator for review, with their existing owner retained. Credentials
were cleared from the test controller.

Quality boundary: full decoded sample count and 303 non-silent 10-second windows
were compared against the source; minimum/median waveform correlation is
0.999141/0.999704. This and the first/last transcript timestamps support sound
preservation and temporal coverage. Independent word-for-word semantic accuracy
of the entire recording was not established by listening. The existing damaged
source frame remains an input limitation; no stronger accuracy claim is made.

See the [native media runbook](../../stage2/operations/STT_NATIVE_MEDIA_TRANSCRIPTION_RUNBOOK.md).
