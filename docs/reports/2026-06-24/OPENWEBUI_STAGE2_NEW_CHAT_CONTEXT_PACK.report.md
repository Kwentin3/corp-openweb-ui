# OpenWebUI Stage 2 New Chat Context Pack Report

Date: 2026-06-24

Verdict: `stage2_context_pack_ready_web_search_closed_for_provider_baseline`

## 1. Executive Summary

Created a restart-safe Stage 2 / OpenWebUI context pack:

`docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STAGE2_OPENWEBUI.md`

The pack is based on current repo evidence, existing Stage 2 docs and the
2026-06-19 / 2026-06-23 reports. It confirms:

- STT MVP is implemented/proven/current-stage closed.
- Web Search provider connectivity baseline is closed for the current stage.
- Web Search rollout is still pending.
- Brave is the current native direct-context baseline.
- Yandex is a working RU direct API path by owner/operator confirmation, with
  weaker proof than Brave.
- Private SearXNG works as a private native meta-search comparison path in
  snippet/bypass mode.
- The next Web Search step, if continued, is three-path comparison plus rollout
  gates.
- If Web Search pauses, the next epic should come from PRD-1 roadmap/backlog;
  data policy plus provider/model catalog is the strongest governance-first
  candidate.

No production code was written. No runtime was changed. No live smoke was run.
No real `.env`, provider key, admin credential, token, private URL or customer
data was read or printed.

## 2. Repo State

Commands requested by the task were run before writing the pack.

```text
git status --short --branch
## main...origin/main
 M .env.example
 M README.md
 M compose/openwebui.compose.yml
 M compose/searxng.private.compose.yml
 M deploy/searxng/limiter.toml
 M docs/infra/DOCKER_COMPOSE_PLAN.md
 M docs/infra/ENVIRONMENT_VARIABLES.md
 M docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md
 M docs/stage2/CONTEXT_INDEX.md
 M docs/stage2/ENGINEERING_BACKLOG.md
 M docs/stage2/README.md
 M docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md
 M docs/stage2/acceptance/ACCEPTANCE_MATRIX.md
 M docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md
 M docs/stage2/blueprints/WEB_SEARCH.blueprint.md
 M docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md
 M docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md
 M docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md
 M docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md
 M docs/stage2/decisions/ADR-0007-web-search-provider.md
 M docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md
 M docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md
 M docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md
 M docs/stage2/research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md
 M docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md
?? docs/reports/2026-06-23/
```

```text
git rev-parse HEAD
7d0e02c24808f3501e7c92b0ce48fcee646aa393

git rev-parse origin/main
7d0e02c24808f3501e7c92b0ce48fcee646aa393

git ls-remote --heads origin
7d0e02c24808f3501e7c92b0ce48fcee646aa393 refs/heads/main
```

Remote state:

```text
origin https://github.com/Kwentin3/corp-openweb-ui.git
old-origin https://github.com/Kwentin3/corp-hermes.git
```

Recent commits:

```text
7d0e02c docs: prepare web search candidate comparison
7cbb9ed docs: prepare web search native pilot
be49bbd docs: add new chat context pack for stt stage
19710ed docs: close stt mvp feature stage
12426a7 fix: patch native web stt recorder
3482a4d fix: prevent native voice transcript duplication
39d2c19 fix: humanize stt storage warning
88e4bdd fix: probe stt source audio before handoff
2318042 docs: actualize stt docs after implementation
6a698ef docs: report stt ffmpeg browser normalization proof
```

Important repo-state note:

- `HEAD` and `origin/main` are synchronized.
- The working tree was already dirty before this task.
- The context pack uses current working-tree docs as evidence, including the
  dirty Web Search documentation/config package.
- Existing dirty files were not edited by this task.
- `.env.example` was listed as dirty by git, but real `.env` files were not read.

## 3. Files Read

Project / PRD / roadmap:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`

STT:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `docs/reports/2026-06-19/OPENWEBUI_NEW_CHAT_CONTEXT_PACK.report.md`
- related 2026-06-19 STT reports were scanned by headings/status terms.

Web Search:

- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`
- `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md`
- `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md`
- `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md`
- `docs/stage2/decisions/ADR-0007-web-search-provider.md`
- `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md`
- `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md`
- `docs/stage2/contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md`
- `docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`
- `docs/infra/ENVIRONMENT_VARIABLES.md`
- `docs/infra/DOCKER_COMPOSE_PLAN.md`
- `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_DOCS_REFINE_AFTER_BRAVE_SMOKE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_STAGE2_WEB_SEARCH_ANAMNESIS_AUDIT.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_ANAMNESIS_AUDIT.report.md`

Runtime/deployment references:

- `compose/openwebui.compose.yml`
- `compose/searxng.private.compose.yml`
- `deploy/searxng/settings.yml`
- `deploy/searxng/limiter.toml`

## 4. Assumptions Checked

| Assumption | Result |
| --- | --- |
| STT MVP is implemented/proven/current-stage closed | confirmed |
| STT production hardening is complete | not confirmed |
| Web Search provider connectivity baseline is closed | confirmed |
| Web Search user/production rollout is complete | not confirmed |
| Brave `brave_llm_context` works | confirmed by runtime baseline report |
| Yandex works | confirmed only by owner/operator report; full evidence pending |
| Private SearXNG works | confirmed by runtime smoke in snippet/bypass mode |
| SearXNG should become primary | not confirmed |
| SearXNG proves full page loading/vectorized retrieval | not confirmed |
| Next Web Search step is comparison plus rollout gates | confirmed by Web Search docs/reports |
| Next non-Web-Search epic should come from PRD/roadmap/backlog | confirmed |
| Provider keys may appear in browser/docs/logs | rejected by contracts and reports |

## 5. Confirmed Closed Items

- PRD-0 corporate chat base is accepted/closed.
- Stage 2 docs domain exists and is navigable.
- STT MVP current stage is closed:
  - private `stage2-stt` sidecar/job route;
  - OpenWebUI static `Transcribe` action;
  - browser ffmpeg.wasm normalization;
  - transcript return into OpenWebUI UX;
  - provider keys kept out of browser.
- Web Search provider connectivity baseline is closed:
  - Brave direct-context baseline works;
  - Yandex RU path works by owner/operator confirmation;
  - private SearXNG snippet/bypass path works.

## 6. Pending Items

Web Search:

- three-path comparison;
- rollout group scope;
- ordinary-user permission allow/deny proof;
- forbidden query policy;
- source cards and answer groundedness matrix;
- logs/retention review;
- browser exposure checks for provider keys;
- cost visibility/budget guardrails;
- Yandex metadata/cost-mode review;
- SearXNG engine tuning and image pinning if it stays valuable;
- vectorized retrieval and full page loading only if product scope needs them.

STT:

- production hardening;
- mobile/low-memory/large customer media proof;
- cancel behavior;
- duration/cancel provider decisions;
- storage/retention policy;
- monitoring/logging/cost events;
- ADR-0004 human review/status decision.

Stage 2 core:

- data policy by provider class;
- provider/model catalog;
- RBAC/workspaces/shared prompts runtime proof;
- native analytics/cost visibility proof;
- documents/OCR/Excel customer samples;
- broker reports / 3-NDFL sample set and expected output;
- manager visibility/no-delete/retention owner policy.

## 7. Recommended Next Epics

If continuing Web Search:

1. Brave / Yandex / private SearXNG candidate-set comparison.
2. Web Search rollout gates: group scope, permissions, forbidden queries,
   source/groundedness, logs/retention and cost visibility.

If stopping Web Search for now:

1. Data policy by provider class plus provider/model catalog.
2. RBAC/workspaces/shared prompts runtime proof.
3. Native analytics/cost visibility proof.
4. Documents/OCR/Excel pilot only after customer samples arrive.
5. Broker reports / 3-NDFL scenario only after anonymized examples arrive.

Agent recommendation:

- Best next epic after closing Web Search baseline is data policy plus
  provider/model catalog, unless the owner explicitly wants to continue Web
  Search comparison immediately.
- This recommendation follows roadmap dependencies: provider setup, Web Search
  rollout, documents and cost governance all depend on provider/data policy.

Owner decisions needed:

- Continue Web Search now, or switch to Stage 2 governance/core configuration.
- Which groups get Web Search first.
- Which queries are forbidden.
- Whether Yandex metadata/cost mode is acceptable.
- Whether private SearXNG is worth ongoing operational cost.
- Whether native analytics is enough or hard budget enforcement is required.
- Which customer samples can be provided for documents/OCR/broker scenarios.

## 8. Files Created / Updated

Created:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STAGE2_OPENWEBUI.md`
- `docs/reports/2026-06-24/OPENWEBUI_STAGE2_NEW_CHAT_CONTEXT_PACK.report.md`

Existing dirty files were intentionally not modified:

- `README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/README.md`
- Web Search docs/config files already dirty before this task.

Reason: the requested outputs had explicit canonical paths. Avoiding extra
navigation edits keeps this handoff separate from the pre-existing dirty Web
Search package.

## 9. Secrets / Sensitive Data Excluded

Excluded from the created files:

- real `.env` contents;
- real provider key values;
- admin credentials;
- private URLs;
- bearer tokens;
- customer data;
- raw sensitive queries;
- raw runtime logs with credentials or customer content.

The new context pack uses config concepts and non-secret image/path names only.

## 10. Final Verdict

`stage2_context_pack_ready_web_search_closed_for_provider_baseline`

The pack is ready for a new chat. It preserves the key boundaries:

- STT current-stage MVP is closed, not a fresh architecture task.
- Web Search provider baseline is closed, but rollout is pending.
- SearXNG is a private comparison path, not primary and not complete privacy.
- Yandex proof is weaker and remains owner/operator-confirmed until full
  evidence is captured.
- Next work should be selected explicitly from Web Search comparison/rollout
  gates or from PRD-1 roadmap/backlog.
