# OpenWebUI Stage 2 Completed Work Audit 150K Report

## 1. Summary

Created a commercial audit/scope document for the already completed Stage 2 Tranche 1 work:

```text
docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md
```

The document frames the completed and proven work as a limited 150 000 ruble tranche: OpenWebUI media transcription module with browser media normalization, server-side STT sidecar, OpenWebUI Action integration, Lemonfox adapter, plus Web Search provider baseline work for Brave, Yandex and private SearXNG.

The document does not claim that full PRD-1 / Practical Stage 2 is complete.

## 2. Sources reviewed

Commercial and PRD sources:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_0.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`

Stage 2 / STT implementation reports:

- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_BROWSER_NORMALIZATION_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FRONTEND_MEDIA_ACTION_PATCH.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_DOCS_IMPLEMENTATION_DRIFT_AUDIT.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_RUNTIME_COMPLETION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_PLAYWRIGHT_UI_PROOF.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_MEDIA_ATTACHMENT_STT_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_BACKEND_IMPLEMENTATION.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_FFMPEG_INPUT_FORMAT_CONTRACT_REFINE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_MEDIA_ATTACHMENT_STT_ACTION_REFINE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_NATIVE_STT_UX_INTEGRATION_RESEARCH.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_SIDECAR_ROUTING_AUTH_AUDIT.report.md`

Closure/context sources:

- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`

Code/config proof paths inspected:

- `deploy/openwebui-static/loader.js`
- `deploy/openwebui-static/stage2-stt-normalization.json`
- `scripts/fetch-ffmpeg-wasm-assets.sh`
- `compose/openwebui.compose.yml`
- `services/stage2-stt/`
- `services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py`
- `services/stage2-stt/tests/`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`
- `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md`
- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md`
- `compose/searxng.private.compose.yml`
- `deploy/searxng/settings.yml`
- `deploy/searxng/limiter.toml`
- `.env.example`

All requested paths were present.

## 3. Completed work identified

Completed / claimable work:

- architecture and contracts for server-side STT boundary;
- extension-first implementation pattern;
- private `stage2-stt` backend sidecar;
- job/capabilities routes and internal auth boundary;
- Lemonfox provider adapter through `SttProviderAdapterFactory`;
- runtime capabilities contract;
- validation and safe typed errors;
- OpenWebUI Action Function path;
- static loader `Транскрибировать` action for media attachments;
- browser ffmpeg.wasm normalization with self-hosted assets;
- prepared MP3 passthrough;
- MP4/WebM generated proof media;
- unsupported/no-audio safe errors;
- OpenWebUI to sidecar runtime wiring;
- Lemonfox live smoke through sidecar path;
- Playwright proof;
- targeted pytest coverage;
- Stage 2/STT documentation actualization and closure context pack;
- native OpenWebUI Web Search domain/contracts/acceptance package;
- Brave `brave_llm_context` direct-context runtime baseline;
- Yandex Search API working RU direct API path by owner/operator confirmation;
- private SearXNG internal meta-search runtime smoke in snippet/bypass mode;
- optional SearXNG compose/config artifacts and operator recovery documentation;
- Brave / Yandex / private SearXNG candidate-set comparison plan.

## 4. Partial/future work separated

Partial / hardening:

- mobile browser testing;
- large/customer media testing;
- low-memory browser behavior;
- long files / practical 1 GB behavior;
- browser ffmpeg cancel;
- upload/job cancel and late-result cleanup;
- durable persistence beyond in-memory job store;
- production storage/retention/cleanup policy;
- Opus provider/default proof;
- transcript history/export/workflow;
- multi-user/group permission hardening;
- monitoring, structured logs and usage/cost events;
- full Web Search production rollout for all users;
- Web Search ordinary-user allow/deny permissions;
- full EN/RU Brave/Yandex/SearXNG comparative matrix;
- Web Search forbidden-query, logging/retention and cost-visibility gates;
- Yandex privacy/data-egress and metadata-forwarding review;
- SearXNG promotion beyond comparison track;
- full page loading and vectorized `web-search-*` retrieval.

Future / out of this 150 000 ruble tranche:

- full Practical Stage 2;
- workspaces/groups/prompts/knowledge;
- full Web Search rollout for all users beyond the completed provider baselines;
- OCR/layout-aware PDF pilot;
- broker reports / 3-NDFL workflow;
- hard billing/gateway;
- full AD/SSO lifecycle;
- full data masking/tokenization;
- production document pipeline;
- production audit/retention archive;
- meeting transcription workspace/history/export.

## 5. Commercial scope created

Created the recommended commercial scope:

```text
Этап 2. Часть 1: транскрибация аудио/видео и базовый веб-поиск в корпоративном OpenWebUI
```

Cost framed as:

```text
150 000 рублей.
```

The amount is explicitly limited to the audited tranche and does not include the full PRD-1 scope or external runtime/API/server/provider costs.

## 6. Contract/act wording prepared

Prepared contract wording with:

- subject of work;
- scope of work;
- result of work;
- limitations;
- cost.

The wording now includes both STT and Web Search provider baseline work.

Prepared act wording with:

- completed work statement;
- accepted result statement;
- 150 000 ruble amount;
- explicit limitation that the act does not close full PRD-1.

The act wording now mentions Brave, Yandex and private SearXNG as completed Web Search provider paths, while keeping full rollout and production policy gates outside the tranche.

## 7. Files changed

Created:

- `docs/commercial/STAGE2_COMPLETED_WORK_AUDIT_150K.md`
- `docs/reports/2026-06-19/OPENWEBUI_STAGE2_COMPLETED_WORK_AUDIT_150K.report.md`

No code, compose, env, historical report, or PRD source file was changed by this task.

## 8. Final verdict

```text
stage2_tranche1_150k_completed_work_audit_ready
```
