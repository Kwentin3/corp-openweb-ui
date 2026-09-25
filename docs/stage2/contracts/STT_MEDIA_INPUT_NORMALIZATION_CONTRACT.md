# STT Media Input Normalization Contract

Status: current uploaded-media contract, 2026-09-25. The June 2026 browser
ffmpeg.wasm/Transcribe Action design is historical; its dated reports remain
evidence of that earlier implementation.

## Boundary and ownership

```text
native OpenWebUI upload
  -> video: upload hook -> stage2-stt FFmpeg preparation -> MP3 File replacement
  -> native Send -> STT Filter -> stage2-stt -> Lemonfox -> chat transcript
```

- OpenWebUI owns File IDs, metadata, storage, attachment state and chat history.
  The upload hook prepares video independently of Send. The native composer
  waits for a pending attachment and sends automatically when it becomes audio.
- `stage2-stt` owns server-side media preparation and STT provider calls.
  Lemonfox credentials and internal authentication stay server-side.
- Uploaded audio follows the native STT Filter on Send. Video enters the Filter
  as prepared audio; it is not passed to a VLM as the original video.
- MIME and extension are routing hints, not a promise that a container or codec
  can be decoded. FFmpeg conversion and a nonempty audio output decide success.
  A video without an audio stream cannot be sent for transcription.

## File state and retention

The native File ID stays constant. During video preparation its `data.status`
is `processing`, with retry/cleanup state in `data.stage2_video_intake`.
Successful conversion stores an MP3 (`audio/mpeg`) under the File ID, deletes
the original video blob, then marks the File `completed`. If deletion fails,
cleanup stays pending and the File is not ready to send.

The service makes at most three conversion attempts: the first two are
consecutive, and the last is scheduled 420 seconds after the second failure.
The reconciler resumes pending work across restarts and checks every 60
seconds. On the final failure it deletes the video, clears `File.path`, marks
the File `failed`, and exposes a safe error. A failed File cannot be sent.
Transient working files are removed after each attempt. The product does not
retain an unconverted video for a later manual retry.

The upload-to-preparation path and sidecar response stream in bounded chunks
to disk; it does not read the entire video into Python or browser memory.
Prepared audio remains available if the later provider STT request fails.
Audio retention follows OpenWebUI's normal File/chat policy; source-video
deletion is a separate hard rule.

## User-visible states

| State | UI behavior |
| --- | --- |
| Upload/preparation running | Attachment is busy; pressing Send shows a waiting notice and queues that draft. |
| Preparation complete | Attachment displays the MP3 name and size; queued Send proceeds. |
| Three conversion failures | Error is shown, queued Send stops, source video is gone. |
| STT provider failure after preparation | MP3 remains; user can retry transcription by sending it again. |

The accepted ordinary-chat flow is described in the
[runbook](../operations/STT_NATIVE_MEDIA_TRANSCRIPTION_RUNBOOK.md). Keep
browser ffmpeg.wasm assets and the older Action contract out of current-route
configuration and acceptance criteria.
