# Microphone dictation: browser Web API and Lemonfox

Updated 29 October 2026. Production OpenWebUI 0.12.2 uses native server-side
Lemonfox as the primary microphone STT for all existing and new accounts. Both
paths remain available through the existing microphone button and native
personal Audio settings. There is no automatic fallback between engines.

## User instructions

Refresh the portal to load the new default. No personal selection is required
for Lemonfox. To inspect or change the choice, open
**Settings → Audio → Speech-to-Text Engine**:

| Personal choice | Path |
| --- | --- |
| **Web API** / **Веб API** | Existing browser speech recognition. |
| **Default** / **По умолчанию** | Record audio, confirm the recording, then transcribe through server-side Lemonfox. |

Save the selection. It persists after reloading. Use the ordinary microphone
button; confirm the recording with the checkmark. The result is appended to the
chat input for review. The separate instant-send setting retains its native
behavior. Server processing has a wait after confirmation; it does not reproduce
browser recognition's immediate feedback.

The initial selectable-reserve activation preserved Web API for 31 existing
accounts. The subsequent explicitly authorized fleet rollout removed only their
`settings.ui.audio.stt.engine` overrides, selecting native Default (Lemonfox).
Other preferences were preserved. Accounts created later also use Lemonfox by
default. Users can still explicitly select Web API through native settings.
A browser recognition outage does not prevent server transcription when
recording still works. Denied device access or a failed recorder must be
resolved separately.

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

## Bounded native speed comparison, 29 October 2026

The native Lemonfox-primary option was tested again without changing the running
service. An owned browser context encoded the same known 11.6-second Russian
source with MediaRecorder into a 176,942-byte WebM/Opus file (SHA256
`fa4f662c0af111b0a6a37797e0efb53f28a1f746b569f29245fac8845ed41d95`).
All four samples reused these exact bytes and the installed `audio.transcribe`
function, native configuration, and real Lemonfox provider. Timing wrappers
delegated unchanged to the original functions. The environment flag was set only
for each isolated probe process; the application and user settings stayed intact.

| Sample order | Preprocessing | Total seconds | Conversion seconds | Provider handler seconds |
| --- | --- | ---: | ---: | ---: |
| 1 | Native default | 8.004 | 0.574 | 7.275 |
| 2 | Bypass | 4.725 | skipped | 4.725 |
| 3 | Bypass | 5.039 | skipped | 5.039 |
| 4 | Native default | 4.998 | 0.529 | 4.269 |

All four returned the complete source text exactly. Bypass works with this
short WebM sample, but a consistent total-time improvement was not established:
the second default sample was as fast as bypass, and conversion itself cost only
0.5–0.6 seconds. The earlier 22-second UI sample does not establish conversion as
the cause of that delay. Provider/network variability remains material.

Keep the native preprocessing default for now. Skipping conversion, compression
and splitting has not been qualified on longer recordings, other browser codecs,
or other Audio paths. No fleet-wide preference or live environment flag was
changed for this pilot. These measurements cover the native transcription
function after imports, not HTTP upload/UI rendering or physical microphone
latency. Protected timing receipts are under the existing operator evidence
directory's `timing/` child; per-call temporary files were removed.

## Fleet rollout acceptance, 29 October 2026

The fleet change used a native SQLAlchemy transaction to remove only the personal
STT engine field. A temporary ordinary account was deliberately given Web API
before migration so its UI acceptance exercised the same transition as the real
accounts. All 31 real accounts and the one temporary test account moved to native
Default. Every other user preference and the complete server configuration were
compared against the pre-change snapshot.

The ordinary-user Audio screen showed Default after migration, with its unrelated
test preference preserved. The microphone check used the existing known Russian
audio fixture, actual MediaRecorder, native server endpoint and real Lemonfox;
browser SpeechRecognition was absent. Exactly one request returned HTTP 200 in
8.345 seconds after confirmation, with the complete source text. The typed
prefix was preserved and the transcript appeared once. Recording UUID was
`c025bf6e-05df-4157-9b0d-0198f19e6c10`. Physical-device acceptance remains distinct
from this synthetic capture check.

The temporary account's sessions were revoked, its old token returned 401, and
the account was deleted through native APIs. Its owned browser context was
closed. Refreshing the original account loaded Default as expected.

Final readback: all 31 real accounts have native Default, all unrelated user
settings exactly match the migration snapshot, and the server configuration hash
is unchanged. QA user/auth/chat counts and exact test cache artifacts are zero.
The same container is healthy, with restart count 0 and the unchanged 26 October
start time. Recovery snapshots are mode 0600 on the host and in the data volume.

The fleet rollback was rehearsed without commit. All users' settings hashes
before and after the rehearsal matched, and configuration stayed unchanged.
The live preprocessing flag, service image and service lifecycle were untouched.

## Recovery for the fleet default change

Protected recovery files are under
`/opt/openwebui-ops/microphone-stt-20261029/fleet/`. The rollback script and
hash-matched private snapshot restore the earlier personal preferences without
changing the configured Lemonfox provider. The original snapshot is mode 0600 at
`/app/backend/data/microphone-stt-fleet-20261029.rollback.private.json`.

Rehearse recovery without applying it:

```bash
docker exec -i -e PYTHONDONTWRITEBYTECODE=1 \
  openwebui-0122-openwebui-0122-1 python - \
  < /opt/openwebui-ops/microphone-stt-20261029/fleet/rollback.py
```

To apply an explicitly authorized fleet rollback, add `--rollback` after
`python -`. The script refuses configuration or personal-settings drift so it
cannot overwrite later user edits. Deleted test accounts are skipped. Refresh
clients after recovery. This operation does not restart the service.

## Earlier provider activation recovery

Protected operator evidence is retained on the production host under
`/opt/openwebui-ops/microphone-stt-20261029/`. It includes the activation/rehearsal
logs, a rollback script, and a hash-matched copy of the private pre-change
snapshot. The original snapshot remains mode 0600 in the WebUI data volume at
`/app/backend/data/microphone-stt-20261029.rollback.private.json`.

The earlier provider-activation rollback also restores global Audio keys. It is
not the rollback for the fleet preference change above. To rehearse that earlier
operation from a trusted host shell without applying it:

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
