# OpenWebUI Capability Research

## 1. Question

Какие native capabilities deployed OpenWebUI реально дает для Stage 2: workspaces, prompts, knowledge, groups/RBAC, STT, web-search, files, analytics, retention and admin surfaces?

## 2. Research status

Status: researched from repo evidence and official docs on 2026-06-18.

Result type: docs-backed findings + runtime blocker. Current deployed/admin UI behavior was not tested in this pass.

## 3. Local repo evidence

- Compose default image is pinned to `ghcr.io/open-webui/open-webui:v0.9.6` in `compose/openwebui.compose.yml`.
- PRD-0 docs deliberately excluded Stage 2 features: SSO/RBAC, web-search, RAG, gateway, hard budgets and custom frontend.
- No real `.env`, API keys or Admin UI state were read.

## 4. Official docs findings

- OpenWebUI RBAC has three layers: Roles, Permissions and Groups. Permissions are additive, and groups can grant feature access and shared access to resources.
- Permissions are feature/action flags, including examples such as chat deletion and web-search access. This makes no-delete and web-search enablement plausible as native checks, but deployed runtime must confirm the exact UI/permission keys in v0.9.6.
- Groups can be separated into permission-only groups and sharing groups. This is useful for Stage 2: do not mix technical capability groups with business/team sharing groups.
- OpenWebUI documents SSO/OIDC/LDAP/SCIM, but PRD-1 practical scope does not require full identity lifecycle.
- STT supports local Whisper, browser Web API and remote/cloud providers. Backend STT supports OpenAI-compatible mode, Deepgram, Azure and Mistral. Native STT is suitable for voice input and simple transcription checks, but not enough by itself for the PRD-1 Lemonfox + browser-ffmpeg workflow without a proxy/adapter decision.
- Web-search is a native feature with provider-specific engines, including Brave and Yandex Web Search env variables.
- Analytics is admin-only and covers message volume, tokens, models, user activity and group filtering according to current docs. It is a good first candidate for basic cost visibility, not a proven hard budget mechanism.
- RAG/file features exist, but OCR/layout-aware PDF and broker-report extraction quality still require test documents.
- Filter functions can be used for PII scrubbing, logging, cost tracking and rate limiting patterns. This is an extension surface, not a free replacement for a designed security/billing subsystem.

## 5. Gaps / blockers

- Deployed v0.9.6 may not match current OpenWebUI docs. Need read-only Admin UI check or controlled staging update research before implementation.
- Native manager visibility into subordinate work chats is not proven by RBAC docs. Groups/sharing are not the same as supervisory access to private conversations.
- Native no-delete policy is plausible because chat deletion is permissioned, but must be tested with non-admin users.
- Provider secrets, real model IDs and real OpenWebUI admin settings were intentionally not inspected.

## 6. Decision impact

- Start Stage 2 native-first for groups, permissions, shared prompts/knowledge, web-search and analytics.
- Keep STT proxy/server-side adapter as a real architecture decision because API keys, file limits, diarization and ffmpeg preprocessing must be controlled outside the browser.
- Treat manager visibility and no-delete as runtime proof items before promising them to the customer as finished native features.
- Do not fork OpenWebUI until a specific requirement fails native configuration and cannot be solved by extension/proxy boundaries.

## 7. Recommended next step

Run a read-only deployed Admin UI capability audit with a test user matrix:

- admin role;
- normal user;
- group with web-search allowed;
- group with chat delete disabled;
- sharing group for work scenario.

Record exact screenshots/settings names in a follow-up report before implementation planning.

## 8. Sources

- https://docs.openwebui.com/features/authentication-access/rbac/
- https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- https://docs.openwebui.com/features/authentication-access/rbac/groups/
- https://docs.openwebui.com/features/authentication-access/
- https://docs.openwebui.com/features/chat-conversations/chat-features/chatshare/
- https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/stt-config/
- https://docs.openwebui.com/reference/env-configuration/
- https://docs.openwebui.com/features/administration/analytics/
- https://docs.openwebui.com/features/chat-conversations/web-search/providers/brave/
- https://docs.openwebui.com/features/chat-conversations/rag/
- https://docs.openwebui.com/features/extensibility/plugin/functions/filter/

## 9. Status

Research complete for documentation-level planning. Runtime proof still required.
