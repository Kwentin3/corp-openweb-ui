# OpenWebUI PRD-1 Source of Truth Sync Report

## 1. Summary

PRD-1, customer summary and Stage 2 engineering domain were synchronized for implementation planning. The work was documentation-only: no code, provider setup, compose/env/scripts, runtime or production changes were made.

## 2. Why sync was needed

`docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md` is the approved Stage 2 source of truth, but parts of the document still looked like an older draft. The Stage 2 domain and customer summary already reflected the newer agreed scope: transcription through existing ffmpeg workflow plus server-side STT proxy, OCR/layout-aware PDF pilot, manager visibility policy, chat deletion check, basic analytics, and data masking as future scope.

## 3. Files reviewed

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`
- `docs/stage2/blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md`
- `docs/stage2/blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md`
- `docs/stage2/blueprints/SECURITY_DATA_POLICY.blueprint.md`
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/research/DATA_MASKING_FUTURE_RESEARCH.md`
- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md`

Missing during review:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_REFINED.md`

The repository now uses `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md` as the final approved PRD-1 and keeps earlier context in `OPENWEBUI_CORPORATE_CHAT_PRD_1_INITIAL_DRAFT.md` and `OPENWEBUI_CORPORATE_CHAT_PRD_1_CHANGELOG.md`.

## 4. Files changed

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/reports/2026-06-18/OPENWEBUI_PRD1_SOURCE_OF_TRUTH_SYNC.report.md`

No `docs/stage2/*` file required content changes in this pass.

## 5. Key sync changes

### PRD status/source-of-truth

- PRD-1 status was updated to `customer-approved Stage 2 PRD / source of truth`.
- PRD-1 now links to customer summary, Stage 2 engineering domain, research actualization report and this sync report.
- README now links to this sync report.

### STT/ffmpeg/proxy

- PRD-1 keeps transcription audio/video as a Practical Stage 2 deliverable.
- Existing ffmpeg workflow remains a technical asset to adapt, not a research idea from scratch.
- A boundary map was added:
  - browser owns file type detection, local media preprocessing, audio extraction/conversion and progress/cancel UX;
  - server-side STT proxy owns auth, permissions, API key handling, provider call, transcript normalization, errors and optional persistence/audit;
  - STT provider owns transcription, timestamps and speaker labels when available.
- API keys are explicitly kept out of the browser.

### Data masking

- Data masking/tokenization remains future security/data-protection scope.
- Practical Stage 2 remains limited to data policy, warnings, provider-class rules, manual anonymization guidance and future architecture note.
- The false-security risk of superficial tag replacement is preserved.

### Claude API wording

- PRD-1 and summary use `Claude API / Claude models` for the chat provider scope.
- `Claude Code` remains documented only as a separate developer/agentic coding tool, not an OpenWebUI employee chat provider.

### OCR pilot

- OCR/layout-aware PDF pilot remains in Practical Stage 2.
- Production-grade OCR/layout pipeline remains a future/optional slice.
- Customer documents remain required for runtime proof.

### Manager visibility

- Manager visibility remains a Stage 2 requirement/check with privacy/security policy.
- It does not mean managers see all personal or draft chats.
- Native OpenWebUI capability still requires runtime proof and policy decision.

### Chat deletion

- Chat deletion restriction remains a technical check.
- The target is to verify whether user chat deletion can be restricted to admins or assigned roles.
- If native support is insufficient, fallback options remain policy, backup/retention, audit/export, minimal patch or future implementation.

### Web-search

- Web-search remains intended for all users, but only with rules, result count, concurrency, cost visibility, provider policy and unsafe-use instructions.
- Brave `brave_llm_context` remains the likely first pilot if approved.
- Yandex Search API remains the Russian search-provider candidate.
- Yandex Search is kept separate from YandexGPT/GigaChat LLM provider decisions.

### Providers

- Production/required candidates remain OpenAI GPT-mini exact ID to confirm, Claude API / Claude models, and DeepSeek as mandatory alternative.
- YandexGPT and GigaChat remain research candidates; one Russian provider should be selected after research and policy/procurement decision.
- Exact model IDs must be confirmed before setup.

### AD/SSO

- AD/SSO remains discovery/optional for Practical Stage 2.
- Full AD lifecycle / SCIM rollout remains future scope.

### Billing/analytics

- Basic analytics / cost visibility remains in Practical Stage 2.
- Hard billing, LiteLLM/gateway, virtual keys and guaranteed blocking remain optional/future until separate ADR/decision.

### Markdown cleanup

- PRD-1 header and source sections were updated so the document no longer reads as an old enriched draft.
- New boundary table was added with a standard GitHub-compatible header separator.
- PRD-1 and customer summary table structure was checked for header/separator formatting.

## 6. What remains for ADR

- STT proxy boundary ADR
- Web-search provider ADR
- Provider model catalog ADR
- Manager visibility/no-delete ADR
- OCR pilot ADR
- Analytics vs hard billing ADR
- Data policy ADR

## 7. What remains for runtime proof

- OpenWebUI deployed version feature proof
- STT proxy smoke
- Lemonfox test
- Web-search smoke
- RBAC/manager visibility test
- Chat deletion UI/API test
- Native analytics proof
- OCR extraction test on customer docs

## 8. Non-goals preserved

- No implementation started.
- No code changed.
- No provider was connected.
- No production or server changes were made.
- No compose/env/scripts were changed.
- No `.env` or secrets were read or printed.
- Data masking/tokenization was not moved into Practical Stage 2 implementation.
- Hard billing/gateway, full AD lifecycle/SCIM and production OCR/layout pipeline remain outside Practical Stage 2 unless separately approved.

## 9. Final status

PRD-1, customer summary and Stage 2 engineering domain are now synchronized for implementation planning.
