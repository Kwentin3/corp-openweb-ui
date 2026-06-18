# OpenWebUI Stage 2 Research Actualization Report

Date: 2026-06-18
Repo: `corp-openweb ui`
Scope: PRD-1 / Stage 2 documentation research and planning update

## 1. Executive summary

Выполнен полный research-pass по Stage 2 / PRD-1 и актуализирован документационный контур `docs/stage2`. Предыдущие research-файлы были в состоянии proof-plan: что нужно проверить, какие источники открыть, какие вопросы закрыть. Сейчас они переведены в состояние findings: что найдено в первичных источниках, какие выводы можно использовать для архитектурных решений, где остаются blockers и какие ADR/проверки нужны до implementation.

Код, runtime, compose/env/scripts, реальные provider keys и `.env` не менялись и не читались. Это осознанно: задача была research/docs, а не настройка Stage 2 на сервере.

Главный вывод: Stage 2 можно вести native-first на OpenWebUI, но нельзя считать все требования уже закрытыми нативно. Есть три класса работ:

1. Native-first configuration after runtime proof: RBAC/groups, shared prompts/knowledge, web-search, documents/RAG, analytics.
2. ADR-required implementation boundaries: STT proxy, web-search provider choice, provider catalog, OCR pilot, manager visibility/no-delete, analytics vs hard billing.
3. Future/deferred slices: full data masking/tokenization, production OCR/layout pipeline, hard billing/gateway unless customer explicitly requires it.

## 2. Где теперь что лежит

### 2.1. Входная навигация

- Root entrypoint: `README.md`.
- Stage 2 entrypoint: `docs/stage2/README.md`.
- Быстрый индекс по задачам: `docs/stage2/CONTEXT_INDEX.md`.
- Доменные границы: `docs/stage2/DOMAIN_MAP.md`.
- Planning backlog после research: `docs/stage2/ENGINEERING_BACKLOG.md`.
- Roadmap: `docs/stage2/ROADMAP.md`.
- Acceptance matrix: `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`.

### 2.2. Research-файлы

- `docs/stage2/research/OPENWEBUI_CAPABILITY_RESEARCH.md` - native capabilities OpenWebUI, RBAC, STT, web-search, analytics, RAG/docs, runtime blockers.
- `docs/stage2/research/RBAC_MANAGER_VISIBILITY_RESEARCH.md` - groups/sharing vs manager visibility, privacy boundary, test matrix.
- `docs/stage2/research/CHAT_DELETION_RETENTION_RESEARCH.md` - native chat deletion permission, retention fallback, runtime proof.
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md` - STT architecture, native OpenWebUI STT, Lemonfox, server-side proxy.
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md` - Lemonfox endpoint, limits, formats, diarization, EU endpoint, pricing, risks.
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md` - ffmpeg.wasm integration boundary, browser constraints, sidecar/module recommendation.
- `docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md` - OpenWebUI web-search, Brave, Yandex Search API, provider decision options.
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md` - OpenWebUI extraction engines, Tika/Docling/Mistral OCR, broker/OCR pilot boundary.
- `docs/stage2/research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md` - provider catalog input: OpenAI mini, Claude API, DeepSeek, YandexGPT, GigaChat.
- `docs/stage2/research/USAGE_ANALYTICS_BILLING_RESEARCH.md` - native analytics vs LiteLLM/gateway/hard budgets.
- `docs/stage2/research/DATA_MASKING_FUTURE_RESEARCH.md` - why masking/tokenization stays future slice and what real architecture would require.

### 2.3. Этот отчет

- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md`.

## 3. Что найдено

### 3.1. OpenWebUI native capabilities

Найдено:

- OpenWebUI официально описывает RBAC через Roles, Permissions и Groups.
- Permissions additive: группы добавляют права, а не создают deny-rules.
- Groups подходят для двух разных задач: permission groups и sharing groups.
- Chat sharing поддерживает access control для users/groups.
- Web-search является native feature с provider-specific engines.
- STT поддерживает local/browser/remote providers, включая OpenAI-compatible backend path.
- Analytics доступна админам и покрывает message volume, token usage, model/user/group breakdown.
- RAG/document extraction exists, включая external extraction engines.

Вывод:

- Native-first подход оправдан для конфигурационных частей Stage 2.
- Но текущие docs могут не совпадать с deployed `ghcr.io/open-webui/open-webui:v0.9.6`; нужен read-only Admin UI/staging proof.

Где лежит:

- `docs/stage2/research/OPENWEBUI_CAPABILITY_RESEARCH.md`.
- `docs/stage2/DOMAIN_MAP.md`.
- `docs/stage2/ENGINEERING_BACKLOG.md`.

### 3.2. RBAC, manager visibility, chat deletion

Найдено:

- Нативные groups/sharing дают управляемое совместное использование ресурсов.
- Это не доказывает автоматический доступ руководителя ко всем рабочим чатам подчиненных.
- Chat deletion appears permissioned in OpenWebUI docs, но нужно проверить deployed behavior.
- Additive permissions могут случайно вернуть delete permission через другую группу.

Вывод:

- Manager visibility нельзя обещать как готовую native-функцию без runtime test matrix и privacy decision.
- Предпочтительная трактовка: видимость только для явно рабочих shared scenarios/resources, а не скрытый просмотр всех личных чатов.
- No-delete нужно проверить UI и API путем test user proof.

Где лежит:

- `docs/stage2/research/RBAC_MANAGER_VISIBILITY_RESEARCH.md`.
- `docs/stage2/research/CHAT_DELETION_RETENTION_RESEARCH.md`.
- `docs/stage2/blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md`.
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`.

### 3.3. Transcription / STT / Lemonfox / ffmpeg browser workflow

Найдено:

- OpenWebUI has native STT, но PRD-1 scenario шире: audio/video transcription через existing browser ffmpeg workflow and Lemonfox priority provider.
- Lemonfox дает OpenAI-compatible transcription endpoint, upload limit 100 MB, URL limit 1 GB, formats including audio/video, Russian language, `srt/vtt/verbose_json`, diarization up to 4 speakers, word timestamps and EU endpoint with surcharge.
- Lemonfox-specific features могут не пройти через native OpenWebUI OpenAI-compatible STT path без adapter/proxy.
- ffmpeg.wasm работает в browser worker, имеет single-thread/multi-thread cores, multi-thread требует SharedArrayBuffer/security requirements, core assets need versioning/self-hosting decision.
- Existing ffmpeg workflow artifact is not in this repo, so integration boundary researched, but actual code not inspected.

Вывод:

- Для Practical Stage 2 нужен server-side STT proxy/adapter.
- Browser must never receive STT API key.
- Native STT можно протестировать как baseline, но acceptance PRD-1 лучше строить вокруг proxy boundary.

Где лежит:

- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`.
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`.
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`.
- `docs/stage2/blueprints/TRANSCRIPTION_STT.blueprint.md`.

### 3.4. Web-search providers

Найдено:

- OpenWebUI поддерживает native web-search providers and env/admin configuration.
- Brave has `brave` and `brave_llm_context`; LLM Context лучше подходит для AI grounding, потому что возвращает подготовленные passages and avoids extra scraping.
- Brave pricing currently: Search $5 / 1,000 requests, $5 monthly credits, 50 rps capacity.
- OpenWebUI docs include Yandex Web Search variables.
- Yandex Search API supports text/image/generative search, sync/deferred modes, quotas and different pricing. Generative response is much more expensive than simple text search.

Вывод:

- Best first pilot: Brave `brave_llm_context`, if customer approves foreign provider and cost.
- Russian-provider candidate: Yandex Search API, but it needs separate smoke/ADR and may require more integration/cost handling.
- Unlimited/agentic browsing should not be enabled without policy and limits.

Где лежит:

- `docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md`.
- Existing older research remains in `docs/infra/WEB_SEARCH_PROVIDER_RESEARCH.md`.
- `docs/stage2/blueprints/WEB_SEARCH.blueprint.md`.

### 3.5. Documents / OCR / Excel / broker reports

Найдено:

- OpenWebUI supports document extraction/RAG and Workspace Knowledge.
- Official docs describe Apache Tika, Docling, Azure, Mistral OCR and custom extractors.
- Docling is relevant for structured extraction from PDFs, Word documents, spreadsheets, HTML and images.
- Mistral OCR is relevant for scanned PDFs/images/handwriting.
- OpenWebUI docs recommend previewing extracted content; blank/missing sections mean extractor settings or engine must change.

Вывод:

- Stage 2 should split documents into: basic native document handling, OCR/layout pilot, future production pipeline.
- Broker/3-НДФЛ output must stay draft/manual-review; no tax/legal guarantee.
- Quality is blocked by real anonymized broker reports and example of good Claude result.

Где лежит:

- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`.
- `docs/stage2/blueprints/DOCUMENTS_OCR_EXCEL.blueprint.md`.
- `docs/stage2/blueprints/BROKER_REPORTS_3NDFL.blueprint.md`.
- `docs/stage2/acceptance/TEST_DATA_REQUIREMENTS.md`.

### 3.6. Provider catalog / models

Найдено:

- `GPT-mini` must become exact model ID before setup. Current OpenAI docs list mini candidates such as `gpt-5.4-mini` and `gpt-5-mini`; existing repo context points to `gpt-5.4-mini` as candidate.
- Claude API is a provider/model family; Claude Code is not employee chat provider.
- DeepSeek currently exposes `deepseek-v4-flash` and `deepseek-v4-pro`; old `deepseek-chat` / `deepseek-reasoner` are marked for deprecation on 2026-07-24.
- Yandex AI Studio exposes explicit YandexGPT URIs and OpenAI-compatible APIs; docs recommend explicit URIs.
- GigaChat current generation models are `GigaChat-2`, `GigaChat-2-Pro`, `GigaChat-2-Max`; auth/procurement path differs from simple OpenAI-style key.

Вывод:

- Нужно оформить Provider Catalog ADR with production/research/rejected labels.
- Production candidates: OpenAI mini and Claude API after account/data-policy approval.
- Research/controlled candidates: DeepSeek, YandexGPT, GigaChat.
- Claude Code should be rejected as normal chat provider and kept only as possible developer-tooling topic.

Где лежит:

- `docs/stage2/research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md`.
- `docs/stage2/blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md`.

### 3.7. Usage analytics / costs

Найдено:

- OpenWebUI Analytics is admin-only and gives message/token/model/user/group views according to current docs.
- This likely satisfies basic Stage 2 visibility if deployed version exposes it.
- Hard budgets, virtual keys, routing and guaranteed spend blocking are gateway-class requirements.
- LiteLLM Proxy supports virtual keys, spend tracking, budgets and rate limits, but adding it changes architecture and ops surface.

Вывод:

- Native analytics first.
- Hard billing/gateway remains optional/future ADR unless customer explicitly asks for enforceable budgets.

Где лежит:

- `docs/stage2/research/USAGE_ANALYTICS_BILLING_RESEARCH.md`.
- `docs/stage2/blueprints/USAGE_ANALYTICS_AND_COSTS.blueprint.md`.

### 3.8. Data masking / security policy

Найдено:

- OpenWebUI filter functions can support PII scrubbing/logging/rate/cost patterns.
- Microsoft Presidio provides detection and anonymization/de-anonymization components.
- LiteLLM has Presidio-based PII/PHI masking guardrail.
- None of that makes masking trivial: real solution needs entity policy, Russian/financial recognizers, mapping storage, reversibility, leak tests and placement decision.

Вывод:

- Do data policy now.
- Keep full masking/tokenization as future security slice.
- Do not promise automatic anonymization in customer-facing scope.

Где лежит:

- `docs/stage2/research/DATA_MASKING_FUTURE_RESEARCH.md`.
- `docs/stage2/blueprints/SECURITY_DATA_POLICY.blueprint.md`.

## 4. Что предложено

### 4.1. ADR / decision notes before implementation

1. STT proxy boundary.
2. Web-search provider selection.
3. Provider model catalog.
4. Manager visibility and no-delete policy.
5. Native analytics vs hard billing.
6. OCR pilot scope.
7. Data policy by provider class.

### 4.2. Runtime proof before implementation

1. OpenWebUI Admin UI capability audit for deployed/staging v0.9.6.
2. Non-admin delete permission test: UI and API if applicable.
3. Manager visibility test matrix with groups/shared chats.
4. Native analytics proof with two users/groups/models.
5. Web-search smoke for selected provider.
6. STT proxy smoke after provider key/test audio approval.

### 4.3. Customer inputs needed

1. Group/role matrix and manager visibility policy.
2. Allowed/prohibited data examples by provider class.
3. Provider accounts/keys/model availability.
4. Anonymized broker reports and expected good-result example.
5. Audio/video test files and practical file-size/duration limits.
6. Web-search smoke queries.

## 5. Files changed by this research pass

### Root and Stage 2 navigation

- `README.md`
- `docs/stage2/README.md`
- `docs/stage2/CONTEXT_INDEX.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/ENGINEERING_BACKLOG.md`
- `docs/stage2/ROADMAP.md`
- `docs/stage2/acceptance/ACCEPTANCE_MATRIX.md`

### Research findings

- `docs/stage2/research/OPENWEBUI_CAPABILITY_RESEARCH.md`
- `docs/stage2/research/RBAC_MANAGER_VISIBILITY_RESEARCH.md`
- `docs/stage2/research/CHAT_DELETION_RETENTION_RESEARCH.md`
- `docs/stage2/research/TRANSCRIPTION_STT_RESEARCH.md`
- `docs/stage2/research/LEMONFOX_STT_RESEARCH.md`
- `docs/stage2/research/FFMPEG_BROWSER_WORKFLOW_RESEARCH.md`
- `docs/stage2/research/WEB_SEARCH_PROVIDERS_RESEARCH.md`
- `docs/stage2/research/DOCUMENTS_OCR_EXCEL_RESEARCH.md`
- `docs/stage2/research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md`
- `docs/stage2/research/USAGE_ANALYTICS_BILLING_RESEARCH.md`
- `docs/stage2/research/DATA_MASKING_FUTURE_RESEARCH.md`

### Report

- `docs/reports/2026-06-18/OPENWEBUI_STAGE2_RESEARCH_ACTUALIZATION.report.md`

## 6. Non-goals and safety notes

- No runtime/provider setup was performed.
- No `.env` was read.
- No real API keys were used.
- No production/server changes were made.
- No OpenWebUI fork/custom frontend was introduced.
- No source-code implementation was started.

## 7. Primary sources used

OpenWebUI:

- https://docs.openwebui.com/features/authentication-access/rbac/
- https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- https://docs.openwebui.com/features/authentication-access/rbac/groups/
- https://docs.openwebui.com/features/chat-conversations/chat-features/chatshare/
- https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/stt-config/
- https://docs.openwebui.com/reference/env-configuration/
- https://docs.openwebui.com/features/administration/analytics/
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/brave/
- https://docs.openwebui.com/features/chat-conversations/rag/document-extraction/

STT / media:

- https://www.lemonfox.ai/apis/speech-to-text
- https://www.lemonfox.ai/
- https://ffmpegwasm.netlify.app/docs/overview/
- https://ffmpegwasm.netlify.app/docs/getting-started/usage/

Search:

- https://brave.com/search/api/
- https://api-dashboard.search.brave.com/documentation/pricing
- https://api-dashboard.search.brave.com/documentation/services/llm-context
- https://yandex.cloud/en/docs/search-api/concepts/
- https://yandex.cloud/en/docs/search-api/pricing
- https://yandex.cloud/en/docs/search-api/concepts/limits

Providers:

- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://developers.openai.com/api/docs/pricing
- https://docs.anthropic.com/en/docs/about-claude/models/overview
- https://docs.anthropic.com/en/api/openai-sdk
- https://api-docs.deepseek.com/
- https://api-docs.deepseek.com/quick_start/pricing
- https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models.html
- https://aistudio.yandex.ru/docs/en/ai-studio/pricing.html
- https://developers.sber.ru/docs/ru/gigachat/models/main
- https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api

Analytics / gateway / masking:

- https://docs.litellm.ai/docs/simple_proxy
- https://docs.litellm.ai/docs/proxy/virtual_keys
- https://docs.litellm.ai/docs/proxy/users
- https://microsoft.github.io/presidio/
- https://microsoft.github.io/presidio/anonymizer/
- https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2

## 8. Recommended next sequence

1. Review this report and Stage 2 README snapshot.
2. Write ADRs for STT proxy, web-search provider and provider catalog.
3. Get customer decisions for provider/data policy and manager visibility.
4. Run runtime proof matrix on deployed/staging OpenWebUI.
5. Collect customer test data.
6. Only then start implementation slices.