# ADR-0004 STT Proxy Boundary

Status: Proposed

## 1. Context

Transcription is a priority Stage 2 scenario. PRD-1 states that an existing
ffmpeg browser workflow is a technical asset, and STT provider keys must remain
server-side.

Lemonfox is the priority STT provider candidate, but native OpenWebUI STT and
other providers remain research/baseline options.

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom Stage 2 logic should live
in bounded domain services, internal APIs, or thin integration shims.

Related boundary map: [CONTRACT_BOUNDARIES](../CONTRACT_BOUNDARIES.md).

## 2. Problem

If transcription starts from UI/browser implementation, provider keys, upload
limits, transcript format, errors, retention and access control can drift across
frontend, OpenWebUI and provider code.

Frontend must not own security, provider keys, data policy, retention, manager
visibility or usage accounting.

The ffmpeg workflow is useful media preprocessing, but it is not a security
boundary. The backend must still validate auth, file metadata, policy, limits
and retention.

## 3. Decision needed

Approve the browser/server/provider boundary and the STT proxy contract before
final UI work.

This ADR does not approve implementation. It defines what must be reviewed and
proven before implementation planning.

## 4. Options

Option 1. Native OpenWebUI STT only.

- Lowest custom work.
- Must prove it satisfies audio/video workflow and Lemonfox needs.
- Must prove provider-specific options, transcript shape, permissions, usage and
  retention are enough.

Option 2. Server-side STT proxy/job boundary.

- Keeps API keys server-side.
- Defines auth, limits, errors, job lifecycle and transcript normalization.
- Keeps provider-specific behavior in backend adapters.
- Recommended direction for PRD-1 transcription.

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
- usage event emission;
- Lemonfox priority candidate;
- actual ffmpeg artifact contract inspection.

Job-based contract is preferred over a single sync-only endpoint because audio
and video files may be long, cancellation/progress matters, and provider callback
support may be needed later.

Short files may still be processed synchronously behind the job contract. The
external UI-facing boundary should remain job-oriented unless ADR review rejects
that shape.

## Contract candidates

The first implementation-facing contract candidates are:

- `TranscriptionJobV1`;
- `TranscriptResultV1`;
- `UsageEventV1`;
- `PolicyDecisionV1`.

Supporting contracts from the broader Stage 2 boundary map:

- `RetentionPolicyV1`;
- `ProviderModelCatalogV1`;
- `ManagerVisibilityPolicyV1`.

UI/templates should depend on normalized internal contracts, not raw Lemonfox,
OpenAI or other provider responses.

## Draft endpoint boundary

Draft endpoint names:

```text
POST /stage2-api/transcription/jobs
GET /stage2-api/transcription/jobs/{job_id}
GET /stage2-api/transcription/jobs/{job_id}/result
POST /stage2-api/transcription/jobs/{job_id}/cancel
```

Important constraints:

- endpoint names are draft;
- final routing depends on OpenWebUI integration/auth proof;
- browser never calls Lemonfox directly;
- provider keys live server-side only;
- ffmpeg workflow contract must be inspected before implementation;
- routes must be compatible with future OpenWebUI updates;
- routing should prefer sidecar/internal backend API or minimal integration shim
  over deep OpenWebUI core patching.

## 6. Consequences

- Frontend/UI follows after proxy contract.
- ffmpeg workflow remains media preprocessing, not a security boundary.
- Storage and retention must align with ADR-0001 and ADR-0003.
- Lemonfox-specific features must be tested before promising them.
- Provider adapter and transcript normalization stay server-side.
- OpenWebUI upgrade risk is lower if Stage 2 API remains isolated behind a
  sidecar/internal backend route or thin shim.

## 7. Runtime proof needed

- Inspect actual ffmpeg workflow artifact.
- Confirm browser output format and proxy input contract.
- Prove STT API key is absent from browser bundle/network.
- Smoke one audio and one video sample.
- Verify unsupported/large-file error behavior.
- Verify auth/session propagation from OpenWebUI or approved identity boundary.
- Emit a sample `UsageEventV1`.
- Return a sample `TranscriptResultV1`.

## 8. Customer input needed

- Maximum file size and duration.
- Required languages.
- Whether speaker labels are required in first slice.
- Retention requirement for source media, audio blob and transcript.
- Approved STT provider/account path.
- Whether EU processing is required.
- Whether transcript storage is required or transient output is enough.

## Open questions

- How will OpenWebUI session/auth be propagated to Stage 2 backend?
- Where are audio blobs temporarily stored?
- What are max file size/duration limits?
- What is cancellation behavior?
- What transcript fields are mandatory?
- How are speaker labels/timestamps normalized?
- How are usage events emitted?
- What retention applies to source audio and transcript?
- Is callback/async provider flow required in Practical Stage 2 or deferred?
- How are errors mapped into stable UI-facing reason codes?

## 9. Acceptance signals

- ADR approved.
- Proxy input/output documented.
- Auth/permissions documented.
- Key handling proven server-side.
- ffmpeg artifact contract inspected.
- Contract candidates reviewed.
- Draft endpoint boundary accepted, revised or rejected.
- Open questions are closed or explicitly deferred before implementation.

## 10. Links

- [CONTRACT_BOUNDARIES](../CONTRACT_BOUNDARIES.md)
- [TRANSCRIPTION_STT](../blueprints/TRANSCRIPTION_STT.blueprint.md)
- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)
