# STT Native Media Transcription Runbook

Status: native media workflow source contract. Verify the deployed image before
using these steps as production acceptance evidence.

## User workflow

1. Select an ordinary OpenWebUI chat model and attach an audio or video file.
2. Recognized audio and video files, including MP3, start server-side preparation
   to MP3 immediately after upload, before **Send**.
   The attachment becomes MP3 when conversion and source cleanup finish.
3. Press **Send**. If conversion is still running, the UI says
   `Подготавливаем аудио. Сообщение отправится автоматически.` and sends the
   draft when the audio attachment is ready. The user need not press Send again.
4. The native STT Filter transcribes the audio through `stage2-stt` and Lemonfox.
   The assistant returns a short summary and the formatted full transcript.
   This is always the first stage, including when the upload has a task prompt.
5. Ask questions or give tasks in subsequent messages. The Filter restores the
   same complete timestamped/speaker-labelled File source for the selected branch,
   independently of the selected chat model, without retranscribing old files.

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
both that attachment and the saved transcript. Additional meeting minutes or
action items can be requested in a subsequent message; the first response's
full timed transcript is the source, and the summary does not replace it.

Filter v0.2.5 removes the obsolete second conversion/lifecycle path that depended
on absent `open_webui.services.stage2_media_lifecycle` modules. Intake remains
the only preparation owner. Ready MP3/WAV/Opus can be transcribed; a bypassed
unprepared MP4/M4A receives `Подготовка медиа не завершена` without preparation,
replacement or STT calls from the Filter. Cached transcripts remain reusable.
Native `metadata.task` auxiliary requests leave attachments and transcript
metadata untouched. Filter v0.2.5 passed an ordinary-user staging upload/Send/reload
check with one STT job and one primary model request. The owner-approved production
follow-up then installed v0.2.5 and the qualified pinned STT image on 7 October.
A native public-browser Send with an existing cached MP3 preserved the File bytes/
cache and displayed summary/full transcript after reload, with zero new STT jobs.
Native auxiliary-task settings and Function Valves were preserved; artifact
identities and narrow rollback are in the follow-up section of the
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

## Shared media context, Filter v0.3.0

The accepted 20 October product contract is summary plus full timed transcript
first, user tasks afterwards. It applies through the existing global Filter,
without model-name, user-name or provider-specific branches. All media attachments
of the current message are admitted; aggregated files from other branches are
never an STT trigger. Non-media files retain their native processing.

The saved File's `display_transcript` is the canonical protocol representation
for both display and model input. New results retain every nonempty segment and
its available time boundaries; absent speakers are explicit and are not guessed.
Old `transcribed-v1` caches remain readable. Missing old text is reported and
does not silently trigger paid STT. A transcript is saved before the LLM runs,
so a model failure does not discard it.

For subsequent tasks the Filter reads the authorized selected native branch
through `Chats.get_messages_map_by_chat_id` and `get_message_list`. It restores
each File source once into a clearly delimited data block in the current user
message. The block preserves speakers, timestamps and uncertainty and separates
recorded speech from the user's task. No second store or provider client is added.

The displayed protocol remains in the first persisted answer. Before another
model call, only its exact service-generated suffix, proven against a linked
File in that selected branch, is removed from outgoing assistant history.
Both legacy content and structured text parts are handled; unrelated authored
text, annotations, reasoning, tool output and persisted history are preserved.
Ambiguous matches after compaction are preserved rather than guessed.

OpenWebUI compacts before Filter inlet. The Filter does not rebuild or expand
the compacted conversation; it restores only the complete File source. It does
not truncate the source, invent a per-model context-window matrix or launch a
second summarizer. Provider/context-window rejection remains an explicit error;
there is no guarantee that an arbitrary recording fits every model's window.

The pinned native full-file path was considered: `File.data.content` with
`context=full` avoids RAG, but `capabilities.file_context=false` disables its
automatic injection. The native Sources panel is gated by `citations` and has a
10,000-character preview with an explicit Show all control. Keeping the existing
inline display and global Filter works without relying on either model setting.
See [implementation and acceptance evidence](../../reports/2026-10-20/MEDIA_CONTEXT_GOAL.report.md).

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
qualify it. Event Function v0.1.3 prepares MP3 as well as other recognized media
under the same native File ID, using the existing mono/16 kHz/64 kbit/s MP3
profile. A completed native preparation marker or saved transcript prevents
preparing the same File again. A legacy MP3 marked completed with zero attempts
is prepared when explicitly admitted again; this is not a bulk migration.
OpenWebUI's upload-time
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
  starts preparation for recognized audio and video, including MP3; the sidecar uses server-side
  FFmpeg to extract the first audio stream into MP3. File content is transferred
  in chunks and the result is written to disk rather than loaded in full into
  application memory.
- On success, the **same File ID** changes to `audio/mpeg` with an MP3 path and
  metadata. The original media blob is deleted before the File is marked
  `completed`. The prepared audio stays available even if a later STT provider
  request fails.
- Preparation writes a separate storage blob (`<File ID>_prepared.mp3`, or the
  alternate name if that is the source). The native File path/metadata commit
  precedes source deletion, including when the uploaded filename already ends
  in `.mp3`. The display filename remains the source stem plus `.mp3`.
- On a conversion error, attempt 2 starts immediately. Attempt 3 becomes due
  420 seconds (7 minutes) after attempt 2; the reconciler checks pending work
  every 60 seconds. After a third failure, v0.1.3 preserves the source media and
  File path and marks the File `failed`. The UI shows an error
  and does not send the failed attachment.
- Attempt and cleanup state live in File metadata so a restart can resume the
  delayed attempt or finish deletion. Pending cleanup is retried until the
  source blob is gone. A conversion success is complete only after deletion.
- Existing linked video attachments were migrated to audio; unreferenced and
  failed legacy videos were removed during the 2026-09-25 rollout. Successful
  preparation retains only prepared audio; v0.1.3 preserves a failed source for
  recovery.

## MP3 preparation change, 20 October 2026

Event Function v0.1.3 and audio-context Filter v0.2.7 were installed through the
native API on OpenWebUI 0.12.2. Ordinary-user upload/Send, full transcript after
reload and cached regeneration passed with one preparation and one STT job.
See the [production report and quality boundary](../../reports/2026-10-20/STT_MP3_PREPARATION.report.md).

The existing STT service validates the actual prepared byte count before
creating a transcription job or calling Lemonfox. No size calculator, URL
publication, new service or provider client is introduced. If prepared audio
still exceeds the configured/direct-upload limit, the Filter maps
`prepared_audio_too_large` and `provider_direct_upload_limit_exceeded` to the
same safe Russian explanation in native status events and the model context:
there is no transcript, split the recording and upload the parts separately,
and resending identical bytes does not help. Other errors keep their existing
handling. Splitting and automatic URL delivery are outside this change.

Qualification combines the existing installed-STT offline media check (now
including a stereo 320 kbit/s MP3) and `verify_native_intake_runtime.py` in the
exact deployed WebUI image, with separate temporary native SQLite/Storage and
no network or production mounts. The latter substitutes only preparation HTTP;
it does not qualify FFmpeg or paid transcription. For a Functions-only release,
preserve source/Valves/activation, confirm no pending media, then disable the
Event through the native API, update its source and enable it again so its old
reconciler stops and the new one starts. No service restart is needed.

## Operator checks

For the verified 0.12.2 production containers on the VPS (recheck current owners
before operations):

```text
docker inspect --format '{{.Name}} {{.State.Status}} {{.State.Health.Status}}' openwebui-0122-openwebui-0122-1 openwebui-0122-stage2-stt-0122-1
docker logs --since 15m openwebui-0122-openwebui-0122-1
docker logs --since 15m openwebui-0122-stage2-stt-0122-1
```

The old `openwebui`/`stage2-stt` applications and their volumes were retired
with owner approval on 7 October. `/opt/openwebui-prd0` now retains shared
infrastructure configuration, not those applications. The verified current
release Compose is under `/opt/openwebui-upgrade-0122/compose/`, with the
private environment under `/opt/openwebui-upgrade-0122/final-01/`. Follow the
[0.12.2 production and recovery owner](../../infra-ops/openwebui-0122-cutover.md)
and inspect the current Compose labels before lifecycle operations.

Verify the user route through `https://gpt.alpha-soft.ru/` with an ordinary
account: attach a small M4A and a small video with speech in separate chats,
observe MP3 replacement before Send, then send and check each transcript.
Repeat with a long enough recording to observe the waiting notice. A no-audio
video must fail after three attempts, retain its source with failed status and
produce no STT job. Remove task-owned verification uploads and chats after
checking. A healthy `/health`
response alone does not prove this workflow.

For a failed provider call, inspect the sidecar error separately from media
preparation. The prepared audio remains the user attachment and can be sent
again. Do not restore the source media as a recovery step. Check disk space,
container memory and swap before a large-media investigation. Never print
provider keys, internal tokens, authorization headers, or raw provider payloads.

## Memory limits

The following is historical 0.9.6 incident evidence, not the current 0.11.4
deployment recipe. Inspect the current container names above and their native
cgroup limits, current release Compose and recorder samples for a new incident.

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
