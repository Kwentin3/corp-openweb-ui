# Providers Yandex GigaChat DeepSeek Claude Research

## 1. Question

Which provider/model catalog should Stage 2 expose, and how should Claude API, OpenAI GPT-mini,
DeepSeek, YandexGPT and GigaChat be classified?

## 2. Research status

Status: researched from official provider docs on 2026-06-18.

Result type: model catalog input. No API keys or live calls were used.

## 3. Key findings

### OpenAI GPT-mini

- `GPT-mini` must not remain a vague model name in implementation docs.
- Current OpenAI docs list `gpt-5.4-mini` as a current mini model for lower-latency/lower-cost work,
  with text+image input and text output.
- OpenAI docs also list `gpt-5-mini`. If the customer says "GPT-mini", implementation must choose an
  exact model ID and price tier.
- Existing repo docs already mention `gpt-5.4-mini`; keep it as the default candidate unless account
  availability or budget says otherwise.

### Claude API

- Claude API models are available through Anthropic API surfaces and supported platforms.
- Anthropic documents an OpenAI SDK compatibility layer for testing/evaluation.
- Claude Code is not the same thing as Claude API chat model access. It is a developer/agent tool
  and should not be listed as a normal chat provider for employees.

### DeepSeek

- DeepSeek API is compatible with OpenAI and Anthropic API formats.
- Current docs list `deepseek-v4-flash` and `deepseek-v4-pro`.
- `deepseek-chat` and `deepseek-reasoner` are marked for deprecation on 2026-07-24 and should not be
  introduced as fresh Stage 2 model IDs.
- DeepSeek V4 pricing is very low in official docs, but procurement, jurisdiction and privacy policy
  still need customer approval.

### YandexGPT / Yandex Cloud AI Studio

- AI Studio exposes YandexGPT models and other models through Text Generation APIs and
  OpenAI-compatible APIs.
- Current YandexGPT model URIs include `gpt://<folder_ID>/yandexgpt-5.1`,
  `gpt://<folder_ID>/yandexgpt-5-pro`, and `gpt://<folder_ID>/yandexgpt-5-lite`.
- Yandex docs recommend explicit URIs rather than relying on legacy aliases.
- Yandex notes common-instance model requests may be logged anonymized/masked and recommends
  disabling data logging for sensitive information.

### GigaChat

- GigaChat API has current generation models `GigaChat-2`, `GigaChat-2-Pro`, `GigaChat-2-Max` plus
  embeddings.
- GigaChat API authentication uses OAuth token flow and scopes for personal, B2B and corporate
  access.
- Official docs state first-generation `GigaChat`, `GigaChat-Pro`, `GigaChat-Max` route to
  second-generation analogs; implementation should use explicit current IDs where possible.
- Pricing docs for model pages list 65/500/650 RUB per 1M tokens for Lite/Pro/Max classes.

## 4. Recommended catalog classification

| Provider/model family | Stage 2 classification | Notes |
| --------------------- | ---------------------- | ----- |
| OpenAI `gpt-5.4-mini` | Production candidate | Good default for low-cost general tasks if account access is available. |
| Claude API models | Production candidate for complex documents/broker scenario | Do not confuse with Claude Code. Need exact model and cost approval. |
| DeepSeek V4 Flash/Pro | Alternative/research candidate | Cheap and compatible, but policy/procurement/jurisdiction review needed. |
| YandexGPT 5.1/5 Lite | Russian provider candidate | Good candidate when Russian provider/data policy is preferred. |
| GigaChat 2 Lite/Pro/Max | Russian provider candidate | Strong Russian-local option; integration/auth path differs from OpenAI-style providers. |
| Claude Code | Rejected as employee chat provider | May be separate dev-agent tooling, not PRD-1 chat catalog. |

## 5. Open questions

- Exact customer-approved provider list.
- Which foreign providers may process broker/financial data.
- Which Russian provider is preferred commercially: YandexGPT or GigaChat.
- Exact model IDs available in customer accounts.
- Whether OpenWebUI can connect each provider directly or through a gateway/adapter.

## 6. Recommendation

Prepare a provider catalog ADR with three levels:

- Production: OpenAI mini + Claude API if approved.
- Research/controlled: DeepSeek, YandexGPT, GigaChat.
- Not a chat provider: Claude Code.

Do not configure new providers until keys, data policy and exact model IDs are approved.

## 7. Sources

- https://developers.openai.com/api/docs/models
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://developers.openai.com/api/docs/models/gpt-5-mini
- https://developers.openai.com/api/docs/pricing
- https://docs.anthropic.com/en/docs/about-claude/models/overview
- https://docs.anthropic.com/en/docs/about-claude/pricing
- https://docs.anthropic.com/en/api/openai-sdk
- https://docs.anthropic.com/en/api/rate-limits
- https://api-docs.deepseek.com/
- https://api-docs.deepseek.com/quick_start/pricing
- https://api-docs.deepseek.com/quick_start/rate_limit
- https://aistudio.yandex.ru/docs/en/ai-studio/concepts/generation/models.html
- https://aistudio.yandex.ru/docs/en/ai-studio/pricing.html
- https://developers.sber.ru/docs/ru/gigachat/models/main
- https://developers.sber.ru/docs/ru/gigachat/models/gigachat-2-lite
- https://developers.sber.ru/docs/ru/gigachat/models/gigachat-2-max
- https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api
- https://developers.sber.ru/docs/ru/gigachat/api/tariffs

## 8. Status

Research complete. Provider catalog ADR required before runtime setup.
