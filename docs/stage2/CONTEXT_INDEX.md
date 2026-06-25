# Stage 2 Context Index

Цель: быстро понять, какие документы читать по конкретной будущей задаче.

## Общий Stage 2 scope

Read first:

- [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [README](README.md)
- [Stage 2 Unblocked Work Plan](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [DOMAIN_MAP](DOMAIN_MAP.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
- [EXTENSION_FIRST_IMPLEMENTATION_PATTERN](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [OpenWebUI native capability audit](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [OpenWebUI native capability runtime audit report](../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md)
- [OpenWebUI admin/test-user runtime proof report](../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md)
- [Customer Stage 2 Governance Proposal](proposals/CUSTOMER_STAGE2_GOVERNANCE_PROPOSAL.md)
- [Customer runtime decisions / решения после runtime-аудита](proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)
- [Workspace scenario user stories](implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Synthetic test data index](testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [Customer summary](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md)
- [PRD-0 audit](../reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md)

Skip unless needed:

- PRD-0 deploy runbooks.

Comment:

- PRD-1 is the source of truth.
- Stage 2 custom logic must stay behind backend/domain contracts.
- OpenWebUI-facing features should follow the extension-first order before a
  fork: native mechanisms, Functions/Actions/Tools, thin static loader/UI shim,
  private sidecar, then fork only with proof and owner/ADR approval.
- For STT, user-facing UX must remain inside OpenWebUI; the sidecar is
  backend-only.
- MVP STT trigger is explicit `Transcribe` action on an audio/video media
  attachment.

## Unblocked planning / work without new customer approval

Read first:

- [Stage 2 Unblocked Work Plan](implementation/STAGE2_UNBLOCKED_WORK_PLAN.md)
- [Stage 2 Scenario Shortlist](implementation/STAGE2_SCENARIO_SHORTLIST.md)
- [Workspace scenario user stories](implementation/WORKSPACE_SCENARIO_USER_STORIES.md)
- [Synthetic test data index](testdata/SYNTHETIC_TEST_DATA_INDEX.md)
- [ENGINEERING_BACKLOG](ENGINEERING_BACKLOG.md)
- [ACCEPTANCE_MATRIX](acceptance/ACCEPTANCE_MATRIX.md)

Additional context:

- [OpenWebUI native capability audit](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [Customer runtime decisions](proposals/CUSTOMER_STAGE2_RUNTIME_DECISIONS.md)
- [CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH](research/CORPORATE_AI_WORKSPACE_USE_CASES_RESEARCH.md)
- [USAGE_ANALYTICS_BILLING_RESEARCH](research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- [VL_OCR_PROVIDER_RESEARCH](research/VL_OCR_PROVIDER_RESEARCH.md)
- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN](implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md)

Skip unless separately approved:

- Runtime `.env`.
- Customer documents.
- Stand runtime smoke/proof.

Comment:

- This stream is for internal documentation, skeletons, synthetic data,
  research, benchmark plans and proof plans.
- Corporate AI workspace use-case research is available as fact base before
  expanding or selecting user stories.
- Scenario shortlist and first draft user stories are available as a docs-only
  selection layer before synthetic data or proof planning.
- Synthetic proof can support mechanics and candidate comparison, but it does
  not close customer acceptance or implementation gates.
- VL OCR research and synthetic benchmark can start now; customer OCR pilot
  remains blocked by real samples and data policy.
- Usage analytics proof should target user/day/week/model/token/message and
  approximate-cost breakdown before any hard billing/gateway decision.

## Domain isolation / contract boundaries

Read first:

- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)
- [EXTENSION_FIRST_IMPLEMENTATION_PATTERN](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [DOMAIN_MAP](DOMAIN_MAP.md)
- [ROADMAP](ROADMAP.md)

Additional context:

- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)
- [decisions/README](decisions/README.md)
- [Docs format and gates refine report](../reports/2026-06-18/OPENWEBUI_STAGE2_DOCS_FORMAT_AND_GATES_REFINE.report.md)

Skip unless needed:

- Provider setup runbooks.
- Runtime `.env`.

Comment:

- OpenWebUI remains upstream product shell.
- Stage 2 custom capabilities live in bounded domain services, internal APIs or
  thin integration shims.
- Frontend does not own security, provider keys, data policy, retention, manager
  visibility or usage accounting.

## Рабочие пространства / RBAC

Read first:

- [OPENWEBUI_NATIVE_CAPABILITY_AUDIT](implementation/OPENWEBUI_NATIVE_CAPABILITY_AUDIT.md)
- [WORKSPACES_AND_RBAC](blueprints/WORKSPACES_AND_RBAC.blueprint.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT report](../reports/2026-06-24/OPENWEBUI_NATIVE_CAPABILITY_RUNTIME_AUDIT.report.md)
- [OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF report](../reports/2026-06-24/OPENWEBUI_ADMIN_TEST_USER_RUNTIME_PROOF.report.md)
- [OPENWEBUI_CAPABILITY_RESEARCH](research/OPENWEBUI_CAPABILITY_RESEARCH.md)
- [RBAC_MANAGER_VISIBILITY_RESEARCH](research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)
- [ACCESS_POLICY](../security/ACCESS_POLICY.md)

Skip unless needed:

- STT/provider pricing docs.

Comment:

- Research is done and public runtime version/health proof was captured on
  2026-06-24. Admin/test-user proof is still needed for RBAC, model visibility,
  prompts, knowledge, analytics, no-delete and manager visibility.

## Транскрибация

Read first:

- [OpenWebUI STT ffmpeg browser normalization implementation report](../reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md)
- [OpenWebUI STT MVP feature closure report](../reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md)
- [OpenWebUI STT runtime completion report](../reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md)
- [Extension-first implementation pattern](EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md)
- [STT backend implementation plan](implementation/STT_BACKEND_IMPLEMENTATION_PLAN.md)
  (historical traceability)
- [STT OpenWebUI media action probe plan](implementation/STT_OPENWEBUI_MEDIA_ACTION_PROBE_PLAN.md)
  (historical traceability)
- [STT frontend media action patch plan](implementation/STT_FRONTEND_MEDIA_ACTION_PATCH_PLAN.md)
  (historical traceability)
- [STT media input normalization contract](contracts/STT_MEDIA_INPUT_NORMALIZATION_CONTRACT.md)
- [OpenWebUI STT Frontend Media Action Patch Report](../reports/2026-06-19/OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md)
- [OpenWebUI STT Playwright UI Proof](../reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md)
- [OpenWebUI-native STT UX Integration Research](../reports/2026-06-19/OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md)
- [OpenWebUI mobile microphone STT anamnesis audit](../reports/2026-06-23/OPENWEBUI_MOBILE_MICROPHONE_STT_ANAMNESIS_AUDIT.report.md)
- [TRANSCRIPTION_STT](blueprints/TRANSCRIPTION_STT.blueprint.md)
- [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md)
- [CONTRACT_BOUNDARIES](CONTRACT_BOUNDARIES.md)

Additional context:

- [TRANSCRIPTION_STT_RESEARCH](research/TRANSCRIPTION_STT_RESEARCH.md)
- [FFMPEG_WORKFLOW_ARTIFACT_INSPECTION](research/FFMPEG_WORKFLOW_ARTIFACT_INSPECTION.md)
- [FFMPEG_BROWSER_WORKFLOW_RESEARCH](research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [LEMONFOX_STT_RESEARCH](research/LEMONFOX_STT_RESEARCH.md)

Skip unless needed:

- Broker/tax docs.

Comment:

- API keys never go to the browser.
- STT proxy ADR still defines the backend boundary; ADR-0004 remains
  `Proposed`.
- Private sidecar job routes, the OpenWebUI media attachment `Transcribe`
  action and browser ffmpeg.wasm normalization are implemented/proven for the
  MVP path.
- Stage 2 STT MVP is current-stage closed and ready for broader testing.
  Remaining STT work is testing/hardening, not architectural discovery.
- Prepared-MP3 frontend MVP passed through a static OpenWebUI loader patch.
- MP4-with-audio and WebM generated proof media passed through browser
  normalization into the existing Action/sidecar path.
- Broad input support is capability-based: declared source formats are hints,
  while actual support requires configured ffmpeg.wasm probe/decode,
  audio-stream detection and normalization to an approved output profile.
- A dedicated transcription workspace/history/export/protocol flow is future,
  not MVP.
- External ffmpeg workflow contract is inspected and transferable as MP3 /
  `audio/mpeg`; owner/operator proof is accepted for ADR planning, while
  production dependency decisions remain open.
- Remaining STT hardening: mobile, low-memory browser, large/customer media,
  cancel during ffmpeg, duration-limit policy, Opus provider proof if selected,
  production storage/retention, transcript history/export/workflow and
  multi-user/group permission hardening.
- Known issue as of 2026-06-23: native mobile microphone dictation can show the
  recording waveform but produce no audio transcription and stop after about
  five seconds. Track this as native Web Speech API/mobile hardening, not as a
  `stage2-stt` sidecar failure.
- Do not re-plan STT from zero and do not introduce a separate user-facing STT
  sidecar GUI for the MVP.

## Брокерские отчеты / 3-НДФЛ

Read first:

- [BROKER_REPORTS_3NDFL](blueprints/BROKER_REPORTS_3NDFL.blueprint.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)

Skip unless needed:

- Ops deployment docs.

Comment:

- AI output is draft/analysis only.
- Scenario is blocked by customer test data.

## Web-search

Read first:

- [WEB_SEARCH_CONTEXT_INDEX](WEB_SEARCH_CONTEXT_INDEX.md)
- [WEB_SEARCH](blueprints/WEB_SEARCH.blueprint.md)
- [ADR-0007 Web-search Provider](decisions/ADR-0007-web-search-provider.md)
- [OpenWebUI Web Search Integration Boundary](contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md)

Additional context:

- [WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20](research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md)
- [WEB_SEARCH_PROVIDERS_RESEARCH](research/WEB_SEARCH_PROVIDERS_RESEARCH.md)
- [WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT](contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md)
- [WEB_SEARCH_USAGE_EVENT_CONTRACT](contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md)
- [WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT](contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md)
- [WEB_SEARCH_NATIVE_PILOT_PLAN](implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md)
- [WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN](implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md)
- [WEB_SEARCH_RUNTIME_PROBE report](../reports/2026-06-20/OPENWEBUI_WEB_SEARCH_RUNTIME_PROBE.report.md)
- [WEB_SEARCH_DOMAIN_AND_PROBE report](../reports/2026-06-20/OPENWEBUI_WEB_SEARCH_DOMAIN_AND_PROBE.report.md)
- Existing [WEB_SEARCH_PROVIDER_RESEARCH](../infra/WEB_SEARCH_PROVIDER_RESEARCH.md)

Skip unless needed:

- STT/OCR docs.

Comment:

- Native OpenWebUI Web Search is the first path.
- Brave `brave_llm_context` is the current working native direct-context
  baseline.
- The current Brave baseline uses result count `3`, search concurrency `1`,
  web-loader bypass and web-search embedding/retrieval bypass.
- Known deferred issue: vectorized Web Search retrieval can create
  `web-search-*` collections after search/embedding but return `0` sources on
  follow-up retrieval. Revisit only for long pages, classic `brave`, SearXNG
  page loading or full RAG over fetched content.
- Private SearXNG is the self-hosted meta-search comparison track. It gives a
  private instance boundary, but upstream engines can still receive minimized
  queries. Runtime smoke passed in snippet/bypass mode on 2026-06-23.
- Yandex Search is a working Russian-provider path after 2026-06-23 Admin
  UI/native smoke; broaden use only after metadata-forwarding, allowed data
  class and cost-mode review.
- Current closeout status: Brave, Yandex and private SearXNG provider
  connectivity is proven; production rollout and full provider comparison are
  pending.
- No sidecar/fork/custom gateway until native runtime smoke proves a concrete
  gap.

## Documents / OCR / Excel

Read first:

- [DOCUMENTS_OCR_EXCEL](blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)
- [ADR-0005 OCR / VL OCR Pilot Scope](decisions/ADR-0005-ocr-vl-ocr-pilot-scope.md)

Additional context:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)
- [VL_OCR_PROVIDER_RESEARCH](research/VL_OCR_PROVIDER_RESEARCH.md)
- [TEST_DATA_REQUIREMENTS](acceptance/TEST_DATA_REQUIREMENTS.md)

Skip unless needed:

- Provider setup runbook until integration reaches provider calls.

Comment:

- OCR/VL OCR is a pilot.
- Production OCR/layout pipeline remains future.

## Сканы / картинки / PDF OCR

Read first:

- [DOCUMENTS_OCR_EXCEL](blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md)
- [VL_OCR_PROVIDER_RESEARCH](research/VL_OCR_PROVIDER_RESEARCH.md)
- [TEST_DATA_REQUIREMENTS](acceptance/TEST_DATA_REQUIREMENTS.md)

Additional context:

- [DOCUMENTS_OCR_EXCEL_RESEARCH](research/DOCUMENTS_OCR_EXCEL_RESEARCH.md)

Skip unless needed:

- Full document management docs.

Comment:

- Classify by document type.
- Do not use "OCR works for everything" as acceptance.

## Provider catalog / models

Read first:

- [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
- [ADR-0006 Provider Model Catalog](decisions/ADR-0006-provider-model-catalog.md)

Additional context:

- [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)
- [PROVIDER_CONNECTIONS_PLAN](../infra/PROVIDER_CONNECTIONS_PLAN.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)

Skip unless needed:

- Runtime `.env`.

Comment:

- Claude API is a provider.
- Claude Code is not a chat provider.
- Exact model IDs are required.

## Стоимость / analytics

Read first:

- [USAGE_ANALYTICS_AND_COSTS](blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md)
- [ADR-0008 Native Analytics vs Hard
  Billing](decisions/ADR-0008-native-analytics-vs-hard-billing.md)

Additional context:

- [USAGE_ANALYTICS_BILLING_RESEARCH](research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- [PROVIDERS_MODEL_CATALOG](blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)

Skip unless needed:

- Gateway deployment docs until decision.

Comment:

- Native analytics first.
- Hard billing is a separate ADR/future slice.

## Data policy / masking

Read first:

- [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [DATA_MASKING_FUTURE_RESEARCH](research/DATA_MASKING_FUTURE_RESEARCH.md)
- [SECRETS_POLICY](../security/SECRETS_POLICY.md)
- [SECURITY_MINIMUM](../security/SECURITY_MINIMUM.md)

Skip unless needed:

- Implementation code.

Comment:

- Provider setup must wait for data policy.
- Masking/tokenization remains future.

## Data policy / provider data classes

Read first:

- [SECURITY_DATA_POLICY](blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [ADR-0001 Data Policy](decisions/ADR-0001-data-policy-by-provider-class.md)

Additional context:

- [DATA_MASKING_FUTURE_RESEARCH](research/DATA_MASKING_FUTURE_RESEARCH.md)

Skip unless needed:

- Provider setup runbook until approval.

Comment:

- Read before Claude, DeepSeek, Yandex, GigaChat or OpenAI setup.

## Руководители и чаты

Read first:

- [MANAGER_VISIBILITY_AND_RETENTION](blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)
- [ADR-0002 Manager Visibility Policy](decisions/ADR-0002-manager-visibility-policy.md)

Additional context:

- [RBAC_MANAGER_VISIBILITY_RESEARCH](research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)

Skip unless needed:

- Provider pricing docs.

Comment:

- Controlled work-chat visibility.
- This is not "manager sees everything".

## Retention / audit / no-delete

Read first:

- [MANAGER_VISIBILITY_AND_RETENTION](blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)
- [ADR-0003 Chat Deletion, Retention and Audit](decisions/ADR-0003-chat-deletion-retention-audit.md)

Additional context:

- [CHAT_DELETION_RETENTION_RESEARCH](research/CHAT_DELETION_RETENTION_RESEARCH.md)

Skip unless needed:

- Provider pricing docs.

Comment:

- No Delete is not Retention.
- Retention is not Audit.
- Audit is not immutable archive.

## Operations / acceptance

Read first:

- [OPS_AND_ACCEPTANCE](blueprints/OPS_AND_ACCEPTANCE.blueprint.md)
- [ACCEPTANCE_MATRIX](acceptance/ACCEPTANCE_MATRIX.md)
- [IMPLEMENTATION_GATES](IMPLEMENTATION_GATES.md)

Additional context:

- [SMOKE_TESTS](../ops/SMOKE_TESTS.md)
- [ACCEPTANCE_TESTS](../ops/ACCEPTANCE_TESTS.md)
- [UPDATE_ROLLBACK_RUNBOOK](../ops/UPDATE_ROLLBACK_RUNBOOK.md)

Skip unless needed:

- Feature-specific research.

Comment:

- No production changes in planning phase.

## Source status

Found:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/reports/2026-06-16/OPENWEBUI_PRD_0_POST_ACCEPTANCE_AUDIT.report.md`
- `docs/blueprint/*`
- `docs/infra/*`
- `docs/ops/*`
- `docs/security/*`
- `docs/reports/2026-06-09/*`

Missing:

- `docs/README.md`
