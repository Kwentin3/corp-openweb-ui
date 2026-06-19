# Stage 2 Engineering Backlog

Это planning backlog, не issue tracker. Research выполнен 2026-06-18; следующие элементы являются
decision/planning work, не implementation.

## Delivery rule

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs.
Frontend/UI work follows after backend contracts are clear.

Frontend must not become the place where security, provider keys, data policy, retention rules or
access rules are decided.

Provider setup must not start before data policy by provider class is approved.

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom Stage 2 logic should live
in bounded domain services, internal APIs, or thin integration shims.

Boundary reference: [CONTRACT_BOUNDARIES.md](CONTRACT_BOUNDARIES.md).

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
adapter factory, output profiles, response normalization, optional audit and draft job contracts.
Depends on: human ADR review, STT env contract review, lightweight proof matrix, Lemonfox/Opus
compatibility proof, production dependency decisions, customer media limits
Status: ADR-0004 prepared for review; external ffmpeg workflow contract inspected; transferable
MP3/audio-mpeg source-proven fallback found; operator manual proof captured as manual evidence;
Lemonfox selected as first adapter; needs lightweight proof matrix, Opus default candidate proof,
self-hosted asset path, S3 storage config, prepared-audio retention and cancel UX decision before
implementation

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
Output: provider ADR: Brave first pilot vs Yandex Search API vs self-hosted/external, with limits
and prohibited-query examples.
Depends on: data policy, customer privacy/cost approval, smoke queries
Status: ready for ADR after data policy draft

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
Source: VL_OCR_PROVIDER_RESEARCH
Why: Need to compare native extraction, Tika/Docling, Mistral OCR/document AI, cloud OCR and
local/VLM options before promising OCR quality.
Output: short candidate shortlist and pilot plan for 2-3 candidates.
Depends on: customer data policy and sample documents
Status: research artifact created; pilot candidate choice pending

## Ready for runtime proof

### OpenWebUI native capability audit

Domain: Workspaces / RBAC / analytics / files
Source: OPENWEBUI_CAPABILITY_RESEARCH
Why: Current docs may not match deployed v0.9.6.
Output: capability proof report with exact Admin UI settings and user/group test results.
Depends on: admin or staging access
Status: ready for runtime proof

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
Why: Web-search for all users requires provider, result count, concurrency and cost proof.
Output: smoke results for approved Russian/English queries and documented gaps.
Depends on: ADR-0007, provider account/key path, allowed query examples
Status: ready after ADR and provider approval

### STT proxy smoke plan

Domain: Transcription / STT
Source: TRANSCRIPTION_STT blueprint, ADR-0004
Why: STT proxy must be proven before final UI work.
Output: smoke plan for audio/video, key handling, errors, size/duration and transcript shape.
Depends on: approved ADR-0004, inspected ffmpeg contract, sample media
Status: ready to plan after ADR review; must include Lemonfox adapter proof, Opus output profile
compatibility proof, prepared audio >100 MB behavior, S3 prepared-audio storage proof, cancel
lifecycle proof where technically possible and no API key in browser proof

### STT env/config contract review

Domain: Transcription / STT / configuration
Source: ADR-0004, STT_ENV_CONTRACT
Why: Stage 2 STT provider, output profile, ffmpeg asset mode, storage, limits and cancel behavior
must be configured server-side without exposing secrets to browser.
Output: reviewed draft env contract for Lemonfox, output profiles, self-hosted ffmpeg assets,
S3/object storage, retention, limits and cancel flags.
Depends on: ADR-0004 review, data policy, ops/storage decision.
Status: ready for review; not a real `.env.example`

### FFMPEG mobile / large-file proof matrix

Domain: Transcription / STT
Source: ADR-0004, FFMPEG_WORKFLOW_ARTIFACT_INSPECTION
Why: Operator manual proof is useful, but implementation acceptance needs reproducible evidence.
Output: lightweight proof matrix with device, browser, file type, file size, duration, selected
output profile, result and evidence for desktop audio, desktop video, mobile audio, mobile video,
large WAV and large video.
Depends on: source workflow access and approved test media.
Status: ready for runtime proof after ADR review

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
Why: Normalized/prepared audio sent to provider must be available through controlled S3/object
storage, while source media storage must not be enabled silently.
Output: S3 bucket/prefix/retention decision, prepared-audio cleanup policy, source-media storage
flag, cancelled-job retention behavior.
Depends on: data policy, retention policy, operator storage configuration.
Status: blocked by storage/retention decision

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
