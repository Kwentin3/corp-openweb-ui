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

Acceptance signal:

- STT proxy contract approved.
- User starts transcription and receives the result inside OpenWebUI
  chat/workspace UX.
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
- OpenWebUI-native integration path is selected and proven for trigger, file
  handoff, transcript return, progress and cancel.

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
- Storage mode/config decision for `auto|s3|none`.
- Prepared audio retention decision.
- Prepared audio >100 MB behavior.
- Duration-limit proof or accepted TBD.
- Provider-cancel proof or accepted unsupported/TBD behavior.
- OpenWebUI Action/OpenAPI/files/events runtime probe on the pinned deployment.

Status:

- Transferable ffmpeg contract inspected; owner/operator proof accepted for
  planning; OpenWebUI-native UX research complete; runtime probe, ADR review,
  selected output profile config, self-hosted asset path, storage mode/config,
  retention, duration and cancel TBD handling needed.

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

Acceptance signal:

- Russian/English smoke queries work.
- Result count, concurrency and policy are documented.

Test data needed:

- Web-search task examples.
- Provider key.

Status:

- Research complete; provider ADR needed.

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
