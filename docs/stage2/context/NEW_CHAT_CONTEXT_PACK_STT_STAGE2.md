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

Before calling a new change accepted, verify an ordinary authenticated user
at the public domain: audio upload and transcript; video-to-MP3 replacement
before Send; Send during long conversion with waiting notice and eventual
transcript; final no-audio conversion failure with source deletion; chat
reload and File metadata consistency. Check container health, resource use,
video remnants and cleanup of test artifacts. Do not substitute an isolated
localhost test or an unauthenticated health request for this product route.

The current working implementation was committed as `2364f901` on
`agent/media-lifecycle-prod-20260925`. Verify the deployed image/source
identity before future changes; another agent may be working in the original
workspace. Historical reports under `docs/reports/2026-06-19/` and older
planning documents remain dated evidence only.
