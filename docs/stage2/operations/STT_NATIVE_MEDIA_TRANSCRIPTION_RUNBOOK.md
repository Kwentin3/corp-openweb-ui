# STT Native Media Transcription Runbook

Status: native media workflow source contract. Verify the deployed image before
using these steps as production acceptance evidence.

## User workflow

1. Select an ordinary OpenWebUI chat model and attach an audio or video file.
2. MP3 remains an audio attachment. Other recognized audio and video files start
   server-side conversion to MP3 immediately after upload, before **Send**.
   The attachment becomes MP3 when conversion and source cleanup finish.
3. Press **Send**. If conversion is still running, the UI says
   `Подготавливаем аудио. Сообщение отправится автоматически.` and sends the
   draft when the audio attachment is ready. The user need not press Send again.
4. The native STT Filter transcribes the audio through `stage2-stt` and Lemonfox.
   The assistant returns a short summary and the formatted full transcript.

The upload is not a transcription request: transcription begins on Send. The
microphone/dictation route is separate from uploaded-media STT. There is no
separate Transcribe button or browser ffmpeg.wasm conversion in this route.
The upload hook recognizes audio and video MIME types, plus known media
extensions when the MIME type is generic. During preparation, FFmpeg verifies
that the source has an audio stream; a filename or MIME type alone does not
qualify it. MP3 is marked `completed` directly; other recognized media is
prepared as MP3 under the same native File ID. OpenWebUI's upload-time
transcription and text indexing are bypassed. The chat STT Filter processes
the completed MP3 after Send,
including long recordings.

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

Production checks on 2026-09-25 covered four short MP4 files through video
upload, MP3 replacement, Send and STT; one 809,586,557-byte WebM through
upload, MP3 replacement and source deletion; and a separately uploaded
29,705,228-byte MP3 through Send and STT. The long transcript reached the end
of the 61-minute-53-second recording. A single-chat end-to-end replay of that
exact large WebM through STT was not performed.

## Media preparation lifecycle

- OpenWebUI owns the native File row, attachment and chat. The upload hook
  starts preparation for video and non-MP3 audio; the sidecar uses server-side
  FFmpeg to extract the first audio stream into MP3. File content is transferred
  in chunks and the result is written to disk rather than loaded in full into
  application memory.
- On success, the **same File ID** changes to `audio/mpeg` with an MP3 path and
  metadata. The original media blob is deleted before the File is marked
  `completed`. The prepared audio stays available even if a later STT provider
  request fails.
- On a conversion error, attempt 2 starts immediately. Attempt 3 becomes due
  420 seconds (7 minutes) after attempt 2; the reconciler checks pending work
  every 60 seconds. After a third failure, the source media is deleted, the
  File path is cleared, and the File is marked `failed`. The UI shows an error
  and does not send the failed attachment.
- Attempt and cleanup state live in File metadata so a restart can resume the
  delayed attempt or finish deletion. Pending cleanup is retried until the
  source blob is gone. A conversion success is complete only after deletion.
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
account: attach a small M4A and a small video with speech in separate chats,
observe MP3 replacement before Send, then send and check each transcript.
Repeat with a long enough recording to observe the waiting notice. A no-audio
video must fail after three attempts, leave no video blob and produce no STT
job. Remove verification uploads and chats after checking. A healthy `/health`
response alone does not prove this workflow.

For a failed provider call, inspect the sidecar error separately from media
preparation. The prepared audio remains the user attachment and can be sent
again. Do not restore the source media as a recovery step. Check disk space,
container memory and swap before a large-media investigation. Never print
provider keys, internal tokens, authorization headers, or raw provider payloads.

## Memory limits

The 2026-09-25 production host has 8 GB nominal RAM and 2 GiB swap.
OpenWebUI has a 3 GiB RAM limit and a 4 GiB combined RAM-plus-swap limit;
`stage2-stt` remains at 768 MiB RAM and 1 GiB combined. The source defaults
are in `compose/openwebui.compose.yml`. The live Compose file under
`/opt/openwebui-prd0` and the running Docker cgroup must agree: editing only
the source file or only the running container is not a durable change.

Check `free -h`, `docker stats --no-stream openwebui stage2-stt`, Docker's
effective memory limits, and `memory.events` before attributing an upload
failure to OOM. The 3 GiB change was applied with `docker update` without
restarting OpenWebUI, then recorded in the live Compose file. At verification,
OpenWebUI remained healthy with no OOM event or restart and public `/health`
returned HTTP 200. These checks describe that point in time; a fresh upload
failure still needs its own logs and resource samples.
