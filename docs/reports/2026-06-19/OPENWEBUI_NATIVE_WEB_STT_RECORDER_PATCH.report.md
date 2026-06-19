# OpenWebUI Native Web STT Recorder Patch Report

Date: 2026-06-19
Scope: native OpenWebUI microphone dictation with STT engine set to Web API

## Verdict

The duplicated and mixed microphone transcription behavior is owned by the
OpenWebUI native Web API STT recorder, not by the Stage 2 attachment
transcription feature.

The Stage 2 static loader no longer installs a native microphone guard. It only
keeps the attachment-level `Transcribe` workflow.

## Changes

- Added a patched OpenWebUI image build layer:
  - `deploy/openwebui-native-web-stt-patch/Dockerfile`
  - `deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py`
- Updated `compose/openwebui.compose.yml` so `openwebui` builds from the pinned
  upstream base image and applies the native Web STT patch during image build.
- Updated `.env.example` with:
  - `OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6`
  - `OPENWEBUI_IMAGE=corp-openwebui/openwebui:v0.9.6-native-web-stt-v1`
- Removed the failed native voice post-processing guard from
  `deploy/openwebui-static/loader.js`.

## Patch Intent

The OpenWebUI Web API recorder patch applies source-level semantics to the built
bundle:

- reset the transcript accumulator at the start of each recording;
- rebuild the transcript from the current `SpeechRecognitionResultList` instead
  of appending the last result blindly;
- increase the Web API STT inactivity timeout from 2 seconds to 5 seconds.

The patcher is fail-fast. If OpenWebUI changes the generated recorder bundle and
the known signature is not found exactly once, the image build fails instead of
shipping an unpatched runtime.

## Runtime Notes

This is a bounded patch for the current pinned OpenWebUI image. It should be
revalidated when `OPENWEBUI_BASE_IMAGE` changes.

Long-term, server-side STT remains the preferred production path for predictable
quality and provider control. Browser Web Speech API can remain a convenience
fallback.
