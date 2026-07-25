# Broker Reports — Economy model cost matrix

Дата цен и расчёта: 2026-07-24.

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`.

Все суммы — USD, standard synchronous API, без налогов и региональных
надбавок. Cost estimate не является qualification.

## Official rates

| Exact candidate | Input | Cached input | Output | Batch input/output | Minimum unit / free tier | Lifecycle |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `gpt-5-nano-2025-08-07` | 0.05 | 0.005 | 0.40 | 50% | per token; no API free tier | stable |
| `gpt-5.4-nano-2026-03-17` | 0.20 | 0.02 | 1.25 | 50% | per token; no API free tier | stable |
| `gpt-4.1-nano-2025-04-14` | 0.10 | 0.025 | 0.40 | 50% | per token; no API free tier | stable |
| `gpt-4o-mini-2024-07-18` | 0.15 | 0.075 | 0.60 | 50% | per token; no API free tier | stable |
| `models/gemini-2.5-flash-lite` | 0.10 | 0.01 | 0.40 | 0.05 / 0.20 | per token; free tier has data-use/privacy limitations | stable |
| `models/gemini-3.1-flash-lite` | 0.25 | 0.025 | 1.50 | 0.125 / 0.75 | per token | stable |
| `models/gemini-3.5-flash-lite` | 0.30 | 0.03 | 2.50 | 0.15 / 1.25 | per token | stable GA |
| `claude-haiku-4-5-20251001` | 1.00 | cache hit 0.10 | 5.00 | 50% | per token; cache writes separately billed | stable |
| `deepseek-v4-flash` | cache miss 0.14 | hit 0.0028 | 0.28 | not used | per token | stable |
| `deepseek-v4-pro` | cache miss 0.435 | hit 0.003625 | 0.87 | not used | per token | stable |
| baseline `gpt-5.6-sol` | 5.00 | 0.50 | 30.00 | 50% | per token | prohibited baseline |

Reasoning tokens, если provider их выделяет, оплачиваются как generated
output по provider rules и обязательно входят в post-call usage. В
planning table reasoning отключён/minimal и отдельный hidden allowance не
заложен.

## Измеренные профили

| Workload | Calls | Expected measured | Conservative planning | Hard token ceiling | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| source package | 1 | `5,058 / 700` | `6,400 / 1,024` | `12,000 / 4,096` | Gemini 3.1 passed source |
| domain package | 1 | `NOT_MEASURED` | `6,000 / 800` proxy | `12,000 / 4,096` | отдельного domain usage receipt нет |
| financial scope | 1 | average `1,219 / 182`; observed max output `506` | `1,800 / 506` | `3,072 / 640` | 39-scope baseline |
| full financial scope | 39 | `47,533 / 7,102` | `70,200 / 19,734` | 64-call safety cap | measured aggregate |
| checksum | 1 | `117,555 / 783` | `125,000 / 900` | `130,000 / 1,024` | measured prior checksum |

Порядок чисел: input/output tokens. Domain proxy — только planning value и
не называется real profile.

## Expected cost на measured profiles

Domain использует явно отмеченный planning proxy `6,000 / 800`.

| Candidate | Source | Domain proxy | Financial scope | Financial ×39 | Checksum | Sol saving on ×39 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-5-nano-2025-08-07` | 0.000533 | 0.000620 | 0.000134 | 0.005217 | 0.006191 | 98.84% |
| `gpt-4.1-nano-2025-04-14` | 0.000786 | 0.000920 | 0.000195 | 0.007594 | 0.012069 | 98.32% |
| `models/gemini-2.5-flash-lite` | 0.000786 | 0.000920 | 0.000195 | 0.007594 | 0.012069 | 98.32% |
| `deepseek-v4-flash` | 0.000904 | 0.001064 | 0.000222 | 0.008643 | 0.016677 | 98.08% |
| `gpt-4o-mini-2024-07-18` | 0.001179 | 0.001380 | 0.000292 | 0.011391 | 0.018103 | 97.47% |
| `gpt-5.4-nano-2026-03-17` | 0.001887 | 0.002200 | 0.000471 | 0.018384 | 0.024490 | 95.92% |
| `models/gemini-3.1-flash-lite` | 0.002315 | 0.002700 | 0.000578 | 0.022536 | 0.030563 | 95.00% |
| `models/gemini-3.5-flash-lite` | 0.003267 | 0.003800 | 0.000821 | 0.032015 | 0.037224 | 92.90% |
| `claude-haiku-4-5-20251001` | 0.008558 | 0.010000 | 0.002129 | 0.083043 | 0.121470 | 81.58% |
| baseline `gpt-5.6-sol` | 0.046290 | 0.054000 | 0.011557 | 0.450725 | 0.611265 | baseline |

DeepSeek показан как cost datum, но текущим strict contract отклонён.

## Expected / conservative / worst

Три уровня для основных кандидатов:

| Workload/model | Expected | Conservative | Worst allowed |
| --- | ---: | ---: | ---: |
| source / GPT-5 Nano | 0.000533 | 0.000730 | 0.002238 |
| source / Gemini 3.1 FL | 0.002315 | 0.003136 | 0.009144 |
| source / Gemini 3.5 FL | 0.003267 | 0.004480 | 0.013840 |
| financial ×39 / GPT-5 Nano | 0.005217 | 0.011404 | 0.015974 for 39 calls |
| financial ×39 / Gemini 3.1 FL | 0.022536 | 0.047151 | 0.067392 for 39 calls |
| financial ×39 / Gemini 3.5 FL | 0.032015 | 0.070395 | 0.098342 for 39 calls |
| checksum / GPT-5 Nano | 0.006191 | 0.006610 | 0.006910 |
| checksum / Gemini 2.5 FL | 0.012069 | 0.012860 | 0.013410 |
| checksum / Gemini 3.1 FL | 0.030563 | 0.032600 | 0.034036 |

Worst financial row использует 39 × hard per-call token cap, а не
64-call fail-safe. Full-scope safety guard отдельно сохраняет 64-call cap.

## Retry и fallback

Один same-model retry удваивает соответствующую operation cost. Один
economy fallback добавляет стоимость fallback на том же token profile:

`total = primary + fallback`, не `max(primary, fallback)`.

Примеры:

| План | Expected cost |
| --- | ---: |
| source GPT-5 Nano, 1 call | 0.000533 |
| source GPT-5 Nano + one retry | 0.001066 |
| source GPT-5 Nano + Gemini 3.1 fallback | 0.002847 |
| financial ×39 GPT-5 Nano, no fallback | 0.005217 |
| financial ×39 GPT-5 Nano + full Gemini 3.1 fallback | 0.027754 |
| checksum GPT-5 Nano | 0.006191 |
| checksum fallback | prohibited (`0` fallback calls) |

Default qualification и production target: one call, no hidden retry.
Fallback выполняется только после отдельной workload qualification и
явного budget reservation.

## Target operating budgets

Предлагаемые targets существенно ниже существующих hard ceilings:

| Workload | Target per operation/run | Hard safety ceiling |
| --- | ---: | ---: |
| `gate2_source` | 0.004 per package | 0.064960 per operation |
| `gate2_domain` | 0.004 per package, provisional до measurement | 0.064960 |
| `gate2_financial_evidence` | 0.001 per scope; 0.040 per measured 39 | 0.012544 per operation; 0.401408 full guard |
| `gate2_financial_checksum` | 0.040 per call | 0.135120 |

Target допускает обе опубликованные Flash-Lite модели на source/domain и
Gemini 3.5 Flash-Lite на measured full financial run. Haiku не проходит
target для source/domain/checksum, но может остаться optional qualified
fallback при отдельном product решении. Hard ceilings не являются SLO.

## Rate limits, quotas, regions

- OpenAI limits зависят от usage tier. Для GPT-5 Nano official Tier 1:
  500 RPM / 200k TPM; текущий account tier stage не читался и остаётся
  `NOT_MEASURED`.
- Gemini active limits зависят от project/tier и отображаются в AI Studio;
  capacity не гарантируется. Точный maintained project quota не читался.
- Anthropic limits organization/tier-specific; официальный Haiku Scale
  table показывает до 1,000 RPM, 2M input TPM, 400k output TPM, но stage
  organization limit `NOT_MEASURED`.
- DeepSeek публикует concurrency 2,500 для Flash и 500 для Pro; 429 остаётся
  terminal `QUOTA_OR_RATE_LIMIT`.
- Provider regional availability и возможная 10% regional uplift должны
  проверяться для billing account перед live qualification. Текущие
  connections являются first-party public endpoints; data residency не
  доказывалась.

## Ожидаемая цена полного документа

Единственный полный измеренный компонент — 39 financial scopes:

- baseline Sol: `$0.450725`;
- теоретический GPT-5 Nano: `$0.005217`;
- теоретический Gemini 2.5 Flash-Lite / GPT-4.1 Nano: `$0.007594`;
- опубликованный Gemini 3.1 Flash-Lite: `$0.022536`;
- опубликованный Gemini 3.5 Flash-Lite: `$0.032015`.

Полная document cost, включающая variable count source/domain packages,
`NOT_ESTABLISHED`: отдельный domain token profile и package count отсутствуют.
Её нельзя честно получить сложением одного proxy call.

## Источники

- OpenAI pricing/models:
  https://developers.openai.com/api/docs/pricing и
  https://developers.openai.com/api/docs/models/gpt-5-nano
- Gemini pricing/rate limits:
  https://ai.google.dev/gemini-api/docs/pricing и
  https://ai.google.dev/gemini-api/docs/rate-limits
- Anthropic pricing/rate limits:
  https://platform.claude.com/docs/en/about-claude/pricing и
  https://platform.claude.com/docs/en/api/rate-limits
- DeepSeek pricing/rate limits:
  https://api-docs.deepseek.com/quick_start/pricing/ и
  https://api-docs.deepseek.com/quick_start/rate_limit/

## Gaps

- domain expected profile: `NOT_MEASURED`;
- maintained account quotas/regions: `NOT_MEASURED`;
- actual retry rate and cache hit: `NOT_MEASURED`;
- successful economy full-scope run: `NOT_RUN`;
- achieved saving: `NOT_CLAIMED`.
