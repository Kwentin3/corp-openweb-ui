# Stage 2 Engineering Backlog

Это planning backlog, не issue tracker. Research выполнен 2026-06-18; STT
implementation proof was added on 2026-06-19. Status lines below distinguish
completed implementation proof from remaining decision/planning work.

## Delivery rule

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs.
Frontend/UI work follows after backend contracts are clear.

Frontend must not become the place where security, provider keys, data policy, retention rules or
access rules are decided.

Provider setup must not start before data policy by provider class is approved.

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom Stage 2 logic should live
in bounded domain services, internal APIs, or thin integration shims.

OpenWebUI-facing features should follow the extension-first implementation
pattern before any fork: native mechanisms, Functions/Actions/Tools, thin
static/UI shim, private backend sidecar, then fork only after proof and
owner/ADR approval.

STT user-facing UX must live inside OpenWebUI. The sidecar is backend-only; do
not plan a separate STT user GUI. MVP trigger is an explicit `Transcribe`
action on an audio/video media attachment, not magic LLM inference.

Boundary reference: [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).

Pattern reference:
[EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md).

## Ready to start without new customer approval

These items are documentation, skeleton, research, benchmark-plan and proof-plan
work. They do not change runtime, do not use customer data and do not close
customer gates.

Reference:
[STAGE2_UNBLOCKED_WORK_PLAN.md](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md).

Context routing:
[CONTEXT_USAGE_RULES.md](CONTEXT_USAGE_RULES.md). Backlog status does not
override implementation gates, approved ADR status or customer-data boundaries.

### Workspace scenario user stories

Domain: Workspaces / RBAC / prompts / Knowledge
Output:
[WORKSPACE_SCENARIO_USER_STORIES.md](implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
and follow-up scenario drafts.
Depends on: PRD-1, native capability audit, synthetic data index.
Status: ready for documentation / ready to start. Real groups, owners and
customer workflows remain customer input.

### Selected story proof prep package

Domain: Workspaces / STT workflow / Web Search / analytics / OCR
Output:
[STAGE2_SELECTED_USER_STORIES.md](implementation/STAGE2_SELECTED_USER_STORIES.md),
[STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md](testdata/STAGE2_SELECTED_STORIES_SYNTHETIC_DATA_REQUIREMENTS.md)
и
[STAGE2_SELECTED_STORIES_PROOF_PLANS.md](implementation/STAGE2_SELECTED_STORIES_PROOF_PLANS.md).
Depends on: scenario shortlist, workspace user stories and synthetic data
index.
Status: prepared as docs-only package for `ST2-US-001`, `ST2-US-002`,
`ST2-US-003`, `ST2-US-009` and `ST2-US-011`. `ST2-US-013` remains a marker
but proof execution is paused under the OCR / VL OCR Infrastructure &
Provider Benchmark Epic. Runtime proof и создание synthetic files требуют
отдельного согласования.

### Synthetic test data pack

Domain: Acceptance / test data / proof planning
Output:
[SYNTHETIC_TEST_DATA_INDEX.md](testdata/SYNTHETIC_TEST_DATA_INDEX.md)
and later explicitly synthetic files if approved.
Depends on: acceptance matrix and test data requirements.
Status: ready to start. Synthetic data supports mechanical proof only; it does
not replace customer samples.

### Usage analytics proof

Domain: Usage analytics / costs
Output: proof plan for user/day/week/model/token/message and approximate-cost
breakdown, plus native gap list if OpenWebUI analytics is insufficient.
Depends on: native analytics endpoint proof, provider price catalog skeleton.
Status: next independent proof. Hard billing/gateway remains a separate
customer decision.

### OCR / VL OCR Infrastructure & Provider Benchmark Epic

Domain: Documents / OCR / VL OCR
Output: handoff context, provider shortlist research, input/output contract
draft, error/limitation contract and synthetic benchmark plan.
Depends on: OCR/VL OCR context pack, VL OCR provider research, documents/OCR
research, data policy and synthetic test data index.
Status: corrected provider shortlist research V2 complete; benchmark plan and
adapter contracts next. No runtime/provider setup yet.

### VL OCR candidate research + synthetic benchmark

Domain: Documents / OCR / VL OCR
Output: candidate shortlist and synthetic benchmark plan.
Depends on: VL OCR provider research, documents/OCR/Excel research and
synthetic test data index.
Status: folded under OCR / VL OCR Infrastructure & Provider Benchmark Epic.
Corrected provider shortlist research V2 is complete. Benchmark execution waits
for contracts and benchmark plan. Customer OCR pilot and production acceptance
remain blocked by real documents and provider/data policy.

### Simple document extraction synthetic proof

Domain: Documents / PDF / DOCX / XLSX
Output: mechanical proof plan for simple PDF/DOCX/XLSX synthetic files.
Depends on: synthetic test data index.
Status: ready after synthetic data index. Real broker reports, scans and
complex Excel remain customer-blocked.

### Configuration-first scenario proof

Domain: Workspaces / RBAC / prompts / Knowledge
Output: proof plan for group, Workspace Model, shared prompt, Knowledge and
actor matrix using synthetic resources.
Depends on: workspace scenario user stories and synthetic test data index.
Status: ready after user stories and synthetic data. Runtime proof still needs
separate approval.

## Current-stage closed / proven

### Stage 2 STT MVP

Domain: Transcription / STT
Source: runtime, frontend media action, ffmpeg normalization and Playwright
proof reports from 2026-06-19
Why: The owner accepts the current feature as correctly closed for this stage;
further work is testing/hardening.
Implemented path:

```text
OpenWebUI media attachment -> static loader Transcribe action ->
browser ffmpeg.wasm normalization -> OpenWebUI Action Function ->
private stage2-stt sidecar -> Lemonfox adapter -> transcript returned to
OpenWebUI composer/chat UX
```

Completed/proven:

- sidecar backend foundation;
- private job routes/internal auth;
- Lemonfox adapter/live smoke;
- OpenWebUI Action Function path;
- static loader `Transcribe` button;
- prepared MP3 path;
- browser ffmpeg.wasm normalization;
- MP4 video with audio proof;
- WebM audio/video proof;
- unsupported media safe error;
- no-audio safe error;
- self-hosted ffmpeg.wasm assets.

Status: implemented/proven/current-stage closed; ready for broader testing.

Sticky instruction: do not re-plan STT from zero, do not fork OpenWebUI without
proven necessity, and do not treat the sidecar as a user-facing GUI.

### Native mobile microphone dictation issue

Domain: Transcription / STT / OpenWebUI native microphone UX
Source:
[OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md](../reports/2026-06-23/OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md)
Why: On mobile, native chat microphone dictation can show the recording
waveform but produce no audio transcription and stop after about five seconds.
The current live config uses `audio.stt.engine = web`, so this path is browser
Web Speech API dictation, separate from the Stage 2 attachment `Transcribe`
Action/sidecar path.
Output: mobile browser event/network trace for `SpeechRecognition`
(`onstart`, `onresult`, `onerror`, `onend`) and a product decision: either keep
Web API microphone as desktop/convenience only with explicit mobile feedback, or
route mobile microphone recordings through server-side STT.
Depends on: real failing mobile device/browser trace.
Status: known runtime issue; diagnostic audit complete; no code fix selected.

## Ready for ADR

### Contract boundaries and domain isolation

Domain: Cross-domain architecture
Source: CONTRACT_BOUNDARIES, DOMAIN_MAP, ROADMAP, PRD-1
Why: STT, OCR, web-search, manager visibility, retention and usage analytics can drift if UI,
provider glue and OpenWebUI core all own decisions implicitly.
Output: versioned internal contracts and proof gates before implementation slices.
Depends on: ADR review and runtime proof
Status: documented; enforce before implementation planning

### Data policy by provider class

Domain: Security / data policy / providers
Source: SECURITY_DATA_POLICY blueprint, DATA_MASKING_FUTURE_RESEARCH, PRD-1
Why: Provider setup and document/transcript workflows depend on allowed/prohibited data classes.
Output: ADR-0001 with provider classes, data classes, draft allowed/prohibited matrix and customer
questions.
Depends on: customer/security approval
Status: ready for ADR; required before provider setup

### STT proxy boundary

Domain: Transcription / STT
Source: TRANSCRIPTION_STT blueprint, TRANSCRIPTION_STT_RESEARCH, LEMONFOX_STT_RESEARCH,
FFMPEG_BROWSER_WORKFLOW_RESEARCH, FFMPEG_WORKFLOW_ARTIFACT_INSPECTION
Why: API keys cannot be exposed in browser; Lemonfox-specific capabilities and ffmpeg preprocessing
need server-side control.
Output: proposed ADR for proxy contract, auth/permissions, upload limits, storage, errors, provider
adapter factory, provider capability profile, runtime capabilities endpoint, capability-based input
normalization contract, output profiles, response normalization, optional audit and draft job
contracts.
Depends on: human ADR review, owner decisions, STT env contract review, Lemonfox capability
profile review, output-profile config, production dependency decisions, customer media limits
Status: ADR-0004 prepared for review; external ffmpeg workflow contract inspected; transferable
MP3/audio-mpeg source-proven fallback found; operator manual proof captured as manual evidence;
Lemonfox selected as first adapter; official docs confirm 100 MB direct upload and 1 GB URL input
but leave exact Opus containers, max duration and provider cancel undocumented; owner/operator proof
is accepted for planning; private sidecar job routes, internal auth boundary, Lemonfox live smoke,
prepared-MP3 frontend MVP, OpenWebUI Action path and browser normalization proof have passed.
Browser normalization proof covers generated MP3 passthrough, MP4 with audio, WebM audio/video,
unsupported fake MP4 and no-audio MP4. Remaining production decisions are Opus/provider proof,
storage mode/config, prepared-audio retention, large-file behavior, duration policy and cancel UX
behavior. Broad media support must still be described as configured ffmpeg.wasm capability-based,
not universal FFmpeg support.

### Provider model catalog

Domain: Providers / models
Source: PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH
Why: Users need curated models; vague `GPT-mini` and Claude Code confusion must be removed before
setup.
Output: catalog with exact model IDs, use cases, costs, data policy, production/research/rejected
labels.
Depends on: ADR-0001 data policy, customer provider accounts
Status: ready for ADR after data policy draft

### Web-search provider

Domain: Web-search
Source: WEB_SEARCH_PROVIDERS_RESEARCH, existing infra web-search research
Why: Web-search нужен всем, но provider choice affects cost/privacy and Russian-provider stance.
Output: provider ADR/runtime status covering Brave first pilot, Yandex Search
as a working RU-provider path after Admin UI/native smoke, and
self-hosted/external comparison options, with limits and prohibited-query
examples.
Depends on: data policy, customer privacy/cost approval, smoke queries
Status: Brave and Yandex native smokes passed; rollout governance still open
data policy, customer privacy/cost approval and group scope.

### Vectorized Web Search retrieval path

Domain: Web-search / retrieval / page loading
Source:
[OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md](../reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md),
[WEB_SEARCH_CONTEXT_INDEX.md](WEB_SEARCH_CONTEXT_INDEX.md)
Why: Runtime diagnostics showed that OpenWebUI can create `web-search-*`
collections from search results, but follow-up vectorized retrieval can return
`0` sources after successful search and embedding. The current working Brave
baseline bypasses this extra path and passes `brave_llm_context` evidence
directly to the LLM.
Output: focused fix/proof for
`search -> web-search-* vector collection -> retrieval sources -> LLM context`,
including collection ownership/session scope, chunk metadata, source retrieval
query, and visible source attribution.
Depends on: a real product need for long page loading, classic `brave`, SearXNG
page loading, or full RAG over fetched content.
Status: known deferred runtime issue; do not block the current Brave
`brave_llm_context` baseline or SearXNG candidate-set comparison on it.

### Manager visibility policy

Domain: RBAC / manager visibility
Source: RBAC_MANAGER_VISIBILITY_RESEARCH, MANAGER_VISIBILITY_AND_RETENTION blueprint
Why: Manager access is a policy/security-controlled capability, not a simple permission toggle.
Output: ADR-0002 with work-chat visibility boundaries, actor matrix and runtime proof plan.
Depends on: customer/admin privacy policy, test users/groups
Status: ready for ADR; runtime proof required

### Chat deletion / retention / audit

Domain: Retention / no-delete / audit
Source: CHAT_DELETION_RETENTION_RESEARCH, MANAGER_VISIBILITY_AND_RETENTION blueprint
Why: No Delete, Retention, Audit and immutable archive are separate decisions.
Output: ADR-0003 with native proof plan, retention questions and fallback options.
Depends on: customer retention policy, deployed/staging runtime proof
Status: ready for ADR; runtime proof required

### OCR / VL OCR pilot scope

Domain: Documents / OCR / Excel
Source: DOCUMENTS_OCR_EXCEL_RESEARCH, VL_OCR_PROVIDER_RESEARCH
Why: OCR pilot is in Practical Stage 2; production pipeline is not. VL OCR may help with
scans/images/complex PDFs but must be benchmarked.
Output: ADR or decision note for pilot candidate list, test set, evaluation criteria and
document-type classification.
Depends on: customer samples and data policy
Status: waiting for customer test data; ready for ADR skeleton
and synthetic benchmark planning. Customer pilot remains blocked by real
documents and provider/data policy.

### Native analytics vs hard billing

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Basic analytics may be enough; gateway must not be assumed.
Output: ADR-0008 native analytics vs hard billing decision.
Depends on: deployed analytics proof, provider catalog
Status: ready for decision after runtime proof

## Ready for research

### VL OCR provider/candidate evaluation

Domain: Documents / OCR / Excel
Source: VL_OCR_PROVIDER_RESEARCH,
VL_OCR_API_PROVIDER_SHORTLIST_RESEARCH_V2
Why: Need to compare dedicated OCR-VL/VLM document parsing APIs, hosted
PaddleOCR-VL and baseline-only OCR/Document AI before promising OCR quality.
Output: short candidate shortlist and pilot plan for 2-3 candidates.
Depends on: customer data policy and sample documents
Status: corrected provider shortlist research V2 artifact created; synthetic
benchmark planning can start; customer pilot candidate choice remains blocked
by samples and data policy

## Ready for runtime proof

### OpenWebUI native capability audit

Domain: Workspaces / RBAC / analytics / files
Source: OPENWEBUI_CAPABILITY_RESEARCH,
[OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md](../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md),
[OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md](../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md),
[OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
Why: Current docs may not match deployed v0.9.6, and Stage 2 needs a
configuration-first proof path before implementation.
Output: initial capability audit completed with public runtime proof,
native-fit matrix and authenticated four-actor synthetic proof.
Depends on: customer decisions for no-delete, manager visibility, Web Search
scope and analytics expectations
Status: public runtime version/health/static proof captured on 2026-06-24;
authenticated admin API proof captured on 2026-06-24 via approved local `.env`
variable names without printing values. A later 2026-06-24 synthetic run
created temporary `stage2-proof-*` actors/resources, completed the four-actor
matrix, and deleted all proof entities. Remaining gaps are no-delete,
manager positive visibility, Web Search scoped-default policy and immediate
synthetic analytics rows.

### OpenWebUI media attachment transcription action proof

Domain: Transcription / STT / OpenWebUI UX
Source: STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN,
OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH, ADR-0004, STT backend
implementation plan
Why: Users must launch and consume transcription from a visible media
attachment action inside OpenWebUI, while Stage2 STT sidecar remains
backend-only.
Output: historical runtime proof for Action Function / media attachment action
on pinned OpenWebUI version.
Subtasks:
- Action Function probe;
- file metadata/bytes probe;
- ffmpeg.wasm attachment normalization decision;
- dummy sidecar call;
- progress events;
- transcript placement;
- cancel semantics;
- final integration path decision.
Depends on: admin/staging access, sample media, approved auth boundary.
Status: current-stage closed for the MVP static loader path. Keep future work
scoped to progress/cancel/access-policy hardening, transcript workflow,
mobile/large-file proof and regression coverage.

### RBAC/groups proof

Domain: Workspaces / RBAC
Source: OPENWEBUI_CAPABILITY_RESEARCH, WORKSPACES_AND_RBAC blueprint
Why: Groups/RBAC are core to Stage 2 workspaces, manager visibility and model access.
Output: test users/groups proof with exact settings and visible resources.
Depends on: staging/admin access, group matrix
Status: ready for runtime proof

### Native analytics proof

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Need evidence that deployed analytics is sufficient for basic reporting.
Output: screenshots/notes for two users/groups/models and cost estimation workflow.
Depends on: test users and sample usage
Status: ready for runtime proof

### Web-search smoke

Domain: Web-search
Source: WEB_SEARCH_PROVIDERS_RESEARCH, ADR-0007
Why: Web-search for all users requires provider, result count, concurrency and
cost proof.
Output: smoke results for approved Russian/English queries, including current
Brave baseline and Yandex RU-provider path, plus documented gaps.
Depends on: ADR-0007, provider account/key path, allowed query examples
Status: Brave and Yandex admin/manual smokes passed; EN matrix, permission
scope, logging/retention and cost visibility still need rollout proof.

### STT proxy smoke proof / hardening data

Domain: Transcription / STT
Source: TRANSCRIPTION_STT blueprint, ADR-0004
Why: STT proxy must stay proven while production hardening expands.
Output: follow-up hardening data for audio/video, key handling, errors,
size/duration and transcript shape.
Depends on: approved ADR-0004, inspected ffmpeg contract, sample media
Status: current-stage smoke is proven in the 2026-06-19 reports. Keep desktop
video, mobile audio, mobile video, large WAV and large video checks, selected
Opus profile proof if promoted, prepared audio >100 MB behavior, storage mode
behavior, duration limit behavior and provider-cancel unknown/unsupported
handling as follow-up acceptance/hardening data.

### STT env/config contract review

Domain: Transcription / STT / configuration
Source: ADR-0004, STT_ENV_CONTRACT
Why: Stage 2 STT provider, output profile, ffmpeg asset mode, storage, limits and cancel behavior
must be configured server-side without exposing secrets to browser.
Output: reviewed draft env contract for Lemonfox, input accept mode, declared input hints,
ffmpeg probe requirements, output profiles, self-hosted ffmpeg assets, storage mode
`auto|s3|none`, retention, limits, runtime capabilities and cancel flags.
Depends on: ADR-0004 review, data policy, ops/storage decision.
Status: ready for review; not a real `.env.example`

### FFMPEG implementation smoke checklist

Domain: Transcription / STT
Source: ADR-0004, FFMPEG_WORKFLOW_ARTIFACT_INSPECTION
Why: Owner/operator proof is accepted for planning; implementation/debug still benefits from a
small smoke checklist.
Output: optional smoke evidence for desktop audio, desktop video, mobile audio, mobile video,
large WAV and large video.
Depends on: implementation slice and approved test media.
Status: optional implementation/debug smoke; not a blocking ADR gate

### Browser ffmpeg.wasm input normalization hardening

Domain: Transcription / STT / frontend preprocessing
Source: STT_MEDIA_INPUT_NORMALIZATION_CONTRACT, ADR-0004, STT_ENV_CONTRACT
Why: Broad media input support is capability-based and cannot be claimed from a
static extension list.
Output: hardening for browser ffmpeg.wasm probe/decode, audio-stream detection,
normalization to selected output profile, progress events and typed safe
errors.
Depends on: approved ffmpeg asset path, input accept mode env, runtime capabilities endpoint,
representative media.
Acceptance: Playwright proof for MP3 prepared/passthrough path, MP4 video with audio, WebM
audio/video if available, unsupported file safe error and no-audio-stream safe error.
Status: implemented/proven/current-stage closed on generated proof media; keep
customer/large/mobile media checks as follow-up acceptance data

### FFMPEG production dependency decisions

Domain: Transcription / STT / frontend dependency
Source: ADR-0004, FFMPEG_WORKFLOW_ARTIFACT_INSPECTION
Why: Source workflow uses `unpkg.com`, `@ffmpeg/ffmpeg` v0.12.6 and MP3 / `libmp3lame`; corporate
production needs explicit dependency, hosting, licensing and limit decisions.
Output: decision note or ADR update for Opus default candidate, MP3 fallback, `self_hosted`
production asset path, licensing/ops review, Lemonfox adapter compatibility and max
file size/duration policy.
Depends on: ADR-0004 review, STT provider compatibility smoke, ops/licensing review.
Status: blocked by production decision

### STT prepared audio storage and retention

Domain: Transcription / STT / storage
Source: ADR-0004, STT_ENV_CONTRACT
Why: Normalized/prepared audio sent to provider may need controlled S3/object storage, while source
media storage must not be enabled silently.
Output: storage mode decision for `auto|s3|none`, S3 bucket/prefix/retention decision when used,
storage health behavior, prepared-audio cleanup policy, source-media storage flag and
cancelled-job retention behavior.
Depends on: data policy, retention policy, operator storage configuration.
Status: blocked by storage/retention decision

### STT runtime capabilities endpoint

Domain: Transcription / STT / configuration
Source: ADR-0004, STT_ENV_CONTRACT
Why: UI must show input affordance hints, output profiles, size warnings, duration limits, storage
mode and cancel affordances from backend truth, not hardcoded Lemonfox assumptions.
Output: `TranscriptionRuntimeCapabilitiesV1` and
`GET /stage2-api/transcription/capabilities` contract without secrets.
Depends on: ADR-0004 review, env/config contract review.
Status: implemented on the private `stage2-stt` sidecar; public OpenWebUI route
is not exposed as sidecar JSON. Keep contract review for future UI-safe dynamic
capabilities integration.

### Document extraction/OCR smoke after test data

Domain: Documents / OCR / VL OCR / Excel
Source: DOCUMENTS_OCR_EXCEL_RESEARCH, ADR-0005
Why: OCR/VL OCR quality must be proven on customer documents.
Output: extraction preview and per-document-class classification.
Depends on: ADR-0005, data policy approval, customer documents
Status: blocked by customer test data

### Manager visibility runtime proof

Domain: Manager visibility / RBAC
Source: RBAC_MANAGER_VISIBILITY_RESEARCH, ADR-0002
Why: Need to prove controlled work-chat visibility without exposing unrelated personal/draft chats.
Output: matrix proof for Admin, Manager/РО, employee inside group and employee outside group.
Depends on: test users/groups and customer policy draft
Status: ready for runtime proof after ADR-0002 draft

### Chat deletion permission proof

Domain: Retention / no-delete policy
Source: CHAT_DELETION_RETENTION_RESEARCH, ADR-0003
Why: Native no-delete is plausible but unproven.
Output: non-admin UI/API delete proof, additive-permission check and admin override check.
Depends on: test user matrix
Status: ready for runtime proof after ADR-0003 draft

## Ready for implementation planning after ADRs

### STT backend implementation plan

Domain: Transcription / STT / backend
Source: ADR-0004, STT_ENV_CONTRACT, TRANSCRIPTION_STT blueprint
Why: First backend slice needs a compact start package before code discovery and implementation.
Output: backend implementation plan with context docs, contracts, endpoints, env keys, discovery
plan, implementation slices and stop conditions.
Depends on: ADR-0004 review, Stage 2 STT env/config contract and passed
OpenWebUI media attachment action probe.
Status: initial backend sidecar/job-route implementation completed and proven
for the MVP path; plan retained as historical traceability. Remaining backend
work is storage/retention, large-file/URL upload policy, duration/cancel
hardening and transcript lifecycle.

### Workspace scenario setup plan

Domain: Workspaces / RBAC
Source: WORKSPACES_AND_RBAC blueprint, OPENWEBUI_CAPABILITY_RESEARCH
Why: Configuration-first domain likely can be planned early after runtime proof.
Output: implementation slices for groups, prompts, knowledge and access.
Depends on: groups/roles from customer, native capability audit, data policy warnings
Status: pending customer input and runtime proof

### Acceptance and test data package

Domain: Operations / acceptance
Source: ACCEPTANCE_MATRIX, TEST_DATA_REQUIREMENTS
Why: Implementation without test data will drift.
Output: approved test data checklist and acceptance sequence.
Depends on: customer files and users
Status: ready for planning

## Blocked by customer input

### Broker report test set

Domain: Broker reports / documents
Source: PRD-1
Why: Scenario quality cannot be validated on imaginary documents.
Output: anonymized broker reports and expected result examples.
Depends on: customer
Status: blocked by customer input

### OCR/scanned document samples

Domain: Documents / OCR / VL OCR
Source: DOCUMENTS_OCR_EXCEL blueprint, VL_OCR_PROVIDER_RESEARCH
Why: OCR/VL OCR quality must be classified by document type.
Output: scanned broker report, photo document, PDF with tables, PDF with stamps/signatures, poor
scan and expected output sample.
Depends on: customer
Status: blocked by customer input

### Example good Claude result

Domain: Broker reports / documents
Source: PRD-1, customer summary
Why: Need a concrete target for broker-report output quality.
Output: sanitized example of current good output from Claude API / Claude models or manual sample.
Depends on: customer
Status: blocked by customer input

### Groups and manager visibility policy

Domain: RBAC / manager visibility
Source: PRD-1, RBAC_MANAGER_VISIBILITY_RESEARCH, ADR-0002
Why: Access model depends on actual departments and privacy stance.
Output: approved group matrix and visibility policy.
Depends on: customer/admin
Status: blocked by customer input

### Provider/data policy approval

Domain: Providers / security
Source: PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH, DATA_MASKING_FUTURE_RESEARCH, ADR-0001
Why: Provider setup must follow allowed-data policy.
Output: provider allowlist and prohibited data examples.
Depends on: customer/admin/security
Status: blocked by customer input

### Provider accounts and access

Domain: Providers / web-search / STT
Source: provider research docs
Why: Runtime smoke cannot run without approved keys/accounts, but keys must not be committed or
printed.
Output: operator confirmation of available accounts and safe smoke procedure.
Depends on: customer/operator
Status: blocked by customer input

### Audio/video files

Domain: Transcription / STT
Source: TRANSCRIPTION_STT blueprint, TEST_DATA_REQUIREMENTS
Why: STT proxy and ffmpeg workflow cannot be accepted without representative media.
Output: approved audio/video samples, large file sample and expected transcript shape.
Depends on: customer
Status: blocked by customer input

### Scanned PDF, PDF with tables and XLSX

Domain: Documents / OCR / Excel
Source: DOCUMENTS_OCR_EXCEL blueprint, TEST_DATA_REQUIREMENTS
Why: Document/OCR acceptance must use real document classes.
Output: scanned PDF, PDF with tables, XLSX and expected outputs.
Depends on: customer
Status: blocked by customer input

### Data policy examples

Domain: Security / data policy
Source: ADR-0001, SECURITY_DATA_POLICY blueprint
Why: Provider/data policy cannot be approved without concrete allowed/prohibited examples.
Output: examples for foreign providers, Russian providers, local/self-hosted path and future masked
path.
Depends on: customer/security
Status: blocked by customer input

## Deferred / future slices

### Full data masking/tokenization subsystem

Domain: Security / data policy
Source: DATA_MASKING_FUTURE_RESEARCH
Why: Requires detection, mapping store, reverse substitution and leak tests.
Output: future security architecture, not Stage 2 implementation.
Depends on: separate approval
Status: deferred

### Local LLM/NER for sensitive data

Domain: Security / data policy
Source: DATA_MASKING_FUTURE_RESEARCH
Why: Reliable Russian financial/legal entity detection may require local model/NER work.
Output: future masking architecture option.
Depends on: separate approval
Status: deferred

### Production-grade OCR/layout pipeline

Domain: Documents / OCR
Source: DOCUMENTS_OCR_EXCEL_RESEARCH, VL_OCR_PROVIDER_RESEARCH
Why: Pilot first; production pipeline requires queue, validation, audit and human review.
Output: future architecture decision after pilot.
Depends on: OCR/VL OCR pilot evidence
Status: deferred

### Complex Excel parser

Domain: Documents / Excel
Source: DOCUMENTS_OCR_EXCEL_RESEARCH
Why: Accurate formulas, multiple sheets, pivots and external links require parser/tool decisions.
Output: future parser/tool architecture.
Depends on: customer XLSX complexity evidence
Status: deferred

### Production DOCX/XLSX generation

Domain: Documents / export
Source: PRD-1
Why: Controlled generation requires templates, validation and versioned output.
Output: future template/export architecture.
Depends on: separate approval
Status: deferred

### Immutable audit archive

Domain: Retention / audit
Source: CHAT_DELETION_RETENTION_RESEARCH, ADR-0003
Why: No-delete and backups do not create immutable legal/audit archive.
Output: future audit/retention architecture.
Depends on: separate legal/security requirement
Status: deferred

### Hard billing/gateway

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Hard budgets require gateway-level architecture.
Output: future gateway ADR if native analytics insufficient.
Depends on: cost visibility research and customer requirement
Status: deferred unless hard budgets are required

### Full AD lifecycle / SCIM

Domain: Identity / access
Source: PRD-1
Why: Practical Stage 2 keeps AD/SSO as optional discovery, not full lifecycle rollout.
Output: separate identity slice.
Depends on: customer infrastructure discovery
Status: deferred

### Deep OpenWebUI fork

Domain: Platform customization
Source: PRD-1 non-goals
Why: Practical Stage 2 favors native OpenWebUI and isolated integration slices first.
Output: future fork rationale and maintenance plan if unavoidable.
Depends on: proof that native/configuration/integration path is insufficient
Status: deferred
