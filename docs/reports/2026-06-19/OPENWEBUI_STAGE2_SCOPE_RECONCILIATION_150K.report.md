# OpenWebUI Stage 2 Scope Reconciliation Report

## 1. Summary

Подготовлен scope reconciliation для limited Stage 2 tranche.

Политика коммерческой документации:

```text
GitHub-документация фиксирует состав работ, трудозатраты, статусы,
доказательства и ограничения. Денежные суммы, график оплаты и финансовые
условия фиксируются только в договорах, счетах и актах и не хранятся в
markdown-документации репозитория.
```

Вывод: текущие фактически выполненные работы нельзя корректно описывать ни как "только STT + Web Search", ни как "полный PRD-1 завершен". Корректная договорная рамка:

**Этап 2. Часть 1: первый функционально-архитектурный срез Stage 2 корпоративного OpenWebUI**

Подзаголовок:

**Включает реализованные модули транскрибации аудио/видео и базового Web Search, а также архитектурную подготовку дальнейших направлений Stage 2.**

Основной документ:

- scope reconciliation commercial file

## 2. Sources Reviewed

Проверены PRD, Stage 2 docs, commercial audit, acceptance/gates/backlog и runtime reports:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- completed-work commercial audit file
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`
- STT runtime, Playwright and closure reports from `docs/reports/2026-06-19/`
- Web Search Brave, Yandex, SearXNG and provider closeout reports from `docs/reports/2026-06-23/`
- `services/stage2-stt/`
- `deploy/openwebui-static/loader.js`
- `compose/searxng.private.compose.yml`
- `deploy/searxng/`

No secrets, private tokens, transcript contents, SSH details or administrative credentials were copied into the reconciliation output.

## 3. PRD-1 Directions Mapped

Mapped PRD-1 directions: 15.

Mapped directions:

1. Корпоративная рабочая среда / workspace model.
2. Groups/RBAC/access.
3. Shared prompts/templates/knowledge.
4. Model catalog/provider policy.
5. STT / transcription.
6. Web Search.
7. Documents: PDF/DOCX/XLSX.
8. OCR / VL OCR / layout-aware PDF.
9. Broker reports / 3-НДФЛ.
10. Manager visibility / read-only access to work chats.
11. No-delete / retention / audit.
12. Data policy / provider class policy.
13. Analytics / cost visibility.
14. User/admin docs.
15. Acceptance/smoke/gates/backlog.

Statuses used:

- `DONE_FEATURE`
- `DONE_ARCHITECTURE`
- `DONE_BASELINE`
- `PARTIAL`
- `RESEARCH_ONLY`
- `PLANNED_FUTURE`

`OUT_OF_TRANCHE` was not required as the primary status because future exclusions are represented through `RESEARCH_ONLY` and `PLANNED_FUTURE`, with explicit exclusion wording.

## 4. Actual Done vs Planned Findings

Completed user-facing capabilities:

- STT / transcription is `DONE_FEATURE` for current-stage MVP.
- Web Search is `DONE_BASELINE` as an LLM search tool baseline with three provider paths.

Completed architecture/documentation work:

- Stage 2 decomposition and context navigation.
- Extension-first integration pattern.
- STT proxy boundary.
- Provider adapter pattern.
- Input normalization contract.
- Web Search privacy/source/usage contracts.
- Acceptance matrix, implementation gates and backlog actualization.
- Runtime and smoke reports for the accepted current slice.

Important Web Search finding:

- Brave/Yandex provider paths were relatively simple through native API/config/Admin GUI routes.
- SearXNG required more substantial private infrastructure preparation, including compose/config artifacts and private runtime smoke.
- The baseline is implemented, but full rollout governance is not complete.

Not completed as full PRD-1:

- managed workspace model;
- full groups/RBAC rollout;
- shared prompts/templates/knowledge catalog;
- production document pipeline;
- production OCR/VL OCR;
- broker reports and 3-НДФЛ;
- manager read-only visibility;
- no-delete/retention/audit;
- data masking;
- analytics/cost visibility;
- hard billing/gateway;
- AD/SSO;
- full Web Search policies/logs/limits/forbidden-query/cost governance.

## 5. Recommended Limited Tranche Scope

Recommended tranche title:

**Этап 2. Часть 1: первый функционально-архитектурный срез Stage 2 корпоративного OpenWebUI**

Included in the limited tranche scope:

- STT/media transcription capability.
- Web Search baseline capability.
- Brave provider baseline.
- Yandex Search API provider path.
- private SearXNG provider path and infrastructure artifacts.
- stage2-stt sidecar.
- static loader and ffmpeg.wasm assets.
- Lemonfox backend provider path.
- Stage 2 architecture decomposition.
- STT and Web Search boundary contracts.
- acceptance matrix, implementation gates, backlog and reports.

This framing is commercially safer than narrowing the tranche to only "STT + Web Search", because it recognizes the architecture and acceptance work already performed.

This framing is also safer than claiming full Stage 2 completion, because the full PRD-1 remains materially broader.

## 6. Key Exclusions

Exclude from the current limited tranche as completed deliverables:

- full PRD-1 completion;
- full managed corporate workspace;
- full groups/RBAC/access governance;
- prompts/templates/knowledge production catalog;
- document pipeline PDF/DOCX/XLSX;
- OCR/VL OCR/layout-aware PDF production or accepted pilot;
- broker reports/3-НДФЛ;
- manager visibility/read-only work chat access;
- no-delete/retention/audit as compliance-ready feature;
- hard billing/gateway;
- AD/SSO;
- data masking/tokenization/local NER;
- analytics and cost visibility;
- full Web Search rollout governance;
- Web Search policies/logs/limits;
- forbidden-query policy;
- full provider quality matrix;
- STT mobile, long-file, low-memory, cancel, persistence, history/export hardening.

## 7. Contract Preparation Readiness

Contract preparation is ready if the contract follows the reconciliation document and avoids overclaiming:

- use the recommended tranche title;
- include STT and Web Search baseline as user-visible delivered capabilities;
- include architecture, contracts, gates, backlog and reports as completed work;
- explicitly mark full PRD-1 as future scope;
- keep any relationship with existing external act/invoice documents outside GitHub markdown, in the parties' contract documents;
- avoid duplicating already paid work.

Any existing external act/invoice should not be described as completion of the full Stage 2. Its financial treatment belongs only in contract documents outside GitHub.

## 8. Final Verdict

The Stage 2 limited-tranche reconciliation is ready for contract draft preparation.

Final verdict:

`stage2_150k_scope_reconciliation_ready_for_contract_draft`
