# OpenWebUI Stage 2 Domain Boundaries and Format Refine Report

## 1. Summary

Stage 2 docs are now aligned around domain isolation and contract boundaries.
The documentation also received another physical markdown cleanup pass for the
Stage 2 domain files that were still hard to review in raw/GitHub view.

No implementation was started. No source code, frontend, backend service,
provider setup, production config, compose/env/scripts or `.env` files were
changed or inspected.

Final status: Stage 2 docs are now physically formatted for review and aligned
around domain isolation / contract boundaries. Next recommended step:
`ADR-0004 STT Proxy Boundary review + inspection contract existing ffmpeg workflow artifact`.

## 2. Why refine was needed

The previous Stage 2 docs already stated backend-first delivery, but the
architecture principle was still spread across reports, roadmap text and ADR
stubs.

This created three risks:

- future implementation could patch OpenWebUI core too deeply;
- UI could accidentally become the owner of provider keys, policy, retention or
  usage accounting;
- provider-specific responses could leak into prompts/templates instead of being
  normalized behind internal contracts.

The refine creates a single Stage 2 contract-boundary entrypoint and links it
from navigation, roadmap, gates, decisions and ADR-0004.

## 3. Files reviewed

Required files reviewed:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/decisions/README.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`
- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_DOCS_FORMAT_AND_GATES_REFINE.report.md`
- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_BACKEND_FIRST_VL_OCR_REFINE.report.md`
- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md`

No required file was missing.

## 4. Files changed

Navigation and domain docs:

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`

Decisions:

- `docs/stage2/decisions/README.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`

Research formatting:

- `docs/stage2/research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md`
- `docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md`

Reports:

- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_DOMAIN_BOUNDARIES_AND_FORMAT_REFINE.report.md`

## 5. Physical markdown cleanup

The cleanup focused on raw markdown readability:

- `CONTEXT_INDEX.md` remains per-domain sections, not a wide table.
- `IMPLEMENTATION_GATES.md` current status changed from a wide table to per-gate
  sections.
- `docs/stage2/README.md` research snapshot changed from a wide table to
  per-topic sections.
- Provider catalog and web-search research decision tables changed to
  per-option sections.
- Headings remain on their own lines.
- List items remain one item per line.
- Tables that remain are normal markdown tables, not code fences.

The PRD/customer summary pricing and hour tables were not rewritten here,
because this task targeted the Stage 2 engineering domain and the numeric tables
are easier to review as tables.

## 6. Domain isolation changes

The following principle is now recorded in Stage 2 navigation and planning docs:

Stage 2 custom capabilities must be isolated behind explicit backend contracts.
OpenWebUI remains the upstream product shell; custom Stage 2 logic should live
in bounded domain services, internal APIs, or thin integration shims. The
frontend must not own security, provider keys, data policy, retention, manager
visibility or usage accounting.

The boundary map separates:

- OpenWebUI core;
- Stage 2 backend/domain services;
- frontend/thin UI;
- external providers;
- storage/retention;
- admin/operator surface.

## 7. Contract boundaries document

Created:

- `docs/stage2/CONTRACT_BOUNDARIES.md`

It defines:

- purpose and principles;
- boundary map;
- draft internal contracts;
- contract versioning rule;
- anti-patterns;
- first STT contract to define;
- related docs.

Draft contracts listed there:

- `TranscriptionJobV1`
- `TranscriptResultV1`
- `UsageEventV1`
- `PolicyDecisionV1`
- `ProviderModelCatalogV1`
- `DocumentExtractionResultV1`
- `ManagerVisibilityPolicyV1`
- `RetentionPolicyV1`

## 8. ADR-0004 updates

`ADR-0004 STT Proxy Boundary` now explicitly states:

- OpenWebUI remains the upstream product shell;
- STT custom logic should live behind backend contracts;
- frontend must not own provider keys, policy, retention or usage;
- job-based STT proxy boundary is the recommended direction;
- endpoint names are draft and depend on OpenWebUI auth/routing proof;
- browser never calls Lemonfox directly;
- provider keys live server-side only;
- ffmpeg workflow contract must be inspected before implementation.

Added contract candidates:

- `TranscriptionJobV1`
- `TranscriptResultV1`
- `UsageEventV1`
- `PolicyDecisionV1`

Added draft endpoint boundary:

- `POST /stage2-api/transcription/jobs`
- `GET /stage2-api/transcription/jobs/{job_id}`
- `GET /stage2-api/transcription/jobs/{job_id}/result`
- `POST /stage2-api/transcription/jobs/{job_id}/cancel`

## 9. Context index updates

`CONTEXT_INDEX.md` now includes a dedicated section for domain isolation and
contract boundaries.

It also links `CONTRACT_BOUNDARIES.md` from:

- general Stage 2 scope;
- transcription / STT context.

The context index remains section-based and grep/search friendly.

## 10. Navigation updates

Links to `CONTRACT_BOUNDARIES.md` were added to:

- root `README.md`;
- `docs/stage2/README.md`;
- `docs/stage2/CONTEXT_INDEX.md`;
- `docs/stage2/ROADMAP.md`;
- `docs/stage2/IMPLEMENTATION_GATES.md`;
- `docs/stage2/decisions/README.md`;
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`.

## 11. Non-goals preserved

This task did not do:

- implementation;
- UI work;
- backend service work;
- API endpoint implementation;
- provider setup;
- production changes;
- OpenWebUI fork;
- data masking implementation;
- hard billing implementation;
- OCR provider integration;
- manager visibility implementation;
- no-delete implementation.

## 12. Checks performed

Checks performed before commit:

- `git status --short`;
- docs-only scope;
- no source code changes;
- no compose/env/scripts changes;
- `.env` not read or printed;
- `CONTRACT_BOUNDARIES.md` exists;
- `CONTEXT_INDEX.md` is not a wide-table-only file;
- `ADR-0004` contains contract candidates;
- README or Stage 2 README links to contract boundaries;
- raw markdown long-line scan for Stage 2 docs;
- markdown table shape check;
- trailing whitespace check;
- secret-like assignment scan;
- `git diff --check`;
- UTF-8 BOM check for changed markdown files.

Markdown tools:

- `markdownlint-cli2`: not installed;
- `markdownlint`: not installed;
- `prettier`: not installed.

## 13. Final status

Stage 2 docs are now physically formatted for review and aligned around domain
isolation / contract boundaries.

Next recommended step:
`ADR-0004 STT Proxy Boundary review + inspection contract existing ffmpeg workflow artifact`.
