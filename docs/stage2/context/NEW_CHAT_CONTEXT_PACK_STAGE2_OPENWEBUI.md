# Stage 2 / OpenWebUI New Chat Context Pack

Date: 2026-06-24

Scope: restart-safe handoff for `Kwentin3/corp-openweb-ui` Stage 2 / PRD-1.
This pack is based on the current working tree, Stage 2 docs and reports. It
does not include live smoke results from this run, production code changes,
runtime changes, real `.env` values, provider keys, admin credentials, private
URLs, tokens or customer data.

## 1. One-Screen Summary

- The project adapts OpenWebUI from a small corporate chat into a controlled
  corporate AI workspace.
- PRD-0 is accepted and closed; PRD-1 / Stage 2 is the current planning and
  proof domain.
- Stage 2 is not "connect more models"; it is scenarios, groups, documents,
  STT, Web Search, provider policy, cost visibility, audit and safe integration.
- STT MVP is implemented, proven for the current stage and ready for broader
  testing/hardening.
- Do not restart transcription architecture discovery unless the owner changes
  the product goal.
- Web Search provider connectivity baseline is closed for the current stage.
- Web Search user rollout is still pending.
- Brave `brave_llm_context` is the current native direct-context baseline.
- Yandex Search API is the working RU direct API path by owner/operator
  confirmation; full evidence remains pending.
- Private SearXNG works as a native private meta-search comparison path in
  snippet/bypass mode.
- Private SearXNG is not primary; treat it as a comparison track.
- The known vectorized `web-search-*` retrieval issue remains deferred.
- The next Web Search task, if Web Search continues now, is three-path
  comparison and rollout gates.
- If Web Search pauses, choose the next epic from PRD-1 roadmap/backlog rather
  than inventing a new track.
- Strong next candidates are data policy/provider catalog, RBAC/workspaces,
  native analytics/cost visibility, and documents/OCR/customer samples.
- Keep native OpenWebUI first and extension-first.
- Use Functions, Actions, Tools and OpenAPI Tool Servers before a sidecar.
- Use a private sidecar only for backend/domain boundaries that cannot live
  natively.
- Use a deep fork only after proof, owner approval and ADR.
- Provider keys stay server-side only.
- Runtime evidence beats assumptions.

## 2. Project Purpose

Stage 2 / PRD-1 exists to turn the accepted PRD-0 OpenWebUI deployment into a
managed corporate AI environment. The product goal is controlled day-to-day
work, not a generic AI platform.

The core value is operational control:

- groups, access and curated scenarios;
- shared prompts/templates and workspace-style models;
- controlled document, audio/video and web-search workflows;
- provider/model catalog with data policy;
- usage/cost visibility;
- audit, retention and safe deployment practices.

PRD-0 proved the base chat. Stage 2 adds business workflows and governance:
transcription, broker reports / 3-NDFL, Web Search, documents/OCR/Excel,
provider policy, RBAC, manager visibility and cost visibility.

Stage 2 stays bounded. LiteLLM/gateway, full AD/SCIM lifecycle, full data
masking/tokenization, hard billing, production document pipeline and deep
OpenWebUI fork are separate optional/future slices unless the owner explicitly
promotes them.

## 3. Current Architecture Principles

- Native OpenWebUI first.
- Extension-first for OpenWebUI-facing work.
- Prefer native configuration, Functions, Actions, Tools and OpenAPI Tool
  Servers before a sidecar.
- Use a thin static loader only when native UX is insufficient.
- Use a private sidecar only for backend/domain boundaries that cannot live
  safely in OpenWebUI-native mechanisms.
- Use a deep fork only after proof, owner approval and ADR.
- Provider keys and internal credentials stay server-side.
- Browser code may prepare data and display policy decisions, but must not own
  policy, provider secrets, retention or cost decisions.
- Keep UX explicit. Avoid hidden magic for risky workflows.
- Policy, cost, privacy, permissions and logging gates come before rollout.
- Runtime evidence is stronger than research notes or assumptions.
- External provider responses are not product contracts; normalize them through
  internal contracts where custom behavior exists.
- Do not turn Stage 2 into a parallel identity system.
- Do not treat a pilot or provider baseline as production acceptance.

## 4. Feature Status Overview

| Feature / domain | Status | Proof level | Current role | Remaining gates |
| --- | --- | --- | --- | --- |
| PRD-0 / corporate chat base | closed | accepted repo docs | base OpenWebUI deployment | Stage 2 starts from it |
| Stage 2 docs domain | closed for setup | docs and indexes present | source map and planning domain | keep updated when new epics land |
| STT | current-stage closed | runtime, Playwright and closure reports | implemented MVP path | hardening, ADR review, production policy |
| Web Search | provider baseline closed | Brave/Yandex/SearXNG reports | next candidate workflow | rollout gates and comparison |
| Brave | works | runtime baseline report | current direct-context baseline | EN/RU matrix, permissions, cost, rollout |
| Yandex | partial proof | owner/operator confirmation report | RU direct API path | source cards, logs, browser exposure check, cost mode, metadata review |
| SearXNG | works in snippet/bypass mode | runtime smoke report | private comparison path | quality, upstream behavior, full page loading if needed, image pinning |
| Usage/cost visibility | not closed | research/backlog only | governance gate | native analytics runtime proof or accepted gap |
| Groups/RBAC/workspaces/shared prompts | not closed | research/backlog only | Stage 2 core | runtime proof and owner policy |
| Documents/OCR/Excel | not closed | PRD/research only | practical Stage 2 pilot | customer samples, candidate selection, OCR proof |
| Broker reports / 3-NDFL | not closed | PRD/research only | priority business scenario | anonymized examples, output acceptance, document pipeline decisions |
| Provider/model catalog | not closed | ADR/backlog ready | provider governance | data policy and exact model/provider decisions |
| Data policy by provider class | not closed | ADR order/backlog | dependency for providers | owner approval and allowed/prohibited examples |
| Manager visibility/no-delete/retention | not closed | research/backlog | governance feature set | owner policy and runtime proof |

Use `unknown / needs roadmap audit` for any feature not covered by these docs.

## 5. STT Closeout Summary

Implemented path:

```text
OpenWebUI attachment/action
-> static loader
-> browser ffmpeg.wasm normalization
-> internal Stage 2 STT sidecar/job route
-> Lemonfox adapter
-> transcript returned into OpenWebUI UX
```

What is proven:

- private `stage2-stt` sidecar/job routes and internal auth boundary;
- explicit OpenWebUI `Transcribe` action/static-loader path;
- browser ffmpeg.wasm normalization for generated proof media;
- safe fail behavior for unsupported/decode-failed/no-audio cases;
- provider keys and sidecar token kept out of browser;
- transcript return to OpenWebUI UX;
- current-stage acceptance for MVP.

Current limitations:

- mobile browser and low-memory behavior need more proof;
- large/customer media still need acceptance samples;
- cancel behavior during preprocessing/upload/provider work needs hardening;
- final duration policy and provider-side cancel support remain decision items;
- storage/retention for prepared audio and transcripts remains policy work;
- native mobile microphone dictation issue is separate hardening, not evidence
  against the `stage2-stt` path.

Do not restart:

- the decision that provider calls must be server-side;
- the attachment/action/static-loader MVP pattern;
- browser ffmpeg.wasm normalization for tested MVP cases;
- the rule against a separate user-facing transcription portal;
- the rule against provider keys in browser code.

Future STT work should be explicit testing/hardening or owner-approved product
extension, not architecture rediscovery.

## 6. Web Search Closeout Summary

Current verdict:

- Provider connectivity baseline is closed for current stage.
- User/production rollout is pending.
- Three native OpenWebUI provider paths now have baseline status.

Brave:

- `brave_llm_context` works.
- It is the current direct-context baseline.
- It uses web-loader and embedding/retrieval bypasses intentionally.
- Brave already returns LLM-oriented passages and source URLs.
- The vectorized `web-search-*` retrieval path can still return `0 sources`
  after successful search/embedding.
- Keep that issue deferred unless long pages, classic `brave`, SearXNG page
  loading or full RAG over fetched content becomes a real product requirement.

Yandex:

- Works by owner/operator confirmation.
- Treat it as the RU direct API path for controlled comparison planning.
- Full evidence remains pending: source cards, logs, browser exposure check,
  permissions, cost mode and metadata review.
- Do not treat YandexGPT, GigaChat or Yandex generative answer modes as part of
  this Web Search baseline.

SearXNG:

- Works as a private native meta-search path in snippet/bypass mode.
- Runtime smoke returned successful source items across safe RU/EN queries.
- It remains comparison infrastructure, not the primary provider.
- It narrows the instance boundary; upstream engines may still receive
  minimized queries.
- The meta-search path does not own a global web index.
- Full page loading and vectorized retrieval are not proven.
- Public instances are not acceptable for corporate acceptance.

Pending gates:

- Brave/Yandex/private SearXNG three-path comparison;
- pilot group and ordinary-user allow/deny checks;
- forbidden query policy;
- source cards and answer groundedness matrix;
- logging/retention review;
- browser exposure checks for provider keys;
- native/provider cost visibility;
- Yandex metadata/cost review;
- SearXNG engine tuning only if comparison shows value.

## 7. Known Issues And Traps

- Brave API worked, but the extra vectorized retrieval path returned zero
  sources in diagnostics.
- Direct-context Brave fixed the current baseline by bypassing web loader and
  embedding/retrieval.
- SearXNG direct JSON initially returned `429` because the private Docker caller
  was not passlisted by the limiter.
- SearXNG needed `link_token=false` and private Docker/loopback passlist.
- OpenWebUI needed no-proxy entries for `searxng`, `searxng:8080` and
  `searxng-valkey`.
- DuckDuckGo CAPTCHA and Brave-through-SearXNG rate-limit noise were observed.
- Yandex proof is operator-confirmed; full evidence is still pending.
- Private SearXNG must not be presented as complete privacy.
- Public SearXNG instances are not acceptable for corporate acceptance.
- Do not reuse STT sidecar logic for Web Search unless a native OpenWebUI gap is
  proven and the owner approves the backend boundary.
- Do not call Web Search rollout complete just because provider connectivity is
  proven.
- Do not let browser code own provider keys, data policy, retention or cost
  decisions.

## 8. Runtime / Deployment Notes

This run did not change runtime and did not run live smoke.

Current repo/deploy shape from compose and reports:

- OpenWebUI base image default: `ghcr.io/open-webui/open-webui:v0.9.6`.
- Repo OpenWebUI image default:
  `corp-openwebui/openwebui:v0.9.6-native-web-stt-v1`.
- Main compose file: `compose/openwebui.compose.yml`.
- Optional private SearXNG overlay: `compose/searxng.private.compose.yml`.
- SearXNG runtime config: `deploy/searxng/settings.yml` and
  `deploy/searxng/limiter.toml`.
- Private SearXNG image default: `docker.io/searxng/searxng:latest`.
- Valkey image default: `docker.io/valkey/valkey:8-alpine`.
- Production-like SearXNG rollout should pin a reviewed image tag.
- SearXNG overlay exposes no public host port by default.
- OpenWebUI internal SearXNG URL shape:
  `http://searxng:8080/search?q=<query>`.
- After SearXNG smoke, provider config was restored to `yandex` and SearXNG
  services were stopped.
- Provider keys must live in server-local env/Admin UI/approved secret storage.
- Do not commit real `.env`, provider keys, admin credentials, private URLs,
  bearer tokens or customer data.

## 9. Security / Privacy / Cost Policy Summary

- External provider calls are data egress.
- Provider/data policy by provider class is a dependency for rollout.
- Use safe, minimized, non-customer queries for Web Search proof.
- Define forbidden query classes before users get broad access.
- Do not put provider keys in browser, docs, reports, logs or screenshots.
- Inspect browser-visible config/network output before rollout.
- Logs must not retain raw sensitive queries/results by default.
- Source attribution must distinguish candidate sources, loaded/extracted
  evidence and evidence actually used by the final answer.
- Cost visibility can start with native/provider analytics if that is enough.
- Hard billing/gateway is not first stage unless the owner requires enforceable
  budgets across providers/features.
- Group permissions must be proven: admin, pilot user and ordinary user cases.
- Private SearXNG still depends on upstream engines and their behavior.

## 10. Current Roadmap Recommendation

Roadmap evidence says Phase 2 ADR/policy work is still the organizing layer.
Data policy, provider catalog, Web Search provider decision, manager visibility,
OCR scope and analytics decision are all in the intended decision sequence.

Candidate next epics:

| Candidate | Why now | Prerequisites | Expected output | Risks | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Web Search three-path comparison | Provider baseline is ready; this is the direct continuation if Web Search remains active | safe query matrix, owner acceptance of Yandex/SearXNG scope | comparison report for Brave/Yandex/private SearXNG | conflating comparison with rollout; weak Yandex proof | recommended if continuing Web Search |
| Web Search rollout gates | Needed before real users get broad Web Search | group scope, forbidden query policy, logs/retention, cost path | rollout gate report and owner decision list | premature rollout without policy | recommended after or alongside comparison |
| Data policy and provider/model catalog | Blocks provider setup, documents and cost governance | owner data classes and provider preference | ADR-0001/ADR-0006 review package | policy discussion can sprawl | recommended if stopping Web Search now |
| RBAC/workspaces/shared prompts proof | Core Stage 2 capability and native-first fit | test users/groups and scenario list | runtime proof and workspace setup plan | hidden OpenWebUI permission semantics | recommended after data policy or in parallel if runtime access exists |
| Native analytics/cost visibility | Required before cost-sensitive rollout | test users/models/providers | evidence whether native analytics is enough | hard billing scope creep | recommended before broad provider usage |
| Documents/OCR/Excel pilot | Practical Stage 2 target | customer samples and data policy | OCR/document pilot matrix | impossible to prove on imaginary docs | not recommended until samples arrive |
| Broker reports / 3-NDFL scenario | High business value | anonymized broker reports and good-output example | scenario workspace/prompt/acceptance pack | document parsing quality unknown | not recommended until samples arrive |

Agent recommendation:

- If Web Search continues now: run Brave/Yandex/private SearXNG comparison, then
  close rollout gates.
- If Web Search pauses: next best epic is data policy plus provider/model
  catalog, because it unlocks provider setup, Web Search rollout, documents and
  cost visibility.
- Owner must decide whether the next chat continues Web Search or switches to
  Stage 2 governance/core configuration.
- Owner must decide which groups get Web Search first, what queries are
  forbidden, whether Yandex metadata/cost mode is acceptable, and whether
  private SearXNG is worth ongoing ops burden.

## 11. Source Map

| Path | Why it matters | Status |
| --- | --- | --- |
| `README.md` | Top-level repo and Stage 2 navigation | current, dirty in working tree |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md` | PRD-1 source of truth | current |
| `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1_CUSTOMER_SUMMARY.md` | Customer-facing summary | current |
| `docs/stage2/README.md` | Stage 2 hub | current, dirty in working tree |
| `docs/stage2/CONTEXT_INDEX.md` | Domain navigation and status | current, dirty in working tree |
| `docs/stage2/ROADMAP.md` | Stage 2 phase and ADR order | current |
| `docs/stage2/ENGINEERING_BACKLOG.md` | Next work candidates and blockers | current, dirty in working tree |
| `docs/stage2/DOMAIN_MAP.md` | Domain ownership map | current |
| `docs/stage2/EXTENSION_FIRST_IMPLEMENTATION_PATTERN.md` | Extension-first rule | current |
| `docs/stage2/CONTRACT_BOUNDARIES.md` | Backend/domain boundary rules | current |
| `docs/stage2/IMPLEMENTATION_GATES.md` | Gate status and proof requirements | current |
| `docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md` | STT restart-safe handoff shape | current for STT |
| `docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md` | STT closure proof | current for STT MVP |
| `docs/reports/2026-06-19/OPENWEBUI_NEW_CHAT_CONTEXT_PACK.report.md` | Prior STT context-pack report | current for STT handoff pattern |
| `docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md` | Web Search operational source map | current, dirty in working tree |
| `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md` | Web Search provider baseline verdict | current |
| `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md` | Brave direct-context proof | current |
| `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md` | Yandex operator-confirmed proof | current, partial evidence |
| `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md` | Private SearXNG runtime proof | current |
| `docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_DOCS_REFINE_AFTER_BRAVE_SMOKE.report.md` | Brave-era docs refinement | useful history; superseded for final provider status by closeout |
| `docs/reports/2026-06-23/OPENWEBUI_STAGE2_WEB_SEARCH_ANAMNESIS_AUDIT.report.md` | Pre-closeout Web Search anamnesis | historical; do not use as final runtime status |
| `docs/reports/2026-06-23/OPENWEBUI_SEARXNG_ANAMNESIS_AUDIT.report.md` | Pre-runtime SearXNG audit | historical; later runtime smoke supersedes its pending smoke status |
| `docs/stage2/implementation/WEB_SEARCH_NATIVE_PILOT_PLAN.md` | Pilot plan and gate list | current, dirty in working tree |
| `docs/stage2/implementation/WEB_SEARCH_CANDIDATE_SET_COMPARISON_PLAN.md` | Three-path comparison method | current, dirty in working tree |
| `docs/stage2/implementation/SEARXNG_PRIVATE_INSTANCE_PLAN.md` | Private SearXNG ops model | current, dirty in working tree |
| `docs/stage2/decisions/ADR-0007-web-search-provider.md` | Web Search ADR | proposed/current, dirty in working tree |
| `docs/stage2/contracts/WEB_SEARCH_PRIVACY_BOUNDARY_CONTRACT.md` | Web Search data-egress rules | current, dirty in working tree |
| `docs/stage2/contracts/WEB_SEARCH_SOURCE_ATTRIBUTION_CONTRACT.md` | Source/evidence vocabulary | current, dirty in working tree |
| `docs/stage2/contracts/WEB_SEARCH_USAGE_EVENT_CONTRACT.md` | Usage-event contract draft | current |
| `docs/stage2/contracts/OPENWEBUI_WEB_SEARCH_INTEGRATION_BOUNDARY.md` | Native integration boundary | current, dirty in working tree |
| `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md` | Acceptance gates | current, dirty in working tree |
| `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md` | Test data requirements | current, dirty in working tree |
| `docs/infra/ENVIRONMENT_VARIABLES.md` | Non-secret env/config contract | current, dirty in working tree |
| `docs/infra/DOCKER_COMPOSE_PLAN.md` | Compose/runtime notes | current, dirty in working tree |
| `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md` | Provider research and pricing framing | current, dirty in working tree |

## 12. Copy-Paste Compact Context

```text
We are in Kwentin3/corp-openweb-ui.
Use the current workspace root supplied by the runner; do not hardcode a local
Windows path in the next chat.
Use current repo evidence; do not rely on memory alone.
Do not read or print real .env values, provider keys, admin credentials,
private URLs, tokens or customer data.
Do not run live smoke unless the owner explicitly asks.
Do not write production code for this handoff task.

Project:
PRD-0 corporate OpenWebUI chat is accepted/closed.
PRD-1 / Stage 2 turns OpenWebUI into a managed corporate AI workspace.
Stage 2 covers scenarios, groups, shared prompts, documents, STT, Web Search,
provider/model catalog, policy, audit and usage/cost visibility.
It is not just "connect more models".

Core rules:
Native OpenWebUI first.
Extension-first.
Try native config, Functions, Actions, Tools and OpenAPI Tool Servers first.
Use a thin static loader only when native UX is insufficient.
Use a private sidecar only for backend/domain boundaries that cannot live
natively.
Use a deep fork only after proof, owner approval and ADR.
Provider keys stay server-side only.
Browser code must not own policy, retention, provider keys or cost decisions.
Runtime evidence beats assumptions.

STT:
Stage 2 STT MVP is implemented/proven/current-stage closed.
Implemented path:
OpenWebUI attachment/action -> static loader -> browser ffmpeg.wasm
normalization -> internal stage2-stt sidecar/job route -> Lemonfox adapter ->
transcript returned into OpenWebUI UX.
Do not restart transcription architecture discovery.
Do not create a separate user-facing transcription portal.
Do not move provider keys into browser.
Remaining STT work is testing/hardening: mobile, low memory, large/customer
media, cancel behavior, duration policy, storage/retention and production
monitoring/cost events.
Native mobile microphone dictation issue is separate hardening, not evidence
against stage2-stt sidecar.

Web Search:
Stage 2 Web Search provider connectivity baseline is closed for current stage.
User rollout is pending.
Brave brave_llm_context works as native direct-context baseline.
Brave baseline intentionally bypasses web loader and embedding/retrieval.
Known issue: vectorized web-search-* retrieval can return 0 sources.
Keep that issue deferred unless long pages, classic brave, SearXNG page loading
or full RAG over fetched content is required.
Yandex Search API works as RU direct API path by owner/operator confirmation.
Yandex full evidence remains pending: source cards, logs, browser exposure
check, permissions, cost mode and metadata review.
Private SearXNG works as native private meta-search path in snippet/bypass mode.
SearXNG is comparison infrastructure, not primary.
Private SearXNG still sends minimized queries to upstream engines.
The meta-search path does not own a global web index.
Public SearXNG instances are not acceptable for corporate acceptance.

Web Search next bounded tasks:
1. Run Brave / Yandex / private SearXNG candidate-set comparison.
2. Close rollout gates: pilot group, allow/deny permissions, forbidden queries,
logs/retention, browser exposure checks and cost visibility.
3. Tune SearXNG only if comparison shows value.
4. Keep vectorized retrieval and long page loading as separate future issues.

If Web Search pauses:
Choose the next epic from PRD-1 roadmap/backlog.
Recommended next epic: data policy by provider class plus provider/model
catalog, because it unlocks provider setup, Web Search rollout, documents and
cost governance.
Other valid candidates: RBAC/workspaces/shared prompts runtime proof, native
analytics/cost visibility, documents/OCR/Excel pilot after customer samples,
broker reports/3-NDFL after anonymized examples.

Read first:
README.md
docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md
docs/stage2/README.md
docs/stage2/CONTEXT_INDEX.md
docs/stage2/ROADMAP.md
docs/stage2/ENGINEERING_BACKLOG.md
docs/stage2/CONTRACT_BOUNDARIES.md
docs/stage2/IMPLEMENTATION_GATES.md
docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STAGE2_OPENWEBUI.md
docs/stage2/context/NEW_CHAT_CONTEXT_PACK_STT_STAGE2.md
docs/stage2/WEB_SEARCH_CONTEXT_INDEX.md
docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_PROVIDER_BASELINE_CLOSEOUT.report.md
docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_BRAVE_RUNTIME_BASELINE.report.md
docs/reports/2026-06-23/OPENWEBUI_WEB_SEARCH_YANDEX_RUNTIME_BASELINE.report.md
docs/reports/2026-06-23/OPENWEBUI_SEARXNG_RUNTIME_SMOKE.report.md
docs/reports/2026-06-19/OPENWEBUI_STT_MVP_FEATURE_CLOSURE.report.md
```
