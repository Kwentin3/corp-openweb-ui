# STT Native Media Transcription Runbook

Status: production workflow as of 2026-09-16.

## User workflow

1. Select any ordinary OpenWebUI chat model.
2. Attach audio or video and use the native **Send** button.
3. Receive one assistant message containing a short summary and a formatted
   full transcript.
4. Use the native suggestions below the message, or a user-managed Prompt via
   slash command, for follow-up work.

No separate transcription button, custom panel, or browser-side media
normalization is part of this workflow.

## Ownership and lifecycle

- OpenWebUI owns the chat, source attachment, derived audio File, transcript
  message, native suggestions, and Prompt management.
- `stage2-stt` owns provider handoff and, for video, temporary server-side
  extraction of its first audio stream with ffmpeg.
- Lemonfox is the external STT provider behind the sidecar adapter.
- For a successful video transcription, the transaction persists the derived
  OpenWebUI audio File and replaces the source attachment; only then is the
  original File/blob removed.
- If preparation, provider handoff, or persistence fails, the source video is
  retained. Never remove it as a failure cleanup step.

## Operator checks

From the production compose directory:

```text
docker compose --env-file .env -f compose/openwebui.compose.yml ps openwebui stage2-stt
docker compose --env-file .env -f compose/openwebui.compose.yml logs --since 15m stage2-stt
```

Expected result: both services are healthy/running and there are no new
tracebacks during a representative user upload.

For product verification, use an ordinary user account and a small video with
speech. After the assistant response finishes, reopen the chat once: the
OpenWebUI client may retain the original attachment card in its in-memory view,
while the persisted chat correctly contains `transcription-audio.mp3`.

## Safe recovery

- Provider `502` or other upstream failure: keep the attachment and ask the
  user to retry later. Do not classify it as a video lifecycle failure without
  sidecar evidence.
- `source_has_no_audio_stream`: explain that the uploaded video has no audio;
  retain the source attachment.
- A sidecar code change requires rebuilding only `stage2-stt`. An OpenWebUI
  restart is needed only when changing the Filter content or its narrow media
  lifecycle overlay.

Never print provider keys, internal tokens, authorization headers, or raw
provider payloads in tickets or logs.
