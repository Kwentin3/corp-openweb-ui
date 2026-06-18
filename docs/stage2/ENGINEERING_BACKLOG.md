# Stage 2 Engineering Backlog

Это planning backlog, не issue tracker. Research выполнен 2026-06-18; следующие элементы являются decision/planning work, не implementation.

## Ready for architecture decision

## STT proxy design

Domain: Transcription / STT
Source: TRANSCRIPTION_STT blueprint, TRANSCRIPTION_STT_RESEARCH, LEMONFOX_STT_RESEARCH, FFMPEG_BROWSER_WORKFLOW_RESEARCH
Why: API keys cannot be exposed in browser; Lemonfox-specific capabilities and ffmpeg preprocessing need server-side control.
Output: ADR for proxy boundary, upload limits, storage, errors, provider response normalization.
Depends on: existing ffmpeg workflow artifact, customer media limits
Status: ready for ADR

## Web-search provider selection

Domain: Web-search
Source: WEB_SEARCH_PROVIDERS_RESEARCH, existing infra web-search research
Why: Web-search нужен всем, но provider choice affects cost/privacy and Russian-provider stance.
Output: provider ADR: Brave first pilot vs Yandex Search API vs self-hosted/external.
Depends on: customer privacy/cost approval, smoke queries
Status: ready for ADR

## Provider model catalog

Domain: Providers / models
Source: PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH
Why: Users need curated models; vague `GPT-mini` and Claude Code confusion must be removed before setup.
Output: catalog with exact model IDs, use cases, costs, data policy, production/research/rejected labels.
Depends on: customer provider accounts and allowed-data policy
Status: ready for ADR

## Billing approach

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Basic analytics may be enough; gateway must not be assumed.
Output: native analytics vs gateway decision.
Depends on: deployed analytics proof, provider catalog
Status: ready for decision after runtime proof

## OCR pilot scope

Domain: Documents / OCR / Excel
Source: DOCUMENTS_OCR_EXCEL_RESEARCH
Why: OCR pilot is in Practical Stage 2; production pipeline is not.
Output: ADR or decision note for first extraction engine and pilot limits.
Depends on: customer samples
Status: waiting for customer test data

## Manager visibility and no-delete policy

Domain: RBAC / manager visibility / retention
Source: RBAC_MANAGER_VISIBILITY_RESEARCH, CHAT_DELETION_RETENTION_RESEARCH
Why: Access model depends on privacy stance and exact OpenWebUI runtime behavior.
Output: decision note with test matrix and accepted visibility boundary.
Depends on: customer/admin policy, deployed/staging runtime proof
Status: ready for runtime proof; blocked for final decision by customer policy

## Ready for runtime proof

## OpenWebUI native capability audit

Domain: Workspaces / RBAC / analytics / files
Source: OPENWEBUI_CAPABILITY_RESEARCH
Why: Current docs may not match deployed v0.9.6.
Output: capability proof report with exact Admin UI settings and user/group test results.
Depends on: admin or staging access
Status: ready for runtime proof

## Native analytics proof

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Need evidence that deployed analytics is sufficient for basic reporting.
Output: screenshots/notes for two users/groups/models and cost estimation workflow.
Depends on: test users and sample usage
Status: ready for runtime proof

## Chat deletion permission proof

Domain: Retention / no-delete policy
Source: CHAT_DELETION_RETENTION_RESEARCH
Why: Native no-delete is plausible but unproven.
Output: non-admin UI/API delete proof.
Depends on: test user matrix
Status: ready for runtime proof

## Ready for implementation planning after ADRs

## Workspace scenario setup plan

Domain: Workspaces / RBAC
Source: WORKSPACES_AND_RBAC blueprint, OPENWEBUI_CAPABILITY_RESEARCH
Why: Configuration-first domain likely can be planned early after runtime proof.
Output: implementation slices for groups, prompts, knowledge, access.
Depends on: groups/roles from customer, native capability audit
Status: pending customer input and runtime proof

## Acceptance and test data package

Domain: Operations / acceptance
Source: ACCEPTANCE_MATRIX, TEST_DATA_REQUIREMENTS
Why: Implementation without test data will drift.
Output: approved test data checklist and acceptance sequence.
Depends on: customer files and users
Status: ready for planning

## Blocked by customer input

## Broker report test set

Domain: Broker reports / documents
Source: PRD-1
Why: Scenario quality cannot be validated on imaginary documents.
Output: anonymized broker reports, expected result examples.
Depends on: customer
Status: blocked by customer input

## Groups and manager visibility policy

Domain: RBAC / manager visibility
Source: PRD-1, RBAC_MANAGER_VISIBILITY_RESEARCH
Why: Access model depends on actual departments and privacy stance.
Output: approved group matrix and visibility policy.
Depends on: customer/admin
Status: blocked by customer input

## Provider/data policy approval

Domain: Providers / security
Source: PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH, DATA_MASKING_FUTURE_RESEARCH
Why: Provider setup must follow allowed-data policy.
Output: provider allowlist and prohibited data examples.
Depends on: customer/admin/security
Status: blocked by customer input

## Deferred / future slices

## Full data masking/tokenization subsystem

Domain: Security / data policy
Source: DATA_MASKING_FUTURE_RESEARCH
Why: Requires detection, mapping store, reverse substitution and leak tests.
Output: future security architecture, not Stage 2 implementation.
Depends on: separate approval
Status: deferred

## Production-grade OCR/layout pipeline

Domain: Documents / OCR
Source: DOCUMENTS_OCR_EXCEL_RESEARCH
Why: Pilot first; production pipeline requires queue, validation, audit.
Output: future architecture decision after pilot.
Depends on: OCR pilot evidence
Status: deferred

## Hard billing/gateway

Domain: Usage analytics / costs
Source: USAGE_ANALYTICS_BILLING_RESEARCH
Why: Hard budgets require gateway-level architecture.
Output: future gateway ADR if native analytics insufficient.
Depends on: cost visibility research and customer requirement
Status: deferred unless hard budgets are required
