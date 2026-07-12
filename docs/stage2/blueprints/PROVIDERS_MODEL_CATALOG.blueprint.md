# Providers Model Catalog Blueprint

## 1. Purpose

Создать curated provider/model catalog for Stage 2 scenarios.

## 2. PRD-1 requirements covered

- Production / required providers: Claude API / Claude models, GPT-mini, DeepSeek.
- Research providers: YandexGPT, GigaChat; choose one Russian provider after research.
- Claude Code is not a chat provider.

## 3. Current known context

PRD-0 used OpenAI primary and Gemini secondary context. PRD-1 expands provider research but requires
safe data policy and cost visibility.

## 4. Target user workflow

User selects a workspace, not a raw provider list. Workspace uses approved model(s) with clear role:
primary, fallback, cheap, strong, Russian provider, restricted.

## 5. Native OpenWebUI first path

- Workspace Models.
- Model access control by groups.
- Admin UI provider configuration.
- Model catalog in docs.

## 6. Integration / custom implementation path

- Adapter for non-compatible providers.
- Gateway only after hard billing/routing decision.
- Separate dev-agent scenario if Claude Code is ever needed.

## 7. Data and security notes

Provider choice depends on data sensitivity. Foreign models are restricted for
personal/financial/accounting data. Russian providers may be wider but still governed.

## 8. Dependencies

- Security data policy.
- Usage analytics/cost visibility.
- Provider access from operator/customer.

## 9. Risks and constraints

- Price/model IDs change.
- API compatibility uncertain.
- Claude Code confusion.
- Quota/billing/region blockers.

## 10. Open questions

- Which GPT-mini exact model is intended?
- Which DeepSeek model is allowed?
- YandexGPT or GigaChat for Russian provider?
- Which providers can process sensitive data?

## 11. Research links

- [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](../research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)
- [USAGE_ANALYTICS_BILLING_RESEARCH](../research/USAGE_ANALYTICS_BILLING_RESEARCH.md)

## 12. Acceptance signals

- Catalog marks each provider: production, pilot, research, rejected or deferred.
- Claude API is separate from Claude Code.
- Model access aligns with groups and data policy.

## 13. Implementation readiness

The broad catalog still needs scenario-specific research and operator/data-policy
approval. For bounded Gate 2 source-fact extraction, the current approved budget
frontier profiles are:

- OpenAI `gpt-5.6-luna` through the OpenWebUI-administered OpenAI connection;
- Google `models/gemini-3.1-flash-lite` through the accepted OpenWebUI
  compatibility transport;
- Anthropic `claude-haiku-4-5-20251001` through native Messages API with
  `output_config.format`.

All provider credentials are resolved from OpenWebUI Admin Connections; no
Function-level duplicate keys are part of the architecture. Gemini raw-native
REST is deferred while the compatibility route preserves strict schema
transport, canonical validation, provenance and no-fallback invariants.
Selection is explicit and is not based on table size. Automatic failover and
cost-based routing remain outside this catalog slice.
