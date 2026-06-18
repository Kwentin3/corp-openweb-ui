# Transcription STT Research

## 1. Question

How should Stage 2 deliver audio/video transcription through OpenWebUI without exposing STT API keys?

## 2. Why it matters for PRD-1

Transcription is the top customer priority and must become a Practical Stage 2 deliverable.

## 3. Current assumptions

- Existing ffmpeg workflow works on desktop/mobile.
- Lemonfox is priority STT candidate.
- Server-side proxy is required for provider keys.

## 4. What to verify

- Native OpenWebUI STT path.
- Upload and file size behavior.
- Internal auth/session reuse.
- Transcript storage.
- Prompt/template integration.
- Error handling and fallback.

## 5. Sources to check

- PRD-1.
- Existing ffmpeg project documentation/code, if provided separately.
- OpenWebUI STT docs/runtime.
- Lemonfox API docs.

## 6. Test plan / proof plan

Define proof with short audio, short video, large audio/video, unsupported format and network/provider error.

## 7. Risks

- API key exposure.
- Large file handling.
- Mobile memory limits.
- Weak user feedback during long tasks.
- Transcript retention ambiguity.

## 8. Decision options

- Native STT only.
- Isolated transcription module plus STT proxy.
- Minimal fork-slice.
- Server-side fallback for large files.

## 9. Recommended next step

Research native STT and Lemonfox first, then write STT proxy ADR.

## 10. Status

Planned, not verified.
