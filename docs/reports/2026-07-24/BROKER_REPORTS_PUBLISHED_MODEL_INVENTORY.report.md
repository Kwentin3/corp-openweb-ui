# Broker Reports — Published model inventory

Дата проверки: 2026-07-24.

Статус: `COMPLETED`.

## Результат

Повторный read-only запрос к stage OpenWebUI `0.9.6` вернул `41` опубликованную
запись. Все записи классифицированы. Maintained connections уже существуют
для OpenAI, Anthropic, DeepSeek и Google Gemini; новый provider stack для
shortlist не требуется.

После снятия publication blockers в aggregate inventory присутствуют три
запрошенных exact-кандидата:

- `models/gemini-2.5-flash-lite`;
- `gpt-5.4-nano-2026-03-17`;
- `claude-haiku-4-5-20251001`.

Опубликованы и другие недорогие модели, но у них есть отдельные blockers:
`deepseek-v4-pro` не даёт strict schema conformance, Gemma 4 доступна через
free-only boundary с неприемлемым privacy/paid-production профилем,
`models/gemini-2.5-flash` стоит как 3.5 Flash-Lite, а не как 2.5
Flash-Lite. `gpt-5.4-mini-2026-03-17` дешевле frontier, но не проходит
предлагаемый target output budget.

## Connection map

| `urlIdx` | Provider route | Endpoint class | Published models | Direct connection inventory |
| ---: | --- | --- | ---: | ---: |
| `0` | OpenAI | first-party OpenAI-compatible | 7 | 109 |
| `1` | Anthropic | maintained external bearer, native adapter для Gate 2 | 4 | 9 |
| `2` | DeepSeek | OpenAI-compatible | 1 | 2 |
| `3` | Google Gemini | Gemini OpenAI-compatible endpoint | 24 | 57 |
| n/a | OpenWebUI local | Pipe, Workspace Model, Arena | 5 | n/a |

Connection inventory шире опубликованного `/api/models`. Поэтому
`MODEL_NOT_PUBLISHED` не означает отсутствие модели у provider connection.

## Полный `/api/models` inventory

`Chat boundary` означает пригодность записи для обычного server-side text
chat. Media generators, realtime, deep-research и Arena не являются
кандидатами bounded Gate 2.

| Exact опубликованный ID | Display name | Route | Identity | Chat boundary | Класс / lifecycle | Gate 2 verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `arena-model` | Arena Model | local | virtual router | нет exact target | Arena | rejected |
| `broker_reports_gate1_pipe` | НДФЛ. Брокерские отчёты / Gate 1 | local Pipe | virtual | Pipe | active | Gate 1, вне scope |
| `broker_reports_gate2_domain_source_fact_pipe` | Broker Reports Gate 2 Domain Source Facts | local Pipe | virtual | Pipe | active | route, не provider model |
| `broker_reports_gate2_source_fact_pipe` | Broker Reports Gate 2 Source Facts | local Pipe | virtual | Pipe | active | route, не provider model |
| `claude-haiku-4-5-20251001` | Claude Haiku 4.5 | Anthropic `1` | dated snapshot | да | stable economy | published; qualification replayed |
| `claude-opus-5` | Claude Opus 5 | Anthropic `1` | named model | да | expensive frontier | prohibited; no calls |
| `claude-sonnet-4-6` | Claude Sonnet 4.6 | Anthropic `1` | direct exact/alias family | да | expensive stable | rejected by cost |
| `claude-sonnet-5` | Claude Sonnet 5 | Anthropic `1` | direct exact/alias family | да | frontier stable | rejected by cost |
| `deepseek-v4-pro` | deepseek-v4-pro | DeepSeek `2` | direct exact | да | cheap stable | research-only: no strict schema |
| `gpt-5.4-nano-2026-03-17` | same | OpenAI `0` | dated snapshot | да | stable economy | published; qualification replayed |
| `gpt-5.4-mini-2026-03-17` | same | OpenAI `0` | dated snapshot | да | mid-cost stable | rejected target budget |
| `gpt-5.6-luna` | same | OpenAI `0` | named model | да | cost-sensitive, not Nano | rejected target budget |
| `gpt-5.6-sol` | same | OpenAI `0` | named model | да | frontier | prohibited |
| `gpt-5.6-terra` | same | OpenAI `0` | named model | да | frontier/mid-tier | prohibited |
| `gpt-realtime-2.1` | same | OpenAI `0` | exact realtime | не обычный chat target | realtime | rejected |
| `gpt-realtime-2.1-mini` | same | OpenAI `0` | exact realtime | не обычный chat target | realtime | rejected |
| `models/antigravity-preview-05-2026` | Antigravity Agent Preview | Google `3` | preview | agent preview | preview | rejected |
| `models/aqa` | Attributed Question Answering | Google `3` | specialized | specialized | active specialized | rejected |
| `models/deep-research-max-preview-04-2026` | Deep Research Max Preview | Google `3` | preview | specialized | preview | rejected |
| `models/deep-research-preview-04-2026` | Deep Research Preview | Google `3` | preview | specialized | preview | rejected |
| `models/deep-research-pro-preview-12-2025` | Deep Research Pro Preview | Google `3` | preview | specialized | preview | rejected |
| `models/gemini-2.5-flash` | Gemini 2.5 Flash | Google `3` | stable exact family | да | stable Flash | secondary only, not Lite price |
| `models/gemini-2.5-flash-lite` | Gemini 2.5 Flash-Lite | Google `3` | stable exact family | да | stable economy | published; provider route returns upstream 404 |
| `models/gemini-3.1-flash-lite` | Gemini 3.1 Flash Lite | Google `3` | stable exact family | да | stable economy | shortlist |
| `models/gemini-3.5-flash` | Gemini 3.5 Flash | Google `3` | stable exact family | да | stable Flash | rejected target budget |
| `models/gemini-3.5-flash-lite` | Gemini 3.5 Flash Lite | Google `3` | stable exact family | да | stable economy | shortlist |
| `models/gemini-3.6-flash` | Gemini 3.6 Flash | Google `3` | stable exact family | да | stable Flash | rejected target budget pending separate acceptance |
| `models/gemini-3-flash-preview` | Gemini 3 Flash Preview | Google `3` | preview | да | preview | rejected lifecycle |
| `models/gemma-4-26b-a4b-it` | Gemma 4 26B A4B IT | Google `3` | stable open model | да | free-only API tier | rejected privacy/paid boundary |
| `models/gemma-4-31b-it` | Gemma 4 31B IT | Google `3` | stable open model | да | free-only API tier | rejected privacy/paid boundary |
| `models/imagen-4.0-fast-generate-001` | Imagen 4 Fast | Google `3` | image generator | нет | stable media | rejected |
| `models/imagen-4.0-generate-001` | Imagen 4 | Google `3` | image generator | нет | stable media | rejected |
| `models/imagen-4.0-ultra-generate-001` | Imagen 4 Ultra | Google `3` | image generator | нет | stable media | rejected |
| `models/lyria-3-clip-preview` | Lyria 3 Clip Preview | Google `3` | music generator | нет | preview | rejected |
| `models/lyria-3-pro-preview` | Lyria 3 Pro Preview | Google `3` | music generator | нет | preview | rejected |
| `models/lyria-realtime-exp` | Lyria Realtime Experimental | Google `3` | music realtime | нет | experimental | rejected |
| `models/nano-banana-pro-preview` | Nano Banana Pro | Google `3` | image generator | нет | preview | rejected; “Nano” не price class Gate 2 |
| `models/veo-3.1-fast-generate-preview` | Veo 3.1 fast | Google `3` | video generator | нет | preview | rejected |
| `models/veo-3.1-generate-preview` | Veo 3.1 | Google `3` | video generator | нет | preview | rejected |
| `models/veo-3.1-lite-generate-preview` | Veo 3.1 lite | Google `3` | video generator | нет | preview | rejected; “lite” не text model |
| `test` | тест | local Workspace Model | alias → `broker_reports_gate1_pipe` | Pipe | active alias | hidden expensive Gate 1 target |

## Text-candidate capability inventory

Значения относятся к official provider API, а не означают прохождение
текущего adapter/canonical route.

| Exact candidate | Modalities | Context / max output | Structured / tools | Reasoning | Standard USD/MTok input/output | Lifecycle |
| --- | --- | --- | --- | --- | ---: | --- |
| `gpt-5-nano-2025-08-07` | text+image in, text out | 400k / 128k | strict Structured Outputs; functions | configurable | `0.05 / 0.40` | stable snapshot, unpublished |
| `gpt-5.4-nano-2026-03-17` | text+image in, text out | 400k / 128k | strict Structured Outputs; functions | none..xhigh | `0.20 / 1.25` | stable snapshot, published |
| `gpt-4.1-nano-2025-04-14` | text+image in, text out | 1,047,576 / 32,768 | strict Structured Outputs; functions | non-reasoning | `0.10 / 0.40` | stable snapshot, unpublished |
| `gpt-4o-mini-2024-07-18` | text+image in, text out | 128k / 16,384 | strict Structured Outputs; functions | non-reasoning | `0.15 / 0.60` | stable snapshot, unpublished |
| `models/gemini-2.5-flash-lite` | text/image/video/audio/PDF in | ~1M / 65,536 | structured output; functions | controllable | `0.10 / 0.40` | stable, published; maintained route unavailable |
| `models/gemini-3.1-flash-lite` | text/image/video/audio/PDF in | 1,048,576 / 65,536 | structured output; functions | thinking control | `0.25 / 1.50` | stable, published |
| `models/gemini-3.5-flash-lite` | text/image/video/audio/PDF in | 1,048,576 / 65,536 | structured output; functions | thinking control | `0.30 / 2.50` | stable GA, published |
| `claude-haiku-4-5-20251001` | text+image in, text out | 200k / 64k | native strict output/tools | controllable | `1.00 / 5.00` | stable dated, published |
| `deepseek-v4-flash` | text in/out | 1M / 384k | JSON mode, tools; no schema guarantee | thinking/non-thinking | `0.14 miss / 0.28` | stable, unpublished |
| `deepseek-v4-pro` | text in/out | 1M / 384k | JSON mode, tools; no schema guarantee | thinking/non-thinking | `0.435 miss / 0.87` | stable, published |

## Alias `test`

`test` разрешён до local base model `broker_reports_gate1_pipe`, а не до
economy provider ID. Live Gate 1 valves внутри Pipe выбирают:

- Gemini: `models/gemini-3.5-flash`;
- OpenAI: `gpt-5.4-mini-2026-03-17`;
- table intake: `models/gemini-3.5-flash`.

Следовательно, display name `тест` скрывает дорогой dual-VLM Gate 1 contour.
Это допустимо для Gate 1 quality boundary, но alias запрещено принимать за
economy Gate 2 model.

## Cheap exact IDs в существующих connections, но не в `/api/models`

После повторной инвентаризации всё ещё не опубликованы:

1. `gpt-5-nano-2025-08-07`;
2. `gpt-4.1-nano-2025-04-14`;
3. `gpt-4o-mini-2024-07-18`.

`deepseek-v4-flash` уже присутствует в connection inventory, но публиковать
его для qualification следует только как `research-only`: текущий contract
требует schema conformance, которого официальный JSON mode не гарантирует.

Не публиковать для qualification `latest`, preview, experimental или
undated moving aliases. Gemini 2.0 Flash-Lite уже shut down; его наличие в
connection inventory было бы stale metadata, а не доступностью.

## Источники

- live stage: read-only `/api/models`, `/openai/models`, model/config
  endpoints, проверено 2026-07-24;
- OpenAI model pages: https://developers.openai.com/api/docs/models;
- Gemini models/changelog: https://ai.google.dev/gemini-api/docs/models и
  https://ai.google.dev/gemini-api/docs/changelog;
- Anthropic models: https://platform.claude.com/docs/en/about-claude/models/overview;
- DeepSeek models/pricing: https://api-docs.deepseek.com/quick_start/pricing/.

## Acceptance

- `OPENWEBUI_MODELS`: `FULLY_INVENTORIED`;
- `OPENWEBUI_MODELS_TOTAL`: `41`;
- requested exact candidates published: `3/3`;
- `EXACT_PROVIDER_IDENTITIES`: `RESOLVED_WHERE_POSSIBLE`;
- `ALIASES`: `CLASSIFIED`;
- `HIDDEN_EXPENSIVE_TARGETS`: `IDENTIFIED`;
- stage mutations: `ZERO`;
- credentials/provider raw output in Git: `ZERO`.
