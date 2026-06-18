# Lemonfox STT Research

## 1. Question

Is Lemonfox suitable as the priority STT provider for corporate OpenWebUI transcription?

## 2. Why it matters for PRD-1

PRD-1 names Lemonfox as priority STT candidate, but implementation depends on API behavior and limits.

## 3. Current assumptions

- Lemonfox may be cheaper than common alternatives.
- Provider call must go through server-side proxy.

## 4. What to verify

- OpenAI-compatible STT path.
- Direct upload limits.
- URL upload limits.
- Supported formats.
- Speaker labels / diarization.
- Russian language quality.
- Pricing.
- Response formats.
- Error handling.
- Latency.

## 5. Sources to check

- Lemonfox API docs.
- Official pricing page.
- Practical test with approved sample files.

## 6. Test plan / proof plan

Use short audio, short video-derived audio, large audio, Russian speech, noisy sample, and error case.

## 7. Risks

- Upload limits.
- Diarization limits.
- Latency for large files.
- Corporate data policy concerns.

## 8. Decision options

- Lemonfox as primary.
- Lemonfox as pilot only.
- OpenAI STT fallback.
- Local/alternative STT deferred.

## 9. Recommended next step

Verify API compatibility and limits before STT proxy design.

## 10. Status

Planned, not verified.
