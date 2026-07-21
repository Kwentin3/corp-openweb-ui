# OpenWebUI Native Capability Runtime Audit

Date: 2026-06-24

Scope: Stage 2 / PRD-1 native OpenWebUI capabilities, deployed-version proof
and fit against PRD/blueprints/backlog.

Verdict: `native_first_path_confirmed_with_admin_runtime_gaps`

## 1. Executive Summary

Текущий стенд отвечает как OpenWebUI `0.9.6`. Публичные read-only endpoints
доступны, health проходит, Stage 2 STT static loader реально отдается с
публичного static path. Это подтверждает deployed version и наличие текущего
STT UI shim, но не заменяет Admin UI proof.

Нативные возможности OpenWebUI достаточно сильны, чтобы Stage 2 начинать без
fork/gateway:

- рабочие сценарии можно собрать из Workspace Models, Prompts, Knowledge,
  Groups/RBAC and access control;
- shared prompts/templates, knowledge bases and curated models являются
  configuration-first областями;
- Web Search уже имеет native provider baseline по Brave, Yandex и private
  SearXNG;
- native analytics является первым кандидатом для basic cost visibility;
- native STT полезен для микрофона/voice input, но не заменяет текущий Stage 2
  media attachment STT sidecar для аудио/видео-файлов.

Ключевые ограничения:

- admin/test-user runtime proof не был доступен в этом запуске;
- `/api/models` без авторизации возвращает `401`, поэтому model visibility,
  groups/RBAC, analytics, prompts, knowledge, no-delete and manager visibility
  не проверялись как admin/user matrix;
- OpenWebUI permissions are additive/union-based: deny-прав нет, ограничения
  нужно строить от минимальных global defaults и явных grants;
- manager visibility and no-delete нельзя считать закрытыми нативно без
  customer policy и runtime proof;
- documents/OCR/XLSX and broker reports нельзя принимать без customer samples.

Итог: native-first путь подтвержден как правильный. Следующий практический
шаг - admin/test-user runtime proof matrix на deployed `0.9.6`, затем
configuration-first план для workspaces/RBAC/prompts/knowledge/model catalog.
Новые production-фичи, Web Search rollout, LiteLLM/gateway и deep fork в этом
аудите не запускались и не требуются как ближайший шаг.

## 2. Repo State

Initial sanity pass:

```text
git status --short --branch
## main...origin/main

git rev-parse HEAD
3f23a0c5acb7c8634e229cb06b0837b26b0c59ea

git worktree list
<redacted-worktree> 3f23a0c [main]

git rev-list --left-right --count HEAD...origin/main
0 0
```

After `git fetch origin`, local `main` and `origin/main` remained synchronized.
Working tree was clean before audit edits.

No real `.env`, provider keys, tokens, admin credentials, private URLs or
customer data were read or printed.

## 3. Documents Read

Core PRD / TЗ:

- `README.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md`
- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md`

Stage 2 navigation:

- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md`

Current context and proposal:

- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STAGE2_OPENWEBUI.md`
- `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md`
- `docs/stage2/proposals/CUSTOMER_STAGE2_GOVERNANCE_PROPOSAL.md`

Acceptance and test data:

- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`

Relevant reports:

- `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md`
- `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md`
- `docs/reports/2026-06-24/OPENWEBUI_STAGE2_NEW_CHAT_CONTEXT_PACK.report.md`

Relevant blueprints/research/ADRs:

- `docs/stage2/research/OPENWEBUI_CAPABILITY_RESEARCH.md`
- `docs/stage2/research/RBAC_MANAGER_VISIBILITY_RESEARCH.md`
- `docs/stage2/research/CHAT_DELETION_RETENTION_RESEARCH.md`
- `docs/stage2/research/USAGE_ANALYTICS_BILLING_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`
- `docs/stage2/research/WEB_SEARCH_EXTERNAL_RESEARCH_2026-06-20.md`
- `docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md`
- `docs/stage2/blueprints/WORKSPACES_AND_RBAC.blueprint.md`
- `docs/stage2/blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md`
- `docs/stage2/blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md`
- `docs/stage2/blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md`
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`
- `docs/stage2/blueprints/WEB_SEARCH.blueprint.md`
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`
- `docs/stage2/decisions/ADR-0002-manager-visibility-policy.md`
- `docs/stage2/decisions/ADR-0003-chat-deletion-retention-audit.md`
- `docs/stage2/decisions/ADR-0006-provider-model-catalog.md`
- `docs/stage2/decisions/ADR-0008-native-analytics-vs-hard-billing.md`
- `docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md`
- `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md`

Runtime/deploy references:

- `compose/openwebui.compose.yml`
- `compose/searxng.private.compose.yml`
- `docs/ops/DEPLOYMENT_DECISIONS.md`

External official OpenWebUI docs checked on 2026-06-24:

- https://docs.openwebui.com/features/authentication-access/rbac/groups/
- https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- https://docs.openwebui.com/features/workspace/models/
- https://docs.openwebui.com/features/workspace/prompts/
- https://docs.openwebui.com/features/workspace/knowledge/
- https://docs.openwebui.com/features/administration/analytics/
- https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/stt-config/
- https://docs.openwebui.com/features/chat-conversations/rag/
- https://docs.openwebui.com/features/extensibility/plugin/tools/
- https://docs.openwebui.com/reference/env-configuration/

## 4. Runtime Access And Checks

Admin/staging credentials were not available in this run. No attempt was made
to read `.env` or recover credentials.

Local Docker:

```text
docker ps --format ...
NAMES IMAGE STATUS PORTS
```

No local containers were running, so no local Admin UI proof was possible.

Safe public deployed checks:

| Check | Result |
| --- | --- |
| `GET /` | `200`, HTML returned |
| `GET /api/config` | `200`, JSON keys include `status,name,version,default_locale,oauth,features`, version `0.9.6` |
| `GET /api/version` | `200`, version `0.9.6` |
| `GET /health` | `200`, status JSON |
| `GET /api/models` without auth | `401 Unauthorized` |
| `GET /static/loader.js` | `200`, contains `stage2_media_transcription_action` |
| `GET /static/stage2-stt-normalization.json` | `200`, version `stage2-stt-browser-normalization-v1` |

Interpretation:

- deployed OpenWebUI version is proven as `0.9.6`;
- public health is proven;
- Stage 2 static STT loader asset is present;
- unauthenticated model list is protected;
- admin-only capability surfaces remain unproven in this run.

## 5. Capability Domain Results

### 5.1 Workspaces / Workspace Models

Status: `native-with-configuration`, `needs-runtime-proof`.

Docs-backed finding:

- OpenWebUI Workspace Models can wrap a base model with system prompt,
  knowledge, tools/skills/actions and access control.
- This is enough to model "рабочий сценарий" as a curated model/scenario, not
  as a separate OpenWebUI product entity.
- Dynamic variables such as user/date/group context can support reusable
  scenario prompts.

Runtime status:

- public deployed version proof exists;
- admin Workspace Models UI and group visibility were not inspected.

Gap:

- no single native entity called "business workspace";
- scenario consistency depends on configuration discipline, naming, owner
  process and acceptance tests;
- exact deployed `0.9.6` UI/settings still need proof.

Recommendation:

- use Workspace Models as the scenario anchor;
- bind prompts/knowledge/skills/tools only after group and data policy are
  clear;
- start with three scenarios: general corporate chat, transcription, Web Search
  or broker/documents depending on customer test data.

### 5.2 Groups / RBAC / Access Control

Status: `native-with-configuration`, `needs-runtime-proof`.

Docs-backed finding:

- Groups support permission management and resource access control for private
  resources such as Models, Knowledge Bases and Tools.
- Permission logic is additive/union-based. If any source grants permission,
  the user has it. There are no deny permissions.
- Best practice is minimal global defaults and explicit grants by group.

Runtime status:

- `/api/models` is protected without auth;
- real admin group settings and ordinary-user visibility were not tested.

Gap:

- deny-rules do not exist;
- default permissions and group grants must be audited together;
- "manager of group" is not proven as a native role.

Recommendation:

- separate permission groups from sharing/business groups;
- do not rely on negative/deny logic;
- run a four-actor matrix: Admin, Manager/РО, employee inside group, employee
  outside group.

### 5.3 Shared Prompts / Templates

Status: `native-ready` by docs, `needs-runtime-proof` on deployed UI.

Docs-backed finding:

- Workspace Prompts support slash commands, input variable forms, system
  variables, version history, rollback, enable/disable and sharing with
  users/groups.
- This fits scenario templates for transcription summaries, document review,
  Web Search research and broker-report draft analysis.

Runtime status:

- no admin/user prompt workflow was tested in this run.

Gap:

- exact approval/change-control process is not a product default;
- prompt ownership and publication rules must be defined.

Recommendation:

- use native Prompts for shared templates;
- add owner, command name, intended scenario, allowed data class and
  review/rollback rule in admin docs.

### 5.4 Knowledge

Status: `native-with-configuration` for instructions/methodics/templates,
`native-partial` for document pipelines, `blocked-by-test-data` for customer
documents/OCR.

Docs-backed finding:

- Knowledge can store PDFs, spreadsheets, code and text-based documents;
- it supports retrieval/RAG and full-context modes;
- it can be attached to model presets or referenced in chat;
- retrieval access control is expected to check whether the user can read a
  file/collection.

Runtime status:

- Knowledge UI and file ingestion were not tested in this run.

Gap:

- Knowledge is not a production document pipeline;
- extraction quality for PDF/DOCX/XLSX/OCR must be proven on samples;
- large/complex Excel and scans need parser/OCR/tool decisions.

Recommendation:

- use Knowledge for approved instructions, methods, examples and stable
  templates;
- keep customer documents out of tests until explicit approval and samples
  exist;
- classify documents before promising any OCR/XLSX behavior.

### 5.5 Model Catalog / Curated Models

Status: `native-with-configuration`, `needs-customer-decision`,
`needs-runtime-proof`.

Docs-backed finding:

- Workspace Models can expose curated presets and restrict them by users/groups;
- models can be hidden/cloned/exported/imported and described;
- this supports a provider/model catalog without showing a raw provider-model
  list to every user.

Runtime status:

- unauthenticated `/api/models` is blocked;
- exact admin model list and group access were not inspected.

Gap:

- provider/data policy and exact model IDs are not approved in this audit;
- raw provider model hiding and curated model exposure need Admin UI proof;
- pricing/model IDs drift and must be rechecked before production enablement.

Recommendation:

- continue ADR-0006 as catalog governance;
- expose curated scenario models, not raw provider sprawl;
- do not introduce LiteLLM/model gateway unless hard budgets/routing are
  explicitly required.

### 5.6 Analytics / Usage / Cost Visibility

Status: `native-partial`, `needs-runtime-proof`, `needs-customer-decision` for
hard billing.

Docs-backed finding:

- OpenWebUI Analytics is admin-only and covers message volume, token usage,
  model performance, user activity, time periods and group filtering.
- It is derived from message history and is suitable as first candidate for
  basic visibility.

Runtime status:

- analytics tab/API were not accessible without admin login.

Gap:

- native analytics is not hard billing;
- no proof yet for deployed `0.9.6` user/group/model breakdown;
- STT/Web Search/provider dashboard costs may need manual reconciliation.

Recommendation:

- use native analytics first after admin proof;
- maintain a simple price catalog;
- keep LiteLLM/gateway as ADR-0008 future/custom slice only if customer needs
  guaranteed budgets, virtual keys, rate limits or routing.

### 5.7 Files / Documents

Status: `native-partial`, `blocked-by-test-data`, `needs-custom-integration`
for complex/OCR/XLSX paths.

Docs-backed finding:

- OpenWebUI supports chat file upload, RAG/full context and Workspace Knowledge;
- extraction engines include paths such as Tika, Docling, Mistral OCR or custom
  loaders in current docs;
- RAG quality depends on extraction, chunking and retrieval settings.

Runtime status:

- no customer files were used;
- no file upload proof was executed.

Gap:

- simple file analysis may be native;
- scanned PDFs, table-heavy documents, broker reports and XLSX formulas need
  test data and extraction/parser decisions;
- without customer samples, no quality claim is valid.

Recommendation:

- allow only synthetic/safe files for operator smoke;
- collect the test data package before implementation planning;
- keep production OCR/layout and complex Excel parser as separate slices.

### 5.8 Web Search Permissions And Providers

Status: provider baseline `native-ready`; rollout `needs-customer-decision` and
`needs-runtime-proof`.

Repo proof:

- Brave `brave_llm_context` native smoke passed on 2026-06-23 and is the
  current direct-context baseline.
- Yandex Search API is a working RU direct API path by owner/operator
  confirmation; full evidence remains pending.
- Private SearXNG native provider smoke passed in snippet/bypass mode and is a
  comparison path, not primary.

Runtime status in this audit:

- no Web Search live rollout/smoke was run;
- no provider config was changed.

Gap:

- group permission allow/deny proof is still pending;
- source cards, logs/retention, browser-key exposure and cost visibility remain
  rollout gates;
- vectorized `web-search-*` retrieval is a known deferred issue;
- full page loading is not proven.

Recommendation:

- keep native OpenWebUI Web Search first;
- run Brave/Yandex/private SearXNG comparison only with safe queries;
- do not launch all-user rollout until group scope, forbidden queries,
  logging/retention and cost visibility are approved.

### 5.9 STT Native vs Stage 2 STT Sidecar

Status: Stage 2 STT sidecar `current-stage closed`; native STT
`native-partial` and not a replacement for media attachment transcription.

Docs/runtime proof:

- OpenWebUI supports local/browser/remote STT providers for voice input;
- deployed static loader contains `stage2_media_transcription_action`;
- deployed STT normalization config is publicly served;
- 2026-06-19 reports close the current Stage 2 media attachment STT MVP.

Gap:

- native microphone/Web API dictation is a separate path and has a known mobile
  issue;
- native STT does not own the PRD-1 media attachment workflow: browser
  normalization, sidecar job routes, Lemonfox adapter, retention and usage
  metadata.

Recommendation:

- do not reopen STT architecture;
- keep Stage 2 media attachment sidecar path;
- treat native microphone/mobile issue as separate hardening.

### 5.10 Chat Deletion / Retention / Audit

Status: `needs-runtime-proof`, `needs-customer-decision`.

Docs-backed finding:

- research indicates chat deletion is permissioned in OpenWebUI docs;
- no-delete, retention, backup, audit and immutable archive are separate
  decisions.

Runtime status:

- no non-admin UI/API delete test was possible.

Gap:

- additive permissions may accidentally re-enable delete;
- UI-only check is insufficient;
- backup is not retention and not audit.

Recommendation:

- test native no-delete first with non-admin user;
- check UI and API delete behavior;
- keep ADR-0003 proposed until customer retention policy and runtime proof
  exist.

### 5.11 Manager Visibility

Status: `native-partial`, `needs-customer-decision`, `needs-runtime-proof`;
possible `needs-custom-integration`.

Docs-backed finding:

- native groups/sharing can support shared work resources;
- docs do not prove "manager sees all subordinate work chats" natively.

Runtime status:

- no manager/employee group test was possible.

Gap:

- group membership is not the same as supervisory access;
- blanket admin access is not acceptable manager visibility;
- work chats and personal/draft chats must be separated by policy.

Recommendation:

- use explicit work-scenario visibility model as target;
- prove what native sharing can and cannot do;
- fall back to export/reporting/policy-only before building custom supervisory
  UI.

### 5.12 Admin/User Instructions

Status: `native-ready` for skeleton documentation, `needs-runtime-proof` for
exact screenshots/settings.

What can be prepared now:

- admin checklist for groups, workspace models, prompts, knowledge, analytics,
  Web Search and no-delete proof;
- user instructions for approved scenarios and forbidden data examples;
- prompt/knowledge ownership rules;
- Web Search safe-use instructions.

What should wait:

- exact customer policy text;
- screenshots from Admin UI;
- final provider/model/data-class matrix.

## 6. PRD/Stage 2 Compliance Matrix

| Требование Stage 2 | Источник | Native OpenWebUI capability | Runtime status | Gap | Нужно ли согласование заказчика | Рекомендация |
| --- | --- | --- | --- | --- | --- | --- |
| Рабочие сценарии | PRD-1, WORKSPACES_AND_RBAC | Workspace Models + Prompts + Knowledge + Groups | version proven; Admin UI proof pending | no single business workspace entity | частично: owners/groups | собирать сценарий конфигурацией |
| Groups/RBAC | PRD-1, capability research | Groups, roles, permissions, resource access | Admin proof pending | additive permissions, no deny | да, group matrix | минимальные defaults + explicit grants |
| Workspace models | PRD-1, provider catalog | Model presets with prompts/knowledge/access | `/api/models` protected; admin proof pending | exact model IDs/data policy | да | curated models only |
| Shared prompts/templates | PRD-1 | Workspace Prompts, slash commands, variables, history, sharing | UI proof pending | owner/change process | частично | native prompts + publication rules |
| Knowledge/instructions | PRD-1 | Workspace Knowledge, RAG/full context, model binding | UI/file proof pending | not document pipeline | для customer docs да | use for instructions/templates first |
| Provider/model catalog | PRD-1, ADR-0006 | Workspace Models and access control | proof pending | provider/data policy, exact IDs | да | ADR-0006 + Admin UI proof |
| Basic analytics/cost visibility | PRD-1, ADR-0008 | Admin Analytics | proof pending | no hard budgets | да, granularity/budget | prove native first; no gateway now |
| Documents/simple file analysis | PRD-1, docs blueprint | Chat files, Knowledge/RAG, extraction settings | no file proof | extraction quality unknown | customer samples | native pilot on safe samples |
| OCR/layout PDF | PRD-1, ADR-0005 | extraction engines may help | not tested | needs OCR/VL OCR choice | да | blocked by test data |
| XLSX/complex Excel | PRD-1 | possible upload/extraction | not tested | formulas/parser accuracy | да | parser/tool future slice if needed |
| Web Search provider baseline | Web Search reports | Native Web Search providers | Brave/Yandex/SearXNG baseline exists | rollout gates pending | да | comparison + policy gates |
| Web Search group permissions | PRD-1, acceptance | Feature permissions / model capabilities / per-chat toggle | not tested | group allow/deny proof | да | admin/test-user proof |
| STT media attachment transcription | STT closure report | OpenWebUI UX + Action + sidecar integration | public static asset confirmed; MVP closed | production hardening | retention/limits yes | keep sidecar path |
| Native microphone STT | OpenWebUI docs, mobile audit | Local/browser/remote STT | not retested | mobile Web Speech issue | no for audit | separate hardening |
| Chat deletion restriction | PRD-1, ADR-0003 | likely native permission | not tested | UI/API proof needed | да | test native no-delete first |
| Retention/audit | PRD-1, ADR-0003 | backup/admin surfaces partly relevant | not tested | no immutable archive | да | policy/ADR before implementation |
| Manager visibility | PRD-1, ADR-0002 | groups/sharing partly relevant | not tested | no proven supervisory model | да | explicit work-scenario policy |
| Admin/user instructions | PRD-1 | docs/training/config | can draft now | exact settings need proof | partly | prepare skeletons now |

## 7. What Can Move Without Customer Approval

- Keep documentation and operator checklists current.
- Prepare admin runtime proof checklist.
- Prepare scenario skeletons with placeholder groups and synthetic examples.
- Prepare prompt/knowledge/model catalog templates without enabling providers.
- Prepare safe Web Search comparison matrix and forbidden-query examples.
- Prepare user/admin instruction skeletons.
- Run read-only public health/version/static checks.

## 8. What Can Be Prepared As Skeleton / Documentation

- Provider/model catalog table for ADR-0006.
- Native analytics proof worksheet for ADR-0008.
- Manager visibility matrix for ADR-0002.
- No-delete / retention / audit proof plan for ADR-0003.
- Workspace scenario template:
  `scenario -> owner -> group -> curated model -> prompts -> knowledge -> rules -> acceptance`.
- Web Search safe-use and rollout-gate checklist.
- Documents/OCR test-data intake form.

## 9. What Must Not Be Implemented Without Customer Approval

- broad Web Search rollout;
- enabling new production providers;
- sending customer documents to external providers;
- manager visibility beyond explicit work-scenario policy;
- no-delete/retention policy changes in production;
- hard billing/gateway/LiteLLM;
- deep OpenWebUI fork;
- production OCR/layout pipeline;
- data masking/tokenization subsystem;
- full AD/SCIM lifecycle.

## 10. Items Requiring Runtime Proof Only

- exact group permission behavior on deployed `0.9.6`;
- model visibility by group;
- Workspace Prompts sharing/version behavior;
- Knowledge access and retrieval checks;
- Analytics tab breakdown by user/model/group;
- non-admin chat delete UI/API behavior;
- Web Search feature permission/per-chat toggle/model capability behavior;
- file upload behavior on safe synthetic PDF/DOCX/XLSX;
- browser secret exposure check for Web Search provider config;
- admin/user visibility surfaces for shared chats.

## 11. Items Requiring ADR / Owner Decision

- ADR-0001 Data Policy by Provider Class.
- ADR-0002 Manager Visibility Policy.
- ADR-0003 Chat Deletion, Retention and Audit.
- ADR-0005 OCR / VL OCR Pilot Scope.
- ADR-0006 Provider Model Catalog.
- ADR-0007 Web Search Provider rollout governance.
- ADR-0008 Native Analytics vs Hard Billing.

No ADR was finalized in this audit.

## 12. Implementation Candidates

Configuration-first candidates:

1. Minimal workspace scenario package:
   - one group;
   - one curated Workspace Model;
   - one shared prompt;
   - one knowledge collection with synthetic/instructional content;
   - one ordinary-user visibility proof.
2. Native analytics proof:
   - two test users;
   - two models;
   - one group filter;
   - compare with provider dashboard where available.
3. Web Search rollout proof:
   - safe query matrix;
   - admin/pilot/ordinary user permissions;
   - source/cost/log checks.

Custom/integration candidates only after proof:

- custom supervisory export/reporting if native sharing is insufficient;
- server-side delete guard if native no-delete fails and customer approves;
- document parser/OCR pipeline after customer samples;
- gateway only if ADR-0008 concludes native analytics is insufficient.

## 13. Risks

- Treating docs-backed OpenWebUI capabilities as deployed proof.
- Additive permissions granting access through unexpected group/default path.
- Confusing shared work resources with manager access to private chats.
- Promising document/OCR quality without customer samples.
- Treating native analytics as hard billing.
- Treating SearXNG as complete privacy or primary search provider.
- Reopening STT architecture despite current-stage closure.
- Letting frontend/UI own provider keys, data policy, retention or usage
  accounting.

## 14. Recommended Next Slices

1. Admin/test-user native capability proof on deployed `0.9.6`.
   - No new production features.
   - Use test users/groups.
   - Capture exact setting names and screenshots without secrets.
2. Configuration-first workspace scenario pilot.
   - One safe synthetic scenario.
   - Curated model + prompt + knowledge + group access.
3. Native analytics proof.
   - Decide whether ADR-0008 can stay native-first.
4. Web Search comparison/rollout gates if Web Search continues.
   - Brave/Yandex/private SearXNG candidate-set comparison.
   - Permission/logging/retention/cost proof.
5. Customer decision package.
   - Data policy, provider/model catalog, manager visibility, retention,
     documents/OCR sample requirements.

## 15. Operator Runtime Checklist

Use only approved test users/groups and safe synthetic data.

1. Confirm deployed version:
   - `/api/version`;
   - Admin UI version/build if visible.
2. Create or identify:
   - Admin;
   - Manager/РО;
   - Employee inside group;
   - Employee outside group.
3. Groups/RBAC:
   - set minimal default permissions;
   - create one permission group and one sharing/business group;
   - verify effective permissions are additive;
   - record exact setting names.
4. Workspace scenario:
   - create one Workspace Model over an existing safe base model;
   - attach one system prompt and one safe knowledge item;
   - restrict model to a group;
   - verify ordinary user sees only allowed model/scenario.
5. Prompts:
   - create one prompt with variables;
   - share with group;
   - verify slash command visibility and version/history behavior.
6. Knowledge:
   - upload a safe synthetic text/PDF file;
   - attach to model;
   - verify inside/outside group access and retrieval behavior.
7. Analytics:
   - generate small sample usage by two users/models;
   - verify user/model/group/time filters;
   - record whether export exists.
8. Web Search:
   - do not roll out broadly;
   - use safe query matrix only;
   - verify feature permission/model capability/per-chat toggle behavior;
   - check provider key not visible in browser config/network.
9. No-delete:
   - create a test chat as non-admin;
   - attempt UI delete;
   - attempt API delete if available;
   - verify admin override.
10. Manager visibility:
    - share one work chat/resource by explicit group policy;
    - verify manager visibility;
    - verify unrelated personal/draft chat is not visible.
11. Files:
    - use only synthetic safe PDF/DOCX/XLSX;
    - record extraction quality and visible limitations.
12. Save evidence:
    - screenshots without secrets/customer data;
    - setting names;
    - actor matrix;
    - exact blockers.

## 16. Final Verdict

`native_first_path_confirmed_with_admin_runtime_gaps`

The current OpenWebUI `0.9.6` deployment is reachable and healthy. Native
OpenWebUI capabilities are strong enough to carry the first Stage 2 governance
and scenario work through configuration and extension-first patterns. The
remaining blocker is not architecture discovery; it is controlled admin/test-user
runtime proof plus customer decisions on data policy, groups, manager
visibility, retention, provider/model catalog and rollout scope.
