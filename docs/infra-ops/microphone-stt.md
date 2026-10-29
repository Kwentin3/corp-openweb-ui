# Microphone dictation: browser Web API and Lemonfox

Updated 29 October 2026. Production OpenWebUI 0.12.2 provides both paths through
the existing microphone button and native personal Audio settings. This is
manual selection; there is no automatic fallback on a browser recognition error.

## User instructions

Refresh the portal, then open **Settings → Audio → Speech-to-Text Engine**:

| Personal choice | Path |
| --- | --- |
| **Web API** / **Веб API** | Existing browser speech recognition. |
| **Default** / **По умолчанию** | Record audio, confirm the recording, then transcribe through server-side Lemonfox. |

Save the selection. It persists after reloading. Use the ordinary microphone
button; confirm the recording with the checkmark. The result is appended to the
chat input for review. The separate instant-send setting retains its native
behavior. Server processing has a wait after confirmation; it does not reproduce
browser recognition's immediate feedback.

All 31 accounts present before activation retained the browser path through an
explicit `settings.ui.audio.stt.engine = web` preference. Accounts created later
use Lemonfox by default unless they select Web API. A browser recognition outage
does not prevent server transcription when recording still works. Denied device
access or a failed recorder must be resolved separately.

## Native configuration owner

The authoritative settings are OpenWebUI's persisted Audio configuration, not a
frontend patch or the attachment STT service:

| Persisted key | Accepted value |
| --- | --- |
| `audio.stt.engine` | `openai` (OpenAI-compatible protocol) |
| `audio.stt.openai.api_base_url` | `https://api.lemonfox.ai/v1` |
| `audio.stt.model` | `whisper-1` |
| `audio.stt.openai.api_request_format` | `multipart` |
| `audio.stt.supported_content_types` | `["audio/*", "video/webm"]` |

The API key remains in protected server-side configuration. It was sourced from
the existing Lemonfox integration; it is not exposed to ordinary users or committed.
Changing the key in the attachment service does not rotate the native Audio
configuration automatically. During credential rotation, update both existing
configuration consumers using the protected secret source and recheck the routes.

The standard route is:

`microphone → getUserMedia → MediaRecorder → /api/v1/audio/transcriptions → native OpenAI-compatible STT adapter → Lemonfox → chat input`.

Attachment transcription remains owned by the existing media intake/Stage 2
path. No core code, image, service, recorder, proxy or provider client was added.
No build or restart was needed.

Do not use `ui.default_interface_settings.audio.stt.engine = web` to preserve
browser selection globally: the native UI saves Default by omitting `engine`;
merging a global browser preference would select Web API again after reload.

## Acceptance evidence

The final readback binds this configuration to image
`sha256:a0f5752afafd24ae065190ef28d88717e9a29c739ccb23be1e2d3e7ff7bfe424`.
The unchanged recorder bundle `BIrlHEaX.js` has SHA256
`b8caa6482794fc51afda2a9a50e748d0a1edc175ff8f89af5cd271e072d56455`.
Final health was `healthy`, restart count was 0, and the container start time
remained 26 October 2026, 14:53:46 UTC.

- Installed native adapter rehearsal returned the entire known Russian source
  phrase through the real Lemonfox endpoint before activation.
- A temporary ordinary-user browser session selected Web API, saved, reloaded,
  and confirmed the selection. It then selected Default, saved, reloaded, and
  used server transcription with both SpeechRecognition constructors absent.
- A known 11.6-second synthetic Russian WAV supplied the audio capture fixture.
  The actual native MediaRecorder produced a WebM recording; no transcription
  request or response was mocked. One 177,197-byte multipart request reached the
  native endpoint and returned HTTP 200 with the entire source phrase.
- The existing typed prefix was retained, with the transcript appended once.
  No chat message or model request was submitted; the test account had zero chats.
- Escape cancellation and a synthetic microphone `NotAllowedError` each left
  the input intact and produced no additional transcription request.
- The native server log correlated recording UUID
  `4a7bd925-639b-4452-a6f4-9dc9e8d57c74` with conversion and HTTP 200. For this
  approximately 25-second recording, processing from server receipt to response
  took about 22 seconds (13:45:58–13:46:20 UTC). This is one observed sample,
  not a latency guarantee.
- All 31 original account settings matched the expected single-field migration;
  all unrelated configuration keys and user settings remained unchanged.
- Temporary account sessions were revoked and the account deleted through native
  APIs; its owned browser context was closed. Exact test cache artifacts were
  removed after recording evidence. Normal audit events and protected rollback
  evidence remain retained.

Synthetic capture verifies the browser recorder, server/provider route, and
text insertion. Physical desktop microphone and mobile-device acceptance were
not performed. Browser speech recognition itself was not independently retested;
its deployed code is byte-identical and its personal selection persists.

## Recovery

Protected operator evidence is retained on the production host under
`/opt/openwebui-ops/microphone-stt-20261029/`. It includes the activation/rehearsal
logs, a rollback script, and a hash-matched copy of the private pre-change
snapshot. The original snapshot remains mode 0600 in the WebUI data volume at
`/app/backend/data/microphone-stt-20261029.rollback.private.json`.

From a trusted host shell, rehearse the native rollback without applying it:

```bash
docker exec -i -e PYTHONDONTWRITEBYTECODE=1 \
  openwebui-0122-openwebui-0122-1 python - \
  < /opt/openwebui-ops/microphone-stt-20261029/rollback.py
```

The script defaults to an uncommitted transaction and verifies that live
configuration is unchanged afterward. This rehearsal passed for all 31 accounts.
To apply an explicitly authorized rollback, add `--apply` after `python -`.
The script refuses STT configuration drift, restores only the touched native
Audio keys and per-user engine field, and preserves unrelated preferences and
subsequent user engine choices. Refresh clients after applying.
