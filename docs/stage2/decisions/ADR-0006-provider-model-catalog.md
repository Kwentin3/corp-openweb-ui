# ADR-0006 Provider Model Catalog

Status: Proposed

## 1. Context

PRD-1 includes Claude API / Claude models, GPT-mini, DeepSeek, YandexGPT,
GigaChat and existing OpenAI/Gemini context. Stage 2 needs curated model access,
not a raw provider list.

## 2. Problem

Without a provider/model catalog, users get a chaotic model list and admins lose
control of cost, allowed data classes and provider status.

## 3. Decision needed

Approve a provider model catalog format and first model set before provider
setup.

## 4. Options

Option 1. Configure provider keys directly.

- Fast.
- High drift and governance risk.
- Not recommended.

Option 2. Curated model catalog.

- Defines exact model IDs, status, costs, data classes and fallback.
- Recommended.

Option 3. Gateway-first model routing.

- Useful for hard billing/routing.
- Optional/future unless ADR-0008 requires it.

## 5. Recommended option

Use Option 2 for Practical Stage 2.

Catalog fields must include:

- exact model IDs;
- provider status: production / pilot / research / rejected;
- data class allowed;
- cost unit;
- owner;
- fallback;
- Claude API vs Claude Code distinction;
- DeepSeek current model IDs and alias drift warning;
- YandexGPT/GigaChat research and selection.

## 6. Consequences

- Provider setup waits for ADR-0001 data policy.
- Pricing/model IDs must be rechecked before production enablement.
- Workspace models should expose curated choices, not all raw provider models.
- Gateway/hard routing remains separate unless approved.

## 7. Runtime proof needed

- Verify exact model IDs against provider account/API.
- Confirm model access by group/workspace.
- Confirm basic usage/cost visibility path.
- Record rejected/deferred models with reason.

## 8. Customer input needed

- Provider accounts.
- Approved provider list.
- Allowed data classes by provider.
- Required production vs pilot vs research providers.
- Budget/cost visibility expectations.

## 9. Acceptance signals

- Catalog approved.
- Every enabled model has exact ID, status, data class and fallback.
- Claude Code is not presented as chat provider.
- DeepSeek alias/model drift is documented.
- Russian provider selection path is documented.

## 10. Links

- [PROVIDERS_MODEL_CATALOG](../blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
- [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](../research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)
- [ADR-0001 Data Policy](ADR-0001-data-policy-by-provider-class.md)
