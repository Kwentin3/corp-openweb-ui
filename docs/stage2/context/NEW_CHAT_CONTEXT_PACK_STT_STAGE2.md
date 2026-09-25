# Stage 2 STT: context for a new work session

Updated 2026-09-25. Start with the [current runbook](../operations/STT_NATIVE_MEDIA_TRANSCRIPTION_RUNBOOK.md)
and [media input contract](../contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md).
The June 2026 browser ffmpeg.wasm/Transcribe Action reports describe a previous
implementation and must not be used as the current acceptance route.

## Accepted user route

```text
Attach video -> native upload -> server FFmpeg converts to MP3
             -> same OpenWebUI File ID points to audio -> video blob deleted
             -> Send -> native STT Filter -> stage2-stt/Lemonfox -> transcript
```

Conversion starts on attachment, without Send. While it runs, Send shows a
waiting notice and sends the draft automatically when the MP3 is ready.
Uploaded audio goes directly to the native STT Filter on Send. Dictation from
the microphone is a separate OpenWebUI route. The user's ordinary model
remains selected; there is no dedicated STT model or Transcribe button.

Video is never a durable chat artifact. Conversion makes up to three attempts:
two immediate, then a last one due 420 seconds after the second failure.
After the last failure, delete the source video, mark the File failed and stop
the pending Send. A reconciler resumes pending attempts or cleanup after a
restart. Provider STT failure occurs later and leaves the prepared MP3
available for retry.

## Owners and code pointers

- OpenWebUI native File/chat/upload lifecycle:
  `deploy/openwebui-media-lifecycle/stage2_video_intake.py` and the pinned
  upload integration in `deploy/openwebui-patches/`.
- Composer waiting notice, auto-send and attachment label:
  `deploy/openwebui-patches/apply_stage2_video_composer_patch.py`.
- Server preparation and STT endpoints: `services/stage2-stt/`.
- Ordinary chat transcription Filter:
  `services/stage2-stt/openwebui_filters/stage2_audio_context_filter.py`.
- Production Compose: `compose/openwebui.compose.yml`; live source:
  `/opt/openwebui-prd0`; public product:
  `https://gpt.alpha-soft.ru/`.

Keep secrets in the server environment. File transfer uses disk-backed
streaming; avoid whole-file reads into Python or browser memory. Preserve
OpenWebUI's File ownership and the same File ID when replacing video with
audio. Do not restore a video on provider error.

## Acceptance and operational state

The 2026-09-25 rollout converted seven linked legacy videos, removed two
failed and seven orphan/dangling video records, and verified zero remaining
video File rows and unreferenced video blobs at that audit point. Production
domain smoke produced a transcript and removed its test upload. These are
dated observations, not a guarantee about future uploads.

The 2026-09-25 large-media recheck uploaded an 809,586,557-byte WebM through
the public domain, converted it to a 29,705,228-byte MP3 and removed the video
blob. Four short MP4 files from the project root completed the browser
video-to-MP3-to-STT route. A 61-minute MP3 generated with the same server
FFmpeg profile produced 308 transcript intervals through `1:01:53`. The
large video's conversion and its long-audio STT were verified in separate
runs; an exact single-chat large-video-to-STT replay remains unverified.
Direct audio uploads now skip OpenWebUI's upload-time transcription and reach
the native STT Filter on Send. Production image:
`corp-openwebui/openwebui:media-intake-audio-release-20260925`.
The public upload timeout is 30 minutes. The running OpenWebUI container has
3 GiB RAM and 4 GiB combined RAM-plus-swap limits; the VPS has 2 GiB swap.
The source Compose defaults and deployed Compose file both carry the 3 GiB
RAM limit. Check effective Docker limits after any future deployment.

Before calling a new change accepted, verify an ordinary authenticated user
at the public domain: audio upload and transcript; video-to-MP3 replacement
before Send; Send during long conversion with waiting notice and eventual
transcript; final no-audio conversion failure with source deletion; chat
reload and File metadata consistency. Check container health, resource use,
video remnants and cleanup of test artifacts. Do not substitute an isolated
localhost test or an unauthenticated health request for this product route.

The current work is in [PR #523](https://github.com/Kwentin3/corp-openweb-ui/pull/523)
on `agent/media-lifecycle-prod-20260925`. Its initial video upload change is
`2364f901`; later changes `74a8a1c7` and `183f7d70` fixed large upload and
direct-audio behavior, and `e0536253` raised the OpenWebUI memory limit.
Verify deployed image and source identity before future changes; another agent
may be working in the original workspace. Historical reports under
`docs/reports/2026-06-19/` and older planning documents remain dated evidence
only.
