# STT Native Media Transcription Runbook

Status: production workflow as of 2026-09-25. This page is the operational
source of truth for uploaded audio and video in ordinary chats.

## User workflow

1. Select an ordinary OpenWebUI chat model and attach an audio or video file.
2. Audio remains an audio attachment. A video starts server-side conversion to
   MP3 immediately after upload, before **Send**. The attachment changes to an
   audio file when conversion and source cleanup finish.
3. Press **Send**. If conversion is still running, the UI says
   `Подготавливаем аудио. Сообщение отправится автоматически.` and sends the
   draft when the audio attachment is ready. The user need not press Send again.
4. The native STT Filter transcribes the audio through `stage2-stt` and Lemonfox.
   The assistant returns a short summary and the formatted full transcript.

The upload is not a transcription request: transcription begins on Send. The
microphone/dictation route is separate from uploaded-media STT. There is no
separate Transcribe button or browser ffmpeg.wasm conversion in this route.

Large uploads pass through the Traefik `websecure` entrypoint. Its request-body
read timeout is set to 30 minutes in `compose/openwebui.compose.yml`; the
Traefik default of 60 seconds cut off a 772 MB WebM before OpenWebUI received
the complete file. If an upload fails, check the browser's `/api/v1/files/`
response and Traefik timing before investigating FFmpeg or STT. A gateway
`502`/`504` with a non-JSON body is an upload failure, not an STT response.
If the File is already MP3 on the server but the composer still shows WebM,
check whether the browser loaded old cached `C7Lxt8YS.js` or `B56SVFjv.js`.
Refresh with Ctrl+Shift+R before repeating the UI check; Ctrl+R can reuse
those cached assets.

## Video lifecycle

- OpenWebUI owns the native File row, attachment and chat. The upload hook
  starts preparation; the sidecar uses server-side FFmpeg to extract the first
  audio stream into MP3. File content is transferred in chunks and the result
  is written to disk rather than loaded in full into application memory.
- On success, the **same File ID** changes to `audio/mpeg` with an MP3 path and
  metadata. The original video blob is deleted before the File is marked
  `completed`. The prepared audio stays available even if a later STT provider
  request fails.
- On a conversion error, attempt 2 starts immediately. Attempt 3 becomes due
  420 seconds (7 minutes) after attempt 2; the reconciler checks pending work
  every 60 seconds. After a third failure, the source video is deleted, the
  File path is cleared, and the File is marked `failed`. The UI shows an error
  and does not send the failed attachment.
- Attempt and cleanup state live in File metadata so a restart can resume the
  delayed attempt or finish deletion. Pending cleanup is retried until the
  video blob is gone. A conversion success is complete only after deletion.
- Existing linked video attachments were migrated to audio; unreferenced and
  failed legacy videos were removed during the 2026-09-25 rollout. New video
  retention is not part of the product workflow.

## Operator checks

From `/opt/openwebui-prd0` on the VPS:

```text
docker compose --env-file .env -f compose/openwebui.compose.yml ps openwebui stage2-stt
docker compose --env-file .env -f compose/openwebui.compose.yml logs --since 15m openwebui stage2-stt
```

Verify the user route through `https://gpt.alpha-soft.ru/` with an ordinary
account: attach a small video with speech, observe MP3 replacement before
Send, then send and check the transcript. Repeat with a long enough video to
observe the waiting notice. A no-audio video must fail after three attempts,
leave no video blob and produce no STT job. Remove verification uploads and
chats after checking. A healthy `/health` response alone does not prove this
workflow.

For a failed provider call, inspect the sidecar error separately from video
preparation. The prepared audio remains the user attachment and can be sent
again. Do not restore the source video as a recovery step. Check disk space,
container memory and swap before a large-media investigation. Never print
provider keys, internal tokens, authorization headers, or raw provider payloads.
