# Stage 2 Engineering Backlog

Это planning backlog, не issue tracker.

## Ready for research

## OpenWebUI native capability audit

Domain: Workspaces / RBAC / analytics / files
Source: PRD-1, PRD-0 audit
Why: Реализация должна быть native-first.
Output: Capability research notes and gaps.
Depends on: deployed version access
Status: ready for research

## Transcription STT integration research

Domain: Transcription / STT
Source: PRD-1 priority scenario
Why: Нужно понять integration boundary for ffmpeg workflow and STT proxy.
Output: STT proxy decision inputs, Lemonfox fit assessment.
Depends on: existing ffmpeg project details, Lemonfox research
Status: ready for research

## Web-search provider research

Domain: Web-search
Source: PRD-1, existing web-search research
Why: Web-search нужен всем, но с cost/privacy limits.
Output: provider selection options, smoke plan.
Depends on: provider access/pricing confirmation
Status: ready for research

## Documents/OCR/Excel research

Domain: Documents / OCR / Excel
Source: PRD-1, broker reports scenario
Why: Нужно отделить basic handling от production pipeline.
Output: OCR pilot scope, parser/tool options.
Depends on: customer test documents
Status: ready for research

## Manager visibility and deletion research

Domain: Manager visibility / retention
Source: PRD-1 customer requirement
Why: Нужна privacy-safe модель доступа и no-delete check.
Output: native capability findings and decision options.
Depends on: OpenWebUI permission model, customer policy
Status: ready for research

## Ready for architecture decision

## STT proxy design

Domain: Transcription / STT
Source: TRANSCRIPTION_STT blueprint
Why: API keys cannot be exposed in browser.
Output: ADR for proxy boundary, upload limits, storage, errors.
Depends on: transcription research
Status: waiting for research

## Billing approach

Domain: Usage analytics / costs
Source: PRD-1
Why: Basic analytics may be enough; gateway must not be assumed.
Output: native analytics vs gateway decision.
Depends on: OpenWebUI analytics research, provider catalog
Status: waiting for research

## OCR pilot scope

Domain: Documents / OCR / Excel
Source: PRD-1
Why: OCR pilot is in Practical Stage 2; production pipeline is not.
Output: ADR or decision note for pilot scope.
Depends on: customer samples
Status: waiting for research

## Ready for implementation planning

## Workspace scenario setup plan

Domain: Workspaces / RBAC
Source: WORKSPACES_AND_RBAC blueprint
Why: Configuration-first domain likely can be planned early.
Output: implementation slices for groups, prompts, knowledge, access.
Depends on: groups/roles from customer
Status: pending customer input

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
Source: PRD-1
Why: Access model depends on actual departments and privacy stance.
Output: approved group matrix and visibility policy.
Depends on: customer/admin
Status: blocked by customer input

## Deferred / future slices

## Full data masking/tokenization subsystem

Domain: Security / data policy
Source: PRD-1 non-goals
Why: Requires local detection, mapping store, reverse substitution and leak tests.
Output: future security architecture, not Stage 2 implementation.
Depends on: separate approval
Status: deferred

## Production-grade OCR/layout pipeline

Domain: Documents / OCR
Source: PRD-1 optional slices
Why: Pilot first; production pipeline requires queue, validation, audit.
Output: future architecture decision after pilot.
Depends on: OCR pilot evidence
Status: deferred

## Hard billing/gateway

Domain: Usage analytics / costs
Source: PRD-1 optional slices
Why: Hard budgets require gateway-level architecture.
Output: future gateway ADR if native analytics insufficient.
Depends on: cost visibility research
Status: deferred
