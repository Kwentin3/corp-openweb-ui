# Stage 2 Acceptance Matrix

## Minimum working scenarios with groups, prompts and owner

Domain:

- Workspaces / RBAC.

Blueprint:

- [WORKSPACES_AND_RBAC](../blueprints/WORKSPACES_AND_RBAC.blueprint.md)

Research:

- [OPENWEBUI_CAPABILITY_RESEARCH](../research/OPENWEBUI_CAPABILITY_RESEARCH.md)

Acceptance signal:

- User sees only allowed scenario.
- Admin can update prompts through agreed process.

Test data needed:

- Groups/roles list.
- Scenario owners.

Status:

- Research complete; runtime proof needed.

## Audio/video transcription

Domain:

- Transcription / STT.

Blueprint:

- [TRANSCRIPTION_STT](../blueprints/TRANSCRIPTION_STT.blueprint.md)

Research:

- [TRANSCRIPTION_STT_RESEARCH](../research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](../research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](../research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](../research/LEMONFOX_STT_RESEARCH.md)
- [STT_MEDIA_INPUT_NORMALIZATION_CONTRACT](../contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md)

Acceptance signal:

- STT proxy contract approved.
- User starts transcription and receives the result inside OpenWebUI
  chat/workspace UX.
- Audio/video media attachment exposes an explicit `Transcribe` action.
- Fully implicit/magic LLM-triggered transcription is not accepted as MVP.
- Unsupported file does not show the action or returns a safe visible error.
- The `Transcribe` action triggers browser-side normalization after explicit
  user intent.
- Input compatibility is documented as ffmpeg.wasm capability-based:
  extension/MIME are hints, and actual support requires ffmpeg probe/decode,
  audio-stream detection and normalization to an approved output profile.
- Broad source media is presented as an attempt to normalize, not guaranteed
  support for every upstream FFmpeg format.
- User sees immediate acknowledgment, progress/busy state and terminal
  success/error/cancel state.
- Result appears in the same OpenWebUI chat/message/artifact UX.
- User does not leave OpenWebUI.
- Audio/video upload produces transcript through server-side proxy without a
  separate user-facing STT GUI.
- STT API key is not present in browser.
- STT provider call goes through documented adapter/factory boundary.
- Lemonfox is first adapter, not hardwired architecture.
- Lemonfox provider capability profile is reviewed: documented formats,
  direct/URL upload limits, timestamps, speaker labels, Russian language and
  documented unknowns.
- Runtime capabilities endpoint contract is documented and does not expose
  secrets.
- Selected output profile is captured and validated; Opus candidate is proven
  before default and MP3 remains compatibility fallback.
- Input-side runtime capabilities expose accept mode, declared hints,
  ffmpeg-probe requirement and browser limits without secrets.
- STT env/config contract is reviewed without real secrets.
- Owner/operator ffmpeg proof is accepted for ADR planning.
- Optional implementation smoke checklist remains available for desktop audio,
  desktop video, mobile audio, mobile video, large WAV and large video.
- Proof matrix is not a blocking ADR or implementation-planning gate.
- Cancel UX is covered for preprocessing, upload and STT job lifecycle where
  technically possible.
- Production output profile, self-hosted ffmpeg asset path, licensing/ops,
  storage mode, retention and file-limit decisions are documented.
- Browser 1 GB input limit and Lemonfox 100 MB prepared-audio direct upload
  limit are documented.
- Lemonfox 1 GB URL input support is documented as a candidate path, but not
  approved until storage expiry/access proof exists.
- Lemonfox max duration and provider-side cancellation are either proven or
  exposed as `TBD`/unsupported.
- Prepared audio larger than 100 MB has typed fail/fallback behavior.
- Prepared audio larger than 100 MB has a warning reason code before provider
  upload.
- OpenWebUI media attachment action path is selected and proven for explicit
  trigger, prepared handoff, transcript return and basic user feedback; cancel
  remains a hardening item unless separately proven in a future run.
- Prepared-MP3 frontend MVP and browser ffmpeg.wasm broad-media normalization
  are accepted as implemented/proven MVP paths on generated proof media.

Test data needed:

- Audio.
- Video.
- Large file.
- Large WAV.
- ffmpeg source workflow/operator proof evidence.
- Optional implementation smoke media: desktop audio, desktop video, mobile
  audio, mobile video, large WAV and large video.
- Output profile compatibility notes.
- Lemonfox adapter proof.
- Runtime capabilities contract proof.
- ffmpeg input probe/normalization proof for:
  - MP3 passthrough/prepared path;
  - MP4 video with audio;
  - WebM audio/video if available;
  - unsupported file safe error;
  - no-audio-stream safe error.
- Storage mode/config decision for `auto|s3|none`.
- Prepared audio retention decision.
- Prepared audio >100 MB behavior.
- Duration-limit proof or accepted TBD.
- Provider-cancel proof or accepted unsupported/TBD behavior.
- OpenWebUI media attachment Action/files/events runtime probe on the pinned
  deployment.

Status:

- Current-stage acceptance: passed.
- Production hardening: pending.
- Prepared-MP3 OpenWebUI frontend MVP passed.
- OpenWebUI media attachment `Transcribe` Action path passed for the static
  loader MVP implementation.
- Private sidecar job routes, internal auth boundary and Lemonfox live smoke
  passed in the runtime completion evidence.
- Browser ffmpeg.wasm normalization proof passed on generated MP3 passthrough,
  MP4 with audio, WebM audio/video, unsupported fake MP4 and no-audio MP4:
  [OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md](../../reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md).
- Self-hosted ffmpeg.wasm assets are configured through
  `deploy/openwebui-static/stage2-stt-normalization.json` and served from the
  OpenWebUI static path in the implementation reports.
- Broad media support remains capability-based around the configured
  ffmpeg.wasm build and browser limits; do not claim universal FFmpeg input
  support.
- This closes the current Stage 2 STT MVP implementation stage. Remaining STT
  work is testing/hardening, not architectural discovery.
- Remaining acceptance data: mobile, low-memory browser, large/customer files,
  cancel during ffmpeg, duration-limit policy, Opus provider/default proof if
  selected, production storage/retention, transcript history/export/workflow
  and multi-user/group permission hardening.

## Broker reports / 3-НДФЛ draft analysis

Domain:

- Broker reports.

Blueprint:

- [BROKER_REPORTS_3NDFL](../blueprints/BROKER_REPORTS_3NDFL.blueprint.md)

Research:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](../research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)

Acceptance signal:

- User gets structured draft with manual-review warnings.

Test data needed:

- Broker reports.
- Claude good-result example.

Status:

- Blocked by customer input.

## Web-search for all with rules and limits

Domain:

- Web-search.

Blueprint:

- [WEB_SEARCH](../blueprints/WEB_SEARCH.blueprint.md)

Research:

- [WEB_SEARCH_PROVIDERS_RESEARCH](../research/WEB_SEARCH_PROVIDERS_RESEARCH.md)
- [WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20](../research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md)

Contracts / decisions:

- [ADR-0007 Web Search Provider](../decisions/ADR-0007-web-search-provider.md)
- [WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT](../contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md)
- [WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT](../contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md)
- [WEB_SEARCH_USAGE_EVENT_CONTRACT](../contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md)
- [OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY](../contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md)

Acceptance signal:

- Provider ADR is proposed for owner review or accepted for pilot.
- Provider key path is approved and server-side only.
- Provider keys are not visible in browser responses, frontend config,
  localStorage/sessionStorage or runtime reports.
- Raw sensitive queries and raw result bodies are not logged by default.
- Result count is documented and starts low.
- Search concurrency is documented and starts low.
- Web Search can be enabled/disabled by approved group or the native gap is
  recorded.
- Russian/English safe smoke queries work.
- Source links/cards are visible for grounded answers.
- Quota, timeout, no-results and policy-blocked errors are visible.
- Forbidden examples are documented.
- Analytics/cost visibility path is documented or the native gap is explicitly
  accepted.
- If private SearXNG is used, JSON API returns valid JSON and the instance is
  internal-only by default.
- If private SearXNG is used, upstream-engine query leakage is documented and
  accepted by owner.
- Brave and SearXNG comparison uses the same query set.
- Candidate set is captured before final answer generation.
- Final answer is captured separately from the candidate set.
- Candidate source, loaded/extracted source and evidence used in answer are
  distinguished where native OpenWebUI evidence allows it.
- SearXNG is not promoted from comparison track until candidate quality,
  answer groundedness, latency, source visibility and log/privacy evidence pass.

Test data needed:

- 5-10 Russian safe queries.
- 3-5 English safe queries.
- 3-5 forbidden sensitive examples.
- 2 freshness-sensitive examples.
- 2 conflicting-source examples.
- 2 no-sufficient-evidence examples.
- Expected source/citation behavior.
- Provider key through approved secret path only.
- For SearXNG: direct JSON API smoke query and allowed upstream engine list.
- Brave vs SearXNG comparison query matrix.
- Candidate-set capture format: URL, title, snippet, source engine/provider,
  rank/score and freshness metadata where available.

Status:

- Documentation domain ready.
- Provider ADR proposed for owner review.
- Private SearXNG compose/config plan ready for runtime smoke as a comparison
  track.
- Runtime live probe blocked by missing deployed/staging access, provider
  credentials and owner provider approval.

## PDF/DOCX/XLSX basic handling and OCR pilot

Domain:

- Documents / OCR / Excel.

Blueprint:

- [DOCUMENTS_OCR_EXCEL](../blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)

Research:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](../research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [VL_OCR_PROVIDER_RESEARCH](../research/VL_OCR_PROVIDER_RESEARCH.md)

Acceptance signal:

- Simple docs work.
- Scan/complex PDF gets OCR/VL OCR pilot result or documented limitation.
- Results are classified by document type.

Test data needed:

- PDF.
- Scanned PDF.
- PDF tables.
- DOCX.
- XLSX.
- Poor scan/photo.
- Expected output.

Status:

- Research complete; samples needed.

## VL OCR pilot candidate selection

Domain:

- Documents / OCR / VL OCR.

Blueprint:

- [DOCUMENTS_OCR_EXCEL](../blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)

Research:

- [VL_OCR_PROVIDER_RESEARCH](../research/VL_OCR_PROVIDER_RESEARCH.md)

Acceptance signal:

- VL OCR candidate list selected.
- Pilot test set collected before implementation.

Test data needed:

- Scanned broker report.
- Photo document.
- PDF with stamps/signatures.
- Tables.
- Allowed-provider decision.

Status:

- Planned; blocked by customer samples.

## Provider model catalog

Domain:

- Providers.

Blueprint:

- [PROVIDERS_MODEL_CATALOG](../blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)

Research:

- [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](../research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)

Acceptance signal:

- Catalog lists production/research/rejected/deferred providers.
- Exact model IDs, use cases and limits are documented.

Test data needed:

- Provider access.
- Model IDs.
- Data policy.

Status:

- Research complete; catalog ADR needed.

## Basic analytics / cost visibility

Domain:

- Usage analytics.

Blueprint:

- [USAGE_ANALYTICS_AND_COSTS](../blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md)

Research:

- [USAGE_ANALYTICS_BILLING_RESEARCH](../research/USAGE_ANALYTICS_BILLING_RESEARCH.md)

Acceptance signal:

- Admin sees usage or documented gap.
- Hard billing decision is separated.

Test data needed:

- Test users.
- Sample usage.

Status:

- Research complete; runtime proof needed.

## Data policy and no false masking promise

Domain:

- Security / data policy.

Blueprint:

- [SECURITY_DATA_POLICY](../blueprints/SECURITY_DATA_POLICY.blueprint.md)

Research:

- [DATA_MASKING_FUTURE_RESEARCH](../research/DATA_MASKING_FUTURE_RESEARCH.md)
- [ADR-0001](../decisions/ADR-0001-data-policy-by-provider-class.md)

Acceptance signal:

- Data Policy ADR approved.
- Policy distinguishes foreign/RU/local providers.
- Masking remains a future slice.

Test data needed:

- Allowed/prohibited data examples.

Status:

- Research complete; policy decision needed before provider setup.

## Manager work-chat visibility

Domain:

- Manager visibility.

Blueprint:

- [MANAGER_VISIBILITY_AND_RETENTION](../blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)

Research:

- [RBAC_MANAGER_VISIBILITY_RESEARCH](../research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)
- [ADR-0002](../decisions/ADR-0002-manager-visibility-policy.md)

Acceptance signal:

- Manager Visibility matrix approved.
- Manager sees only approved work chats or limitation/options are documented.

Test data needed:

- Groups.
- Privacy policy examples.
- Test users.

Status:

- Research complete; runtime/customer proof needed.

## Chat deletion restriction check

Domain:

- No-delete policy.

Blueprint:

- [MANAGER_VISIBILITY_AND_RETENTION](../blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)

Research:

- [CHAT_DELETION_RETENTION_RESEARCH](../research/CHAT_DELETION_RETENTION_RESEARCH.md)
- [ADR-0003](../decisions/ADR-0003-chat-deletion-retention-audit.md)

Acceptance signal:

- No Delete UI/API proof completed for non-admin.
- Admin override is documented.

Test data needed:

- Test users.
- Test chats.

Status:

- Research complete; runtime proof needed.

## Retention policy decision

Domain:

- Retention / audit.

Blueprint:

- [MANAGER_VISIBILITY_AND_RETENTION](../blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)

Research:

- [CHAT_DELETION_RETENTION_RESEARCH](../research/CHAT_DELETION_RETENTION_RESEARCH.md)
- [ADR-0003](../decisions/ADR-0003-chat-deletion-retention-audit.md)

Acceptance signal:

- Retention policy decision documented separately from no-delete and audit/archive.

Test data needed:

- Retention requirements for chats, files, transcripts and backups.

Status:

- Policy decision needed.

## Ops and acceptance handoff

Domain:

- Operations / acceptance.

Blueprint:

- [OPS_AND_ACCEPTANCE](../blueprints/OPS_AND_ACCEPTANCE.blueprint.md)

Research:

- [OPENWEBUI_CAPABILITY_RESEARCH](../research/OPENWEBUI_CAPABILITY_RESEARCH.md)

Acceptance signal:

- Final acceptance checklist passes without secrets in docs/git.

Test data needed:

- All domain test data.

Status:

- Planned after ADRs.
