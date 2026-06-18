# ADR-0004 STT Proxy Boundary

Status: Proposed

## 1. Context

Transcription is a priority Stage 2 scenario. PRD-1 states that an existing
ffmpeg browser workflow is a technical asset, and STT provider keys must remain
server-side.

Lemonfox is the priority STT provider candidate, but native OpenWebUI STT and
other providers remain research/baseline options.

## 2. Problem

If transcription starts from UI/browser implementation, provider keys, upload
limits, transcript format, errors, retention and access control can drift across
frontend, OpenWebUI and provider code.

## 3. Decision needed

Approve the browser/server/provider boundary and the STT proxy contract before
final UI work.

## 4. Options

Option 1. Native OpenWebUI STT only.

- Lowest custom work.
- Must prove it satisfies audio/video workflow and Lemonfox needs.

Option 2. Server-side STT proxy.

- Keeps API keys server-side.
- Defines auth, limits, errors and transcript normalization.
- Recommended for PRD-1 transcription.

Option 3. Direct browser-to-provider call.

- Not acceptable because API keys and policy would move into browser/client.

## 5. Recommended option

Use Option 2 unless native OpenWebUI STT proves every PRD-1 acceptance need.

The boundary must include:

- browser/server/provider boundary;
- existing ffmpeg workflow as technical asset;
- API keys server-side only;
- auth/permissions;
- max file size/duration;
- MIME/content-type;
- transcript format;
- timestamps/speaker labels;
- error model;
- storage/retention;
- cancellation/retry;
- Lemonfox priority candidate;
- actual ffmpeg artifact contract inspection.

## 6. Consequences

- Frontend/UI follows after proxy contract.
- ffmpeg workflow remains media preprocessing, not a security boundary.
- Storage and retention must align with ADR-0001 and ADR-0003.
- Lemonfox-specific features must be tested before promising them.

## 7. Runtime proof needed

- Inspect actual ffmpeg workflow artifact.
- Confirm browser output format and proxy input contract.
- Prove STT API key is absent from browser bundle/network.
- Smoke one audio and one video sample.
- Verify unsupported/large-file error behavior.

## 8. Customer input needed

- Maximum file size and duration.
- Required languages.
- Whether speaker labels are required in first slice.
- Retention requirement for source media, audio blob and transcript.
- Approved STT provider/account path.

## 9. Acceptance signals

- ADR approved.
- Proxy input/output documented.
- Auth/permissions documented.
- Key handling proven server-side.
- ffmpeg artifact contract inspected.

## 10. Links

- [TRANSCRIPTION_STT](../blueprints/TRANSCRIPTION_STT.blueprint.md)
- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)
