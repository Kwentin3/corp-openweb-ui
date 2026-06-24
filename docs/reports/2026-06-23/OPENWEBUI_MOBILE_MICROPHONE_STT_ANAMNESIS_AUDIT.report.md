# OpenWebUI Mobile Microphone STT Anamnesis Audit

Date: 2026-06-23

Scope: diagnostics only. No runtime settings, source files, container images or
database values were changed during this audit.

## 1. Executive Summary

Observed user symptom:

- desktop chat microphone works: recording, live transcription and composer
  insertion are OK;
- mobile chat microphone shows the recording waveform;
- mobile microphone path does not produce transcription;
- mobile recording stops after about five seconds.

Current verdict:

The mobile symptom is most likely in OpenWebUI native microphone dictation, not
in the Stage 2 `stage2-stt` sidecar and not in the attachment-level
`Transcribe` action.

The live OpenWebUI config has `audio.stt.engine = web`. That means the chat
microphone dictation path uses the browser Web Speech API
(`window.SpeechRecognition` / `window.webkitSpeechRecognition`) when available.
It is a client-side browser-recognition path. It is separate from the server
sidecar path:

```text
Media attachment -> static loader Transcribe -> browser ffmpeg normalization
-> OpenWebUI Action -> private stage2-stt sidecar -> Lemonfox
```

The five-second mobile stop lines up with the currently applied native Web STT
recorder patch. The patch intentionally changed OpenWebUI's Web API inactivity
timeout from 2 seconds to 5 seconds.

Important distinction:

- the waveform proves that `MediaRecorder`/microphone capture is alive;
- it does not prove that `SpeechRecognition` is producing transcript events.

## 2. Existing Project Anamnesis

The repo already records that there are two different STT paths.

Documented Stage 2 MVP path:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md:162` says the MVP
  trigger is explicit attachment `Transcribe`, not implicit LLM behavior.
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md:173` says native
  OpenWebUI microphone/Web API dictation is a separate feature path from the
  attachment-level Stage 2 `Transcribe` workflow.
- `docs/stage2/README.md:159` says native OpenWebUI Web API microphone
  dictation is patched through a pinned OpenWebUI image layer, while the Stage 2
  static loader no longer post-processes native microphone input.

Documented hardening backlog:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md:217` keeps mobile
  browser acceptance in backlog.
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md:221` keeps duration
  policy in backlog.
- `docs/stage2/README.md:191` keeps mobile, large and low-memory browser proof
  in testing/hardening.

Prior native recorder patch report:

- `docs/reports/2026-06-19/OPENWEBUI_NATIVE_WEB_STT_RECORDER_PATCH.report.md:4`
  scopes that patch to native OpenWebUI microphone dictation with STT engine set
  to Web API.
- Lines `8-10` state that duplicated/mixed microphone transcription behavior is
  owned by native OpenWebUI Web API recorder, not the Stage 2 attachment
  transcription feature.
- Lines `33-36` state the patch intent: reset accumulator, rebuild transcript
  from current `SpeechRecognitionResultList`, and increase inactivity timeout
  from 2 seconds to 5 seconds.

## 3. Local Code Evidence

The native Web STT patch is image-level and signature-based:

- `deploy/openwebui-native-web-stt-patch/Dockerfile` builds from pinned
  OpenWebUI and runs the patcher.
- `compose/openwebui.compose.yml:30` points the OpenWebUI image build to
  `deploy/openwebui-native-web-stt-patch/Dockerfile`.
- `compose/openwebui.compose.yml:33` names the image
  `corp-openwebui/openwebui:v0.9.6-native-web-stt-v1`.

The patcher evidence:

- `deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py:5-8`
  documents the intent: reset transcript accumulator, rebuild transcript from
  the current `SpeechRecognitionResultList`, and increase inactivity timeout.
- `deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py:20`
  defines `PATCH_ID = "stage2-native-web-stt-v1"`.
- `deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py:23-24`
  identifies the original Web Speech API recorder signature with `const r=2e3`.
- `deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py:31-35`
  replaces it with the patched signature and `const r=5e3`.

The attachment-level STT path is separate:

- `deploy/openwebui-static/loader.js` installs the `Transcribe` action on media
  attachment cards.
- `deploy/openwebui-static/loader.js:691-707` runs attachment transcription with
  explicit button busy/completed/error feedback.
- `deploy/openwebui-static/loader.js:710-751` calls
  `/api/chat/actions/stage2_media_transcription_action` and appends returned
  transcript to the composer.
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
  sends prepared audio to the sidecar endpoint
  `/stage2-api/transcription/jobs`.

This local evidence already separates "chat microphone dictation" from
"attachment Transcribe action".

## 4. Live Runtime Evidence

Server host:

```text
host: ai-corp
openwebui image: corp-openwebui/openwebui:v0.9.6-native-web-stt-v1
openwebui status: Up / healthy
stage2-stt status: Up
traefik status: Up
```

OpenWebUI database config audit:

```text
audio.stt.engine = web
audio.stt.model = whisper-1
audio.stt.openai.api_base_url = https://api.openai.com/v1
audio.stt.openai.api_key = <masked>
```

Interpretation:

`audio.stt.engine = web` is the decisive setting for the native chat
microphone. It means native microphone dictation uses browser Web API STT, not
OpenAI/Lemonfox server-side transcription.

Live built bundle audit:

```text
/app/build/_app/immutable/chunks/DM0E3qNi.js
patch_id present: true
speech signature present: true
const r=5e3 present: true
const r=2e3 present: false
```

Extracted live chunk behavior:

```text
new (window.SpeechRecognition || window.webkitSpeechRecognition)
p.continuous = true
O = ""
p.__stage2NativeWebSttPatch = "stage2-native-web-stt-v1"
const r = 5e3
p.onresult = ...
setTimeout(() => { p.stop() }, r)
p.onend = ...
p.onerror = ...
```

This proves the running server is using the patched native Web Speech API
recorder and the current inactivity timeout is 5 seconds.

Stage 2 sidecar capability audit from inside the OpenWebUI container:

```text
GET http://stage2-stt:8080/stage2-api/transcription/capabilities -> 200
provider_id = lemonfox
adapter_id = lemonfox
selected_output_profile = opus_webm_compact
fallback_output_profile = mp3_high_compat
max_browser_duration_minutes = None
max_duration_seconds = None
max_prepared_audio_mb = 100
storage_mode = auto
storage_available = False
warnings =
  prepared_audio_storage_transient
  provider_max_duration_unknown
  provider_cancel_unknown_local_cancel_only
```

Static browser normalization config audit:

```text
GET /static/stage2-stt-normalization.json -> 200
selected_output_profile = mp3_high_compat
max_browser_duration_minutes = None
max_browser_input_mb = 1024
max_prepared_audio_mb = 100
ffmpeg_asset_mode = self_hosted
```

Interpretation:

The sidecar and static attachment-transcription path are available. They do not
explain a hard five-second stop in native microphone dictation because that
native microphone path currently uses `audio.stt.engine = web`.

## 5. Live Log Evidence

OpenWebUI logs for the relevant recent window show the attachment path working:

```text
GET /static/stage2-stt-normalization.json -> 200
GET /static/stage2-assets/ffmpeg/0.12.6/ffmpeg-util.js -> 200
GET /static/stage2-assets/ffmpeg/0.12.6/ffmpeg.js -> 200
GET /static/stage2-assets/ffmpeg/0.12.6/ffmpeg-core.js -> 200
GET /static/stage2-assets/ffmpeg/0.12.6/ffmpeg-core.wasm -> 200
file.content_type: audio/x-m4a
file.content_type: audio/mpeg
POST http://stage2-stt:8080/stage2-api/transcription/jobs -> 200
POST /api/chat/actions/stage2_media_transcription_action -> 200
```

Stage 2 sidecar logs show:

```text
POST /stage2-api/transcription/jobs HTTP/1.1 -> 200 OK
```

OpenWebUI logs did not show native microphone server STT requests such as
`/audio/transcriptions` in the inspected 24-hour grep window. That is consistent
with `audio.stt.engine = web`: the native microphone transcript path is handled
by browser `SpeechRecognition`, not by the sidecar.

## 6. Working Hypothesis

Most likely sequence on mobile:

1. User taps microphone.
2. Browser grants microphone capture.
3. OpenWebUI starts `MediaRecorder`, so the recording waveform is visible.
4. OpenWebUI also tries to use `window.SpeechRecognition` or
   `window.webkitSpeechRecognition` because `audio.stt.engine = web`.
5. On the mobile browser/device, speech recognition does not produce usable
   `onresult` transcript events, or it ends/errors quickly.
6. The patched recorder has a five-second inactivity stop path.
7. The UI stops recording with empty/no transcript.

This matches all observed facts:

- desktop works because desktop browser Web Speech API is producing transcript;
- mobile has waveform because audio capture works;
- mobile lacks transcript because recognition events are absent/broken;
- the stop is around five seconds because the live patch uses `const r=5e3`;
- server STT/sidecar does not show a failing mobile job because native mic is
  not using the sidecar.

## 7. What This Is Not

Current evidence does not support these explanations:

- Not a Lemonfox provider outage: sidecar capability endpoint returns 200 and
  recent sidecar job returned 200.
- Not a Stage 2 `Transcribe` action failure: recent attachment action path
  reached sidecar and returned 200.
- Not a global microphone permission failure: waveform indicates media capture
  starts.
- Not a configured Stage 2 duration limit: sidecar capabilities expose
  `max_browser_duration_minutes = None` and `max_duration_seconds = None`.
- Not the earlier Pyodide/Python `ssl` issue: this is browser microphone STT,
  not Code Interpreter.

## 8. UI Integrity Finding

Status: fail for mobile native microphone dictation.

Violations:

- The UI shows recording activity, but does not distinguish "audio capture is
  active" from "speech recognition is producing transcript". This violates the
  requirement that user-visible states be explicit.
- Mobile failure appears to terminate without a clear terminal error explaining
  unsupported/failed browser speech recognition. This violates the requirement
  that every user action produce terminal feedback.
- The current native path has no visible fallback decision: retry Web API,
  upload recorded blob to server STT, or tell the user that this browser is not
  supported. This leaves the user guessing.

Required fixes later, not applied in this audit:

- Add explicit state separation in the microphone UI:
  `recording_audio`, `recognizing_speech`, `recognition_no_result`,
  `recognition_error`, `transcript_inserted`.
- Add mobile-visible terminal errors for Web Speech API unsupported, denied,
  no-speech, aborted, network and empty-result cases.
- Decide whether mobile native microphone should use server STT instead of
  browser Web API STT.

Evidence:

- Problem solved by the screen: dictate chat input from microphone.
- Primary user action: tap microphone and speak.
- Required states: permission request, recording, recognizing, no speech,
  recognition error, empty transcript, transcript inserted, cancelled.
- UI/domain boundary: UI should capture audio and emit intent; STT provider
  choice should come from config/capabilities, not silent browser behavior.
- Feedback: currently waveform gives capture feedback, but mobile terminal STT
  failure is not sufficiently explicit.

Escalation:

The native microphone path is a non-trivial browser state machine. Any fix
should be planned as a separate patch with desktop/mobile proof, not mixed into
unrelated STT sidecar work.

## 9. Recommended Next Diagnostics

No fix should be applied before these are captured from the actual failing phone:

1. Device and browser:
   - OS and version;
   - browser and version;
   - whether it is installed PWA or normal browser tab.

2. Browser capability probe from the mobile browser console:

```js
({
  speechRecognition: Boolean(window.SpeechRecognition),
  webkitSpeechRecognition: Boolean(window.webkitSpeechRecognition),
  mediaRecorder: Boolean(window.MediaRecorder),
  mediaDevices: Boolean(navigator.mediaDevices?.getUserMedia)
})
```

3. Runtime event probe around the microphone button:
   - does `SpeechRecognition.start()` throw?
   - does `onstart` fire?
   - does `onresult` fire?
   - does `onerror` fire, and with what `error` value?
   - does `onend` fire before or after any result?

4. Network tab during mobile microphone use:
   - confirm whether any request is made to `/api/v1/files/`;
   - confirm whether any request is made to `/api/chat/actions/...`;
   - confirm whether any request is made to an OpenWebUI audio transcription
     endpoint.

5. Controlled config comparison:
   - keep current `audio.stt.engine = web` as baseline;
   - in a separate test window, compare server-side STT engine behavior if
     OpenWebUI native mic supports it without using the Stage 2 attachment path.

## 10. Strategic Options

Option A: keep Web API microphone as desktop convenience only.

- Low implementation risk.
- Mobile can show a clear unsupported/fallback message.
- Does not solve mobile dictation parity.

Option B: route mobile microphone recordings to server-side STT.

- Better product consistency.
- Reuses server-controlled provider/key boundary.
- Needs explicit upload/cancel/error/privacy handling.
- Should not be a blind timeout tweak.

Option C: only increase or change the five-second timeout.

- Fastest patch.
- Weak diagnosis.
- If mobile `SpeechRecognition` produces no results at all, this only delays
  failure and does not create transcription.

Current recommendation:

Do not start by increasing the timeout. First prove the mobile
`SpeechRecognition` event sequence. If it produces no reliable `onresult`
events, use server-side STT or explicit unsupported feedback for mobile.

## 11. Commands / Checks Performed

Local repo:

```text
git status --short --branch
rg --files | rg -i "(audio|voice|transcrib|speech|stt|record|mic|microphone|composer|chat|stage2)"
rg -n -i "mediarecorder|speechrecognition|webkitSpeechRecognition|getUserMedia|recording|transcrib|stt|audio|duration|5000"
Get-Content deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py
Get-Content deploy/openwebui-static/loader.js
Get-Content services/stage2-stt/stage2_stt/app.py
Get-Content services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py
```

Live server:

```text
ssh <stage-target> "docker ps ..."
docker inspect openwebui env audit with secrets masked
OpenWebUI SQLite config audit with secrets masked
live built chunk search for stage2-native-web-stt-v1 / const r=5e3 / const r=2e3
docker logs --since 24h openwebui filtered for audio/STT/stage2 events
docker logs --since 6h stage2-stt
GET http://stage2-stt:8080/stage2-api/transcription/capabilities from openwebui container
GET http://127.0.0.1:8080/static/stage2-stt-normalization.json from openwebui container
```

## 12. Final Audit Verdict

The mobile microphone issue is currently best classified as:

```text
native_web_speech_api_mobile_recognition_failure_or_empty_result
```

The server-side Stage 2 transcription path is alive and separate. The five
second cutoff is consistent with the applied native Web STT patch, not with a
Stage 2 sidecar limit. The next useful step is a mobile browser event/network
trace, not immediate code changes.
