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

There are three implementation owners. The approved four-file OpenWebUI 0.11.4
exception adds our `accept_upload` handoff, bounded local upload write/hash and
native attachment metadata/error refresh. `accept_upload` is a custom hook
added by that diff, not an existing unmodified upstream contract; the patch
performs neither FFmpeg conversion nor Lemonfox calls.
`stage2_media_intake` is an Event Function running **inside OpenWebUI**, using
its internal File models and Storage API to own preparation, same-ID replacement,
cleanup and restart recovery. FFmpeg runs in the existing `stage2-stt` service.
After Send, `stage2_audio_context_filter` obtains the transcript from that
service/Lemonfox or reuses the stored transcript, removes the processed audio
from outbound file collections and gives the ordinary chat model text.
The MP3 remains the native user attachment. A later model failure must preserve
both that attachment and the saved transcript. Meeting protocol remains a
separate ordinary Prompt; the model's summary does not replace the transcript.

Filter v0.2.5 removes the obsolete second conversion/lifecycle path that depended
on absent `open_webui.services.stage2_media_lifecycle` modules. Intake remains
the only preparation owner. Ready MP3/WAV/Opus can be transcribed; a bypassed
unprepared MP4/M4A receives `Подготовка медиа не завершена` without preparation,
replacement or STT calls from the Filter. Cached transcripts remain reusable.
Native `metadata.task` auxiliary requests leave attachments and transcript
metadata untouched. Filter v0.2.5 passed an ordinary-user staging upload/Send/reload
check with one STT job and one primary model request. The current production
deployment remains v0.2.4 until this follow-up release is approved and installed;
artifact identities and narrow rollback are in the follow-up section of the
existing backup/upgrade runbook.

Implementation entry points are the
[reviewed upload diff](../../../deploy/openwebui-patches/media-upload-v0.11.4/proposed.patch),
[Event Function](../../../deploy/openwebui-functions/stage2_media_intake.py)
(`accept_upload`, preparation/replacement and cleanup using native Storage),
[post-Send Filter](../../../services/stage2-stt/openwebui_filters/stage2_audio_context_filter.py)
(`inlet`, cached transcript, outbound audio removal and `outlet` display), and
[Lemonfox adapter](../../../services/stage2-stt/stage2_stt/lemonfox.py).
The Filter uploads the prepared MP3 plus its envelope to
`stage2-stt`'s `/stage2-api/transcription/jobs`; the adapter sends multipart
`file` to Lemonfox `/v1/audio/transcriptions`. The ordinary LLM receives the
resulting text through the separate native chat-model connection. Native File
Storage owns the persistent MP3; the Filter stores its transcript/cache marker
in that File's data. The qualified reload/recreation checks are linked below.

The exception, pinned source/build identity, approvals, qualification and rollback
are described in the existing
[backup/upgrade runbook](../../ops/BACKUP_RESTORE_RUNBOOK.md#issue-474-media-component-and-approved-staging-bridge).
This is a conscious core exception. Each future upgrade must first look for a
native replacement, then qualify necessity, compatibility and the reproducible
custom build if the exception remains. The current image is not an unmodified
official image, and the extension's separate source file does not make its
internal OpenWebUI dependencies an independent runtime.

For #474 on 2026-10-05, a native browser regeneration in a fork of the accepted
short MP4 chat reused its cached transcript. A temporary credential-free
loopback receiver captured the **actual HTTP JSON from the installed native
OpenAI client**, rather than the browser's pre-Filter Send body. The request to
`/v1/chat/completions` selected `gpt-5.4-mini`, contained one user message with
string content including the complete transcript, and contained no media/file
payload, media URL or data/base64 encoding. The receiver intentionally returned
HTTP503 and forwarded nothing: zero external model/STT calls, no new model
answer acceptance. This checks current cached-route egress; it is not a wire
capture of the previously accepted paid M4A/MP4 calls. Configuration was restored
and the MP3/cache preserved. See the linked runbook for identity, evidence and
remaining acceptance boundaries. Do not repeat the accepted STT cases merely
to produce another report.

The audio-context Filter 0.2.4 retains the summary and full transcript in both
the legacy message `content` and native structured `output`. OpenWebUI 0.11.4
renders structured output first; updating only `content` leaves the transcript
saved but invisible. The Filter wraps the existing assistant text parts without
changing their IDs, annotations, tool traces or reasoning. Changed containers
are copied so the native outlet detects and persists the update. Check the full
transcript in the browser immediately after the response and again after reload;
an administrative chat response containing it is insufficient evidence.

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
