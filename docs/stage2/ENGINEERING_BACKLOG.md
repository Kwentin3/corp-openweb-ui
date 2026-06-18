# Stage 2 Engineering Backlog

Это planning backlog, не issue tracker. Research выполнен 2026-06-18; следующие элементы являются decision/planning work, не implementation.

## Delivery rule

Stage 2 implementation must start from backend/server-side boundaries, policies and proofs. Frontend/UI work follows after backend contracts are clear.

Frontend must not become the place where security, provider keys, data policy, retention rules or access rules are decided.

Provider setup must not start before data policy by provider class is approved.

## Ready for ADR

### Data policy by provider class

Domain: Security / data policy / providers
Source: SECURITY_DATA_POLICY blueprint, DATA_MASKING_FUTURE_RESEARCH, PRD-1
Why: Provider setup and document/transcript workflows depend on allowed/prohibited data classes.
Output: ADR-0001 with provider classes, data classes, draft allowed/prohibited matrix and customer questions.
Depends on: customer/security approval
Status: ready for ADR; required before provider setup

### STT proxy boundary

Domain: Transcription / STT
Source: TRANSCRIPTION_STT blueprint, TRANSCRIPTION_STT_RESEARCH, LEMONFOX_STT_RESEARCH, FFMPEG_BROWSER_WORKFLOW_RESEARCH
Why: API keys cannot be exposed in browser; Lemonfox-specific capabilities and ffmpeg preprocessing need server-side control.
Output: ADR for proxy contract, auth/permissions, upload limits, storage, errors, provider response normalization and optional audit.
Depends on: existing ffmpeg workflow artifact, customer media limits
Status: ready for ADR before final UI work

### Provider model catalog

Domain: Providers / models
Source: PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH
Why: Users need curated models; vague `GPT-mini` and Claude Code confusion must be removed before setup.
Output: catalog with exact model IDs, use cases, costs, data policy, production/research/rejected labels.
Depends on: ADR-0001 data policy, customer provider accounts
Status: ready for ADR after data policy draft

### Web-search provider

Domain: Web-search
Source: WEB_SEARCH_PROVIDERS_RESEARCH, existing infra web-search research
Why: Web-search нужен всем, но provider choice affects cost/privacy and Russian-provider stance.
Output: provider ADR: Brave first pilot vs Yandex Search API vs self-hosted/external, with limits and prohibited-query examples.
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
Why: OCR pilot is in Practical Stage 2; production pipeline is not. VL OCR may help with scans/images/complex PDFs but must be benchmarked.
Output: ADR or decision note for pilot candidate list, test set, evaluation criteria and document-type classification.
Depends on: customer samples and data policy
Status: waiting for customer test data; ready for ADR skeleton

### Billing approach

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Basic analytics may be enough; gateway must not be assumed.
Output: native analytics vs gateway decision.
Depends on: deployed analytics proof, provider catalog
Status: ready for decision after runtime proof

## Ready for research

### VL OCR provider/candidate evaluation

Domain: Documents / OCR / Excel
Source: VL_OCR_PROVIDER_RESEARCH
Why: Need to compare native extraction, Tika/Docling, Mistral OCR/document AI, cloud OCR and local/VLM options before promising OCR quality.
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

### Native analytics proof

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Need evidence that deployed analytics is sufficient for basic reporting.
Output: screenshots/notes for two users/groups/models and cost estimation workflow.
Depends on: test users and sample usage
Status: ready for runtime proof

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
Output: scanned broker report, photo document, PDF with tables, PDF with stamps/signatures, poor scan and expected output sample.
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
Why: Runtime smoke cannot run without approved keys/accounts, but keys must not be committed or printed.
Output: operator confirmation of available accounts and safe smoke procedure.
Depends on: customer/operator
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
