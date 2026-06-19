# Lemonfox STT Research

## 1. Question

Is Lemonfox suitable as the priority STT provider for corporate OpenWebUI transcription?

## 2. Research status

Status: researched from official Lemonfox docs on 2026-06-18 and refined for
ADR-0004 Stage 2 decisions on 2026-06-19.

Result type: provider fit assessment. No API key or live call was used.

## 3. Confirmed provider facts

- Endpoint: `POST https://api.lemonfox.ai/v1/audio/transcriptions`.
- API shape is OpenAI-compatible enough for standard transcription calls.
- Input can be file object/upload or public URL.
- Upload size limit: 100 MB for direct upload.
- URL input size limit: 1 GB.
- Supported formats include `mp3`, `wav`, `flac`, `aac`, `opus`, `ogg`, `m4a`, `mp4`, `mpeg`, `mov`,
  `webm` and more.
- Response formats: `json`, `text`, `srt`, `verbose_json`, `vtt`.
- Speaker diarization is available through `speaker_labels=true`, with current max 4 speakers, and
  requires `response_format=verbose_json` to access labels.
- `callback_url` exists for long audio/asynchronous completion.
- Word timestamps are available through `timestamp_granularities[]=word` with `verbose_json`.
- Language can be provided explicitly; Russian is listed as supported.
- EU endpoint: use `eu-api.lemonfox.ai`; official docs state a 20% surcharge for EU-based
  processing.
- Pricing stated by Lemonfox: $0.50 per 3 hours of speech; $5/month includes 30 hours STT or
  equivalent credits.
- Lemonfox homepage states data is deleted immediately after processing and EU-based processing is
  available.

## 4. Fit for PRD-1

Lemonfox is a strong candidate for Practical Stage 2 because it gives:

- low advertised STT cost;
- Russian language support;
- video/audio file format support;
- subtitle formats;
- diarization;
- OpenAI-compatible baseline endpoint;
- EU processing option.

It still should be integrated through a server-side proxy because:

- browser must not receive API key;
- direct 100 MB upload limit may require browser preprocessing and/or server checks;
- Lemonfox-specific parameters may not pass through native OpenWebUI STT;
- callback handling needs a server endpoint;
- cost/usage logging is required for corporate admin visibility.

## 5. Risks

- Provider docs are not a substitute for SLA/DPA/legal review.
- Real Russian corporate audio accuracy is untested.
- Diarization max 4 speakers may be insufficient for some meetings.
- Public URL upload is not appropriate for sensitive files unless storage access and expiry are
  designed.
- Long audio UX requires progress/cancel/retry behavior.

## 6. Recommended next step

Build an STT proxy ADR and a small live smoke once the customer approves test audio and provider
key:

- 2-5 minute Russian meeting fragment;
- 2 speakers and 5 speakers samples;
- mobile-recorded audio;
- one video input preprocessed by browser ffmpeg;
- one unsupported/oversized input.

## 7. Sources

- https://www.lemonfox.ai/apis/speech-to-text
- https://www.lemonfox.ai/

## 8. Status

Research complete. Provider selected as priority candidate, not yet production-approved.
For ADR-0004 Stage 2 planning, Lemonfox is the first STT provider through
`LemonfoxSttAdapter`, not hardwired architecture.

Open decisions before implementation:

- prove whether WebM/Opus or OGG/Opus is the better default output profile;
- keep MP3 / `audio/mpeg` as source-proven compatibility fallback;
- document behavior when prepared audio exceeds 100 MB direct upload limit;
- approve URL/object-storage provider path only after access, expiry and
  sensitivity review;
- store normalized/prepared audio in S3/object storage with env-configured
  retention;
- verify whether provider-side cancellation exists; otherwise use local cancel
  and ignore/cleanup late result by retention policy.
