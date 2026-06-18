# Providers Yandex GigaChat DeepSeek Claude Research

## 1. Question

Which LLM providers and models should be production, fallback, pilot, research-only or rejected for Stage 2?

## 2. Why it matters for PRD-1

Provider catalog controls quality, cost, data policy and user choice.

## 3. Current assumptions

- Claude API / Claude models are required.
- GPT-mini is primary/fallback candidate.
- DeepSeek is mandatory alternative.
- YandexGPT and GigaChat are research candidates; choose one Russian provider.
- Claude Code is not a normal chat provider.

## 4. What to verify

- API compatibility.
- Auth and key handling.
- Model IDs.
- Pricing.
- Context limits.
- Russian business quality.
- Data policy fit.

## 5. Sources to check

- Official provider docs.
- Existing provider plans.
- OpenWebUI provider compatibility.
- Operator/customer access.

## 6. Test plan / proof plan

Use same smoke prompts: document summary, business letter, table reasoning, meeting notes, broker report draft.

## 7. Risks

- API incompatibility.
- Unconfirmed billing/quota/region.
- Sensitive data sent to wrong provider.
- Claude Code terminology confusion.

## 8. Decision options

- Production provider.
- Fallback provider.
- Pilot provider.
- Research-only.
- Rejected/deferred.

## 9. Recommended next step

Create provider comparison matrix after access confirmation.

## 10. Status

Planned, not verified.
