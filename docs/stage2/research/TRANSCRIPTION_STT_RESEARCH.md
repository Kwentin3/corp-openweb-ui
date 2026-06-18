# Transcription STT Research

## 1. Question

How should Stage 2 deliver audio/video transcription through OpenWebUI without exposing STT API
keys?

## 2. Research status

Status: researched from official OpenWebUI, Lemonfox and ffmpeg.wasm docs on 2026-06-18.

Result type: architecture input. No runtime API call was made and no customer media was processed.

## 3. Findings

- OpenWebUI has native STT, but it is primarily an audio input/transcription capability inside chat.
  It supports local Whisper, browser Web API and remote providers.
- Backend STT supports `AUDIO_STT_ENGINE=openai`, Deepgram, Azure and Mistral;
  `AUDIO_STT_OPENAI_API_BASE_URL` and `AUDIO_STT_OPENAI_API_KEY` can point to OpenAI-compatible
  endpoints.
- OpenWebUI enforces accepted audio extensions and MIME/content-type controls for STT uploads.
  Default allowed extensions include `mp3,wav,m4a,webm,ogg,flac,mp4,mpga,mpeg`.
- Lemonfox exposes an OpenAI-compatible `/v1/audio/transcriptions` endpoint, accepts file upload or
  URL, and supports `json`, `text`, `srt`, `verbose_json`, `vtt` responses.
- Lemonfox adds useful non-OpenAI parameters: `speaker_labels`, `callback_url`, word timestamps and
  EU endpoint selection. These should not be assumed to pass through native OpenWebUI
  OpenAI-compatible STT without a proxy/adapter test.
- Existing PRD-1 says browser ffmpeg workflow is a technical asset. That workflow is not present in
  this repo, so only the integration boundary can be researched here.

## 4. Recommended architecture direction

Use a server-side STT proxy/adapter for the PRD-1 transcription scenario.

The proxy should:

- authenticate through OpenWebUI/session boundary or an approved internal auth path;
- keep Lemonfox/API keys server-side;
- accept prepared audio from browser ffmpeg workflow;
- enforce file size, duration, MIME and extension limits;
- call Lemonfox or another STT provider;
- normalize response into transcript + timestamps + speaker labels where available;
- return clear errors for size, provider timeout, unsupported format and quota;
- log usage metadata without storing raw audio by default.

Native OpenWebUI STT can still be tested as a low-cost baseline, but it should not replace the proxy
unless it proves all PRD-1 acceptance needs.

Backend-first clarification:

- ffmpeg workflow is a media-preprocessing asset, not a security boundary;
- STT provider keys must live only server-side;
- first implementation slice should define and test STT proxy API before building final UI;
- frontend must not decide provider keys, data policy, retention or access rules.

## 5. Open questions

- Exact deployed OpenWebUI version capabilities and UI flow.
- Where the existing ffmpeg workflow lives and what its API/output contract is.
- Target max media size/duration for pilot.
- Whether diarization is mandatory in Practical Stage 2 or can be first-pass optional.
- Whether EU processing is required despite Lemonfox surcharge.

## 6. Acceptance proof needed

- API key absent from browser network and bundle.
- Desktop and mobile sample media processed through ffmpeg workflow.
- Lemonfox transcript returned for Russian speech.
- Large/unsupported files fail with understandable user message.
- Usage metadata visible enough for admin cost review.
- STT proxy contract, auth/permissions, provider error model and transcript normalization are
  documented before UI integration.

## 7. Sources

- https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/stt-config/
- https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/env-variables/
- https://docs.openwebui.com/reference/env-configuration/
- https://www.lemonfox.ai/apis/speech-to-text
- https://www.lemonfox.ai/
- https://ffmpegwasm.netlify.app/docs/overview/
- https://ffmpegwasm.netlify.app/docs/getting-started/usage/

## 8. Status

Research complete. Next document should be an ADR for STT proxy boundary.
