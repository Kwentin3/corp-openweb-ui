# Stage 2 Contract Boundaries

## 1. Purpose

Этот документ фиксирует доменные границы Stage 2, чтобы реализация не
размазывала custom logic по OpenWebUI core или frontend.

Stage 2 должен оставаться upgrade-safe: OpenWebUI остается upstream product
shell, а custom capabilities добавляются через bounded domain services,
internal APIs или thin integration shims.

Документ не запускает implementation. Он задает рамку для ADR, proof gates и
будущих implementation slices.

## 2. Principles

- Domain isolation: каждый risky domain имеет owner, contract and acceptance.
- Backend-first: security, provider keys, policy, retention and usage decisions
  принадлежат backend/domain services.
- Contract-first: UI and templates depend on stable internal contracts, not raw
  provider responses.
- OpenWebUI upstream-first: native capabilities используются первыми, deep fork
  допускается только после proof that native/config/sidecar path is insufficient.
- Thin frontend: frontend отвечает за user interaction, upload/progress/cancel
  UX and calls to internal Stage 2 APIs.
- No API keys in browser: browser never calls STT/LLM/OCR providers with
  provider secrets.
- No policy decisions in UI: frontend can display decisions and warnings, but
  cannot be source of truth.
- Versioned internal contracts: breaking changes require a new version suffix or
  ADR update.
- Runtime proof before implementation: contracts and gates must be proven before
  final UI or production changes.

## 3. Boundary map

### OpenWebUI core

- auth/session surface;
- users/groups/RBAC where native;
- chat/workspace UI;
- prompts/knowledge/workspace models where native;
- native analytics if sufficient.

### Stage 2 backend/domain services

- STT proxy/job service;
- provider adapters;
- policy resolver;
- usage event collector;
- transcript normalization;
- retention/export lifecycle;
- OCR/VL OCR pilot adapters;
- internal health/smoke endpoints.

### Frontend/thin UI

- user interaction;
- upload/progress/cancel UX;
- calls internal Stage 2 APIs;
- never stores provider API keys;
- never decides data policy;
- never decides manager visibility;
- never owns retention or usage accounting.

### External providers

- STT provider;
- LLM providers;
- web-search providers;
- OCR/VL OCR providers.

External provider responses are not product contracts. Provider adapters translate
them into internal Stage 2 contracts.

### Storage/retention

- temporary files and prepared audio blobs;
- transcript storage if approved by policy;
- document/OCR pilot artifacts;
- usage metadata;
- retention/delete/export lifecycle.

Storage and retention follow data policy, manager visibility policy and chat
deletion/retention ADRs. No-delete is not retention. Retention is not audit.

### Admin/operator surface

- provider/model configuration;
- usage review;
- smoke/proof evidence;
- feature flags and limits;
- safe operational checks without secrets.

Operator surfaces must not print provider keys, `.env` contents or raw sensitive
customer media.

## 4. Stage 2 internal contracts

Draft internal contracts:

- `TranscriptionJobV1`:
  job lifecycle for STT upload, progress, status, cancellation and typed errors.
- `TranscriptResultV1`:
  normalized transcript shape for UI, templates and exports.
- `UsageEventV1`:
  normalized usage record for LLM, web-search, STT, OCR and storage review.
- `PolicyDecisionV1`:
  backend decision for feature access, data class, provider class, limits and
  warnings.
- `ProviderModelCatalogV1`:
  curated provider/model catalog with production, pilot, research, rejected and
  deferred labels.
- `DocumentExtractionResultV1`:
  normalized output for document extraction/OCR pilot, including document class,
  extracted text, tables and quality warnings.
- `ManagerVisibilityPolicyV1`:
  controlled visibility model for work chats and shared scenarios.
- `RetentionPolicyV1`:
  storage and deletion rules for source files, prepared blobs, transcripts,
  extracted documents, usage metadata and exports.

These are planning contracts. They are not API implementation.

## 5. Contract versioning rule

- Contract names must include a version suffix, for example `TranscriptResultV1`.
- Breaking changes require a new version or ADR update.
- UI/templates should depend on normalized internal contracts, not raw provider
  responses.
- Provider adapters translate external responses into internal contracts.
- Contract changes require updated smoke/acceptance checks.

## 6. Anti-patterns

- Frontend directly calls external STT provider with API key.
- UI decides whether data may be sent to provider.
- OpenWebUI core is patched deeply for every custom workflow.
- Provider response shape leaks into prompts/templates.
- Manager visibility is implemented through blanket admin access.
- No-delete is treated as audit/retention.
- OCR pilot is treated as production OCR pipeline.
- Native OpenWebUI analytics is assumed sufficient without runtime proof.
- Stage 2 backend creates a parallel identity system instead of using approved
  OpenWebUI identity/session context.
- External provider setup starts before data policy by provider class is
  approved.

## 7. First contract to define

First implementation-facing contract must be STT proxy boundary:

- `TranscriptionJobV1`;
- `TranscriptResultV1`;
- `UsageEventV1`;
- `PolicyDecisionV1`.

`ADR-0004 STT Proxy Boundary` is now the proposed review document for this
boundary. It recommends a server-side STT proxy/job service and rejects direct
browser-to-provider calls.

Current blocker:

- the actual existing ffmpeg workflow artifact is not present in this repo;
- implementation readiness is blocked until that artifact contract is inspected
  or a replacement preprocessing contract is approved.

The ffmpeg workflow is a media preprocessing asset, not a security boundary.

## 8. Related docs

- [PRD-1](../prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md)
- [Stage 2 README](README.md)
- [Implementation Gates](IMPLEMENTATION_GATES.md)
- [ADR-0004 STT Proxy Boundary](decisions/ADR-0004-stt-proxy-boundary.md)
- [Transcription STT Blueprint](blueprints/TRANSCRIPTION_STT.blueprint.md)
- [FFMPEG Browser Workflow Research](research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md)
- [Transcription STT Research](research/TRANSCRIPTION_STT_RESEARCH.md)
