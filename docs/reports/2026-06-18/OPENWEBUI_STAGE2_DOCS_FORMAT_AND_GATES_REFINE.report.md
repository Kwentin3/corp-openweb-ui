# OpenWebUI Stage 2 Docs Format and Gates Refine Report

## 1. Summary

Stage 2 docs are now formatted for review and ready for ADR work, but the main
engineering risk is not markdown quality anymore. The main risk is boundary
drift: STT, provider access, usage analytics, retention and permissions can
become scattered across OpenWebUI UI changes, provider glue and ad hoc scripts.

My recommendation is to keep OpenWebUI as the mostly-upstream product layer and
add Stage 2 backend capabilities through narrow, documented contracts. The
backend should own provider keys, policy checks, usage metadata, retention and
normalization. The UI should consume stable internal APIs and should not decide
provider, security or storage policy.

Implementation is still blocked by ADR approval, runtime proof and customer test
data.

The task was documentation-only. No code, provider setup, compose/env/scripts or
production changes were made.

## 2. Why refine was needed

The Stage 2 engineering domain was already approved by content, but several
markdown files were hard to review in raw/GitHub view:

- long glued paragraphs;
- wide tables in context/domain/acceptance docs;
- mixed ADR registry order and execution order;
- missing ADR stubs for the next decisions;
- no single implementation-gates document before ADR work.

The cleanup improves:

- GitHub review;
- line-based diff;
- grep/search;
- agent context reading;
- future ADR work;
- implementation planning.

## 2.1. Engineering opinion

The healthiest direction is backend-first and extension-first, not fork-first.

OpenWebUI should remain the chat/workspace/RBAC/user-facing shell. Stage 2
custom logic should sit behind explicit internal backend contracts and should be
kept either:

- in a sidecar/internal backend service behind the same reverse proxy; or
- in a very small OpenWebUI integration shim if native extension points are not
  enough.

The sidecar/shim boundary matters because OpenWebUI will continue to change. If
Stage 2 code is mixed deeply into OpenWebUI routes, database models and UI
components, every upstream update becomes a manual merge project. If Stage 2
code is isolated behind contracts, upstream OpenWebUI can be updated with a
smaller compatibility check: routes, auth/session propagation, config and smoke
tests.

My practical recommendation:

1. Use native OpenWebUI features first for users, groups, model access,
   workspace flows, prompts/templates, web-search where it fits, and basic
   analytics where sufficient.
2. Add custom backend only where native OpenWebUI does not cover the corporate
   contract: STT proxy, provider-specific STT features, usage normalization,
   retention policy, and cross-feature audit/usage events.
3. Avoid deep fork work unless a concrete accepted requirement cannot be met by
   native features, sidecar API, reverse-proxy routing, OpenWebUI config or a
   small integration shim.

## 2.2. Contract proposal

The contracts should be placed at integration boundaries, not inside every
screen or helper.

Recommended contracts for Stage 2:

### Contract 1. STT media preprocessing contract

Owner: browser/ffmpeg workflow.

Purpose: describe what the existing ffmpeg workflow gives to the backend.

Minimum fields:

- `source_kind`: `audio` or `video`;
- `original_filename`;
- `original_mime_type`;
- `prepared_mime_type`;
- `prepared_codec`;
- `duration_sec`;
- `size_bytes`;
- `language_hint`;
- `client_platform`;
- `checksum` if practical;
- `preprocessing_warnings`.

Important rule: this contract is not a security boundary. The backend still
validates MIME, size, duration and permissions.

### Contract 2. STT proxy job contract

Owner: Stage 2 backend.

Purpose: accept prepared audio, protect provider keys, enforce policy and return
a stable transcript shape.

Recommended shape:

- `POST /stage2-api/transcription/jobs`
  - accepts multipart audio plus metadata;
  - returns `202 Accepted` with `job_id`, `status`, `limits`, `created_at`.
- `GET /stage2-api/transcription/jobs/{job_id}`
  - returns job state, progress if available, typed errors.
- `GET /stage2-api/transcription/jobs/{job_id}/result`
  - returns normalized transcript.
- `POST /stage2-api/transcription/jobs/{job_id}/cancel`
  - best-effort cancellation.

The job model is slightly more work than a single sync endpoint, but it is safer
for long audio/video and later async provider callbacks. A simple sync path can
still be implemented internally for short files, as long as the public contract
remains job-based.

### Contract 3. Transcript result contract

Owner: Stage 2 backend.

Purpose: keep provider response differences out of UI and prompts.

Minimum fields:

- `transcript_id`;
- `text`;
- `language`;
- `duration_sec`;
- `segments[]`;
- `segments[].start_sec`;
- `segments[].end_sec`;
- `segments[].text`;
- `segments[].speaker` if available;
- `words[]` if available and enabled;
- `provider`;
- `provider_model`;
- `quality_warnings`;
- `created_at`;
- `retention_mode`.

The UI and templates should depend on this internal shape, not on Lemonfox,
OpenAI or another provider response directly.

### Contract 4. Provider adapter contract

Owner: Stage 2 backend.

Purpose: keep Lemonfox/OpenAI/other STT differences in one backend module.

The adapter should expose a small internal interface:

- `transcribe(input)`;
- `normalize(provider_response)`;
- `map_error(provider_error)`;
- `estimate_usage(input, response)`;
- `supports(feature)`, for example `speaker_labels`, `word_timestamps`,
  `callback_url`, `eu_endpoint`.

This avoids leaking provider-specific parameters into UI and keeps provider swap
or fallback realistic.

### Contract 5. Policy and permission contract

Owner: Stage 2 backend, using OpenWebUI identity/group context where possible.

Purpose: decide whether a user can run a workflow with a provider/data class.

Minimum decision inputs:

- authenticated user;
- groups/roles;
- feature: `stt`, `web_search`, `ocr`, `provider_catalog`;
- data class;
- provider class;
- file metadata;
- requested retention mode.

Minimum decision output:

- `allowed`;
- `reason_code`;
- `warnings[]`;
- `effective_limits`;
- `audit_required`.

This should be backend-owned. Frontend can show the decision, but must not be the
source of truth.

### Contract 6. Usage event contract

Owner: Stage 2 backend.

Purpose: provide admin-visible usage without introducing hard billing too early.

Minimum fields:

- `event_id`;
- `user_id`;
- `group_id`;
- `feature`;
- `provider`;
- `model_or_engine`;
- `input_units`;
- `output_units`;
- `duration_sec`;
- `estimated_cost`;
- `currency`;
- `status`;
- `created_at`;
- `correlation_id`.

This supports native analytics plus a future gateway decision. It should not be
implemented as hard billing in Practical Stage 2 unless ADR-0008 approves that
scope.

### Contract 7. Retention contract

Owner: Stage 2 backend, aligned with data policy and chat deletion ADRs.

Purpose: define what is stored and for how long.

Default recommendation:

- source video/audio: not stored after processing unless explicitly approved;
- prepared audio blob: temporary storage only, with short TTL;
- transcript: stored only when the scenario needs reuse/history;
- usage metadata: stored for admin review;
- provider raw response: do not store by default, or store only sanitized debug
  metadata.

## 2.3. Backend features to add

The backend additions should be small, explicit and isolated from OpenWebUI core.

Recommended Stage 2 backend features:

1. STT proxy/job service.

   Handles auth/session propagation, upload limits, provider key injection,
   provider call, result normalization, typed errors, cancellation and usage
   event emission.

2. Provider adapter layer.

   Starts with Lemonfox STT, keeps room for OpenAI STT fallback or another
   provider. Provider-specific options stay server-side.

3. Feature permission / policy resolver.

   Uses OpenWebUI user/group context where possible, but makes final decisions
   server-side. Covers STT, web-search, OCR/provider catalog and sensitive data
   warnings.

4. Usage event collector.

   Records normalized usage across LLM, web-search, STT and storage/files. This
   is not hard billing; it is the foundation for admin review and possible
   future LiteLLM/gateway decision.

5. Retention and file lifecycle worker.

   Deletes temporary audio blobs, avoids raw media retention by default, and
   records what was retained. This prevents accidental storage drift.

6. Transcript normalization module.

   Converts provider responses into `TranscriptResultV1`. UI, prompts and export
   templates use only the normalized shape.

7. Internal health/smoke endpoints.

   Expose safe readiness checks for adapter availability, configured provider
   class, and storage/temp cleanup status. Do not expose secrets.

8. Correlation/audit metadata.

   Adds a correlation id across upload, provider call, usage event and transcript
   result. This is enough for support/debug without storing sensitive raw media.

9. Optional async callback receiver.

   Only if long Lemonfox jobs or another provider require callback flow. This
   should be a second slice after short-file smoke passes.

Deferred backend features:

- hard per-user billing enforcement;
- full immutable audit archive;
- full masking/tokenization;
- complex OCR/layout production pipeline;
- deep OpenWebUI fork;
- direct provider calls from browser.

## 2.4. Upgrade-safe OpenWebUI strategy

To keep future OpenWebUI updates practical, Stage 2 should follow these rules:

1. Treat OpenWebUI as upstream-owned.

   Do not modify core OpenWebUI internals unless there is no acceptable native
   or sidecar path.

2. Prefer sidecar/internal backend routes.

   Put custom APIs under a clearly owned prefix, for example
   `/stage2-api/...`, behind the same domain/reverse proxy. OpenWebUI UI or
   tools call this API; the custom backend owns provider/security contracts.

3. Keep database ownership separate.

   Prefer separate Stage 2 tables/schema/database for jobs, usage events,
   retention metadata and transcripts. Avoid altering OpenWebUI tables unless
   the upstream extension path requires it.

4. Use OpenWebUI identity, do not duplicate identity.

   Reuse OpenWebUI session/user/group context or an approved reverse-proxy
   identity handoff. The Stage 2 backend should verify identity but should not
   create a parallel user system.

5. Keep the UI integration thin.

   UI should upload files, show status, render transcript and call templates.
   It should not contain provider selection logic, provider keys, retention
   rules or policy decisions.

6. Version the contracts.

   Use `TranscriptResultV1`, `UsageEventV1`, `PolicyDecisionV1`,
   `TranscriptionJobV1`. If a later implementation changes shape, add `V2`
   rather than silently breaking existing UI/templates.

7. Add compatibility smoke before every OpenWebUI update.

   Minimum smoke: login/session, group permission, STT job create, STT result
   read, usage event, temp cleanup, no key in browser network, web-search basic
   check if enabled.

8. Keep provider config externalized.

   Provider base URLs, model IDs, feature flags and limits should live in
   deploy config/admin config, not in patched UI code.

This strategy does not eliminate integration work, but it keeps the blast radius
small. Updating OpenWebUI should mostly require rerunning smoke checks and
adjusting one thin integration point, not rebasing a broad product fork.

## 3. Files reviewed

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/decisions/*.md`
- `docs/stage2/blueprints/*.md`
- `docs/stage2/research/*.md`
- `docs/reports/2026-06-18/*.md`

## 4. Files changed

Navigation and planning:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`

Acceptance and ADR:

- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/stage2/decisions/README.md`
- `docs/stage2/decisions/ADR-0001-data-policy-by-provider-class.md`
- `docs/stage2/decisions/ADR-0002-manager-visibility-policy.md`
- `docs/stage2/decisions/ADR-0003-chat-deletion-retention-audit.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/decisions/ADR-0005-ocr-vl-ocr-pilot-scope.md`
- `docs/stage2/decisions/ADR-0006-provider-model-catalog.md`
- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
- `docs/stage2/decisions/ADR-0008-native-analytics-vs-hard-billing.md`

Format cleanup also touched PRD, customer summary, blueprints, research and
reports where long non-table paragraphs were wrapped.

## 5. Markdown cleanup performed

- Replaced wide `CONTEXT_INDEX.md` table with per-domain sections.
- Replaced wide `DOMAIN_MAP.md` table with per-domain cards.
- Replaced wide `ACCEPTANCE_MATRIX.md` table with per-requirement sections.
- Wrapped long plain paragraphs and list items.
- Kept markdown tables for financial/pricing and hour estimates to preserve
  numeric integrity.
- Kept table separators as markdown tables where tables remain.
- Preserved UTF-8 BOM for Russian markdown files.

## 6. ADR registry vs execution order

ADR registry order is now documented separately from execution/review order.

Registry order:

1. ADR-0001 Data Policy by Provider Class.
2. ADR-0002 Manager Visibility Policy.
3. ADR-0003 Chat Deletion, Retention and Audit.
4. ADR-0004 STT Proxy Boundary.
5. ADR-0005 OCR / VL OCR Pilot Scope.
6. ADR-0006 Provider Model Catalog.
7. ADR-0007 Web-search Provider.
8. ADR-0008 Native Analytics vs Hard Billing.

Recommended execution / review order:

1. Data Policy by Provider Class.
2. STT Proxy Boundary.
3. Provider Model Catalog.
4. Web-search Provider.
5. Manager Visibility Policy.
6. Chat Deletion / Retention / Audit.
7. OCR / VL OCR Pilot Scope.
8. Native Analytics vs Hard Billing.
9. Runtime proof matrix.
10. Customer test data package.
11. Implementation backlog by slices.

Numbers are registry order. Execution order reflects implementation
dependencies.

## 7. ADR stubs created/updated

Updated to unified stub format:

- ADR-0001 Data Policy by Provider Class.
- ADR-0002 Manager Visibility Policy.
- ADR-0003 Chat Deletion, Retention and Audit.

Created:

- ADR-0004 STT Proxy Boundary.
- ADR-0005 OCR / VL OCR Pilot Scope.
- ADR-0006 Provider Model Catalog.
- ADR-0007 Web-search Provider.
- ADR-0008 Native Analytics vs Hard Billing.

All ADRs remain `Status: Proposed`.

## 8. Implementation Gates added

Created:

- `docs/stage2/IMPLEMENTATION_GATES.md`

The gates cover:

- Data Policy approval;
- STT Proxy Boundary;
- Provider Model Catalog;
- Web-search Provider;
- Manager Visibility and Retention policy;
- OCR / VL OCR pilot scope;
- runtime proof;
- customer test data package;
- implementation slices.

No gate is marked completed without evidence.

## 9. Navigation updates

Added Implementation Gates links to:

- root `README.md`;
- `docs/stage2/README.md`;
- `docs/stage2/CONTEXT_INDEX.md`;
- `docs/stage2/ROADMAP.md`.

Updated `docs/stage2/decisions/README.md` with registry order and execution
order.

## 10. Backlog updates

`ENGINEERING_BACKLOG.md` now explicitly includes:

- Ready for ADR: Data Policy, STT Proxy, Provider Model Catalog, Web-search,
  Manager Visibility, Chat Deletion/Retention/Audit, OCR/VL OCR, Native
  Analytics vs Hard Billing.
- Ready for runtime proof: OpenWebUI capability audit, RBAC/groups proof,
  no-delete UI/API proof, manager visibility matrix, native analytics proof,
  web-search smoke, STT proxy smoke plan, document extraction/OCR smoke after
  test data.
- Blocked by customer input: broker reports, good Claude result, audio/video,
  scanned PDF, PDF with tables, XLSX, group/role matrix, provider accounts/keys
  and data policy examples.
- Deferred/future: full masking/tokenization, local LLM/NER masking, hard
  billing/gateway, production OCR/layout pipeline, complex Excel parser,
  production DOCX/XLSX generation, full AD lifecycle/SCIM, immutable audit
  archive and deep OpenWebUI fork.

## 11. Non-goals preserved

- No implementation started.
- No code changed.
- No production changes.
- No provider setup.
- No `.env` or secrets read/printed.
- No compose/env/scripts changes.
- No PRD-1 semantic scope change.
- No financial figures changed.
- No future slices moved into Practical Stage 2.
- No production OCR/layout pipeline promised.
- No hard billing/gateway promised.
- No full data masking/tokenization promised.
- No deep OpenWebUI fork made mandatory.

## 12. Checks performed

Checks are recorded in the final agent response for the exact committed state.

Planned checks before commit:

- docs-only scope;
- no source/compose/env/scripts changes;
- root README navigation;
- Stage2 README navigation;
- `IMPLEMENTATION_GATES.md` exists and is linked;
- ADR-0001..ADR-0008 exist;
- ADR registry order and execution order separated;
- markdown table shape;
- no trailing whitespace;
- secret-like assignment scan;
- UTF-8 BOM spot check;
- `git diff --check`;
- push to `origin/main`.

## 13. Final status

Stage 2 docs are now formatted for review and ready for ADR work.
Implementation is still blocked by ADR approval, runtime proof and customer test
data.

Additional engineering position is now recorded in this report:

- backend-first contracts before final UI work;
- STT proxy/job contract instead of direct browser-to-provider calls;
- provider adapter and transcript normalization server-side;
- policy, permission, usage and retention decisions owned by backend;
- OpenWebUI kept upgrade-safe by isolating Stage 2 custom logic behind
  sidecar/internal backend APIs or a minimal integration shim.

The next useful action is to promote the STT contract proposal into ADR-0004 and
then validate it against the actual existing ffmpeg workflow artifact.
