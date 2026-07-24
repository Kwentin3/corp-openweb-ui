# Broker Reports — Economy structured-output capability matrix

Дата проверки: 2026-07-24.

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`.

## Главное

“Structured output supported” недостаточно. Qualification subject должен
включать четыре слоя:

`model × provider API × maintained adapter/projection × canonical validator`.

OpenAI имеет самый полный документированный strict subset. Gemini и
Anthropic поддерживают schema-constrained output, но текущие projections
изменяют исходную schema. DeepSeek JSON mode гарантирует только JSON и не
подходит неизменённому strict contract.

## Provider API subset

Обозначения: `Y` — документировано; `P` — частично/с оговорками; `N` —
не поддерживается или не документировано, поэтому нельзя требовать без
probe.

| Возможность | OpenAI Nano/4.1 Nano/4o Mini | Gemini 2.5/3.1/3.5 Flash-Lite | Claude Haiku 4.5 native | DeepSeek v4 JSON mode |
| --- | --- | --- | --- | --- |
| schema conformance, strict | Y | Y для supported subset | Y через `output_config.format` | N |
| valid JSON | Y | Y | Y при schema success | P; возможен empty output |
| root object | required | supported/preferred | supported | prompt-only |
| root `anyOf` | N | N/not documented | projection-dependent | N |
| `enum` | Y | Y | Y, casing caveat | prompt-only |
| nested `anyOf` | Y | N/not documented in current guide | P | N |
| `oneOf` | N/avoid | N/not documented | P/complexity-sensitive | N |
| nullable | Y как type union with `null` | Y (`null`) | Y | prompt-only |
| all properties `required` | required by strict subset | supported | supported | N |
| `additionalProperties:false` | required | supported | supported | N |
| arrays/items | Y | Y | Y | JSON only |
| `minItems` / `maxItems` | Y | Y | Y within grammar limits | N |
| `uniqueItems` | N/avoid | N/not documented | P; do not rely without probe | N |
| `const` | not safely documented as general keyword; probe | N/not documented | Y, exact casing not guaranteed | N |
| string pattern/format | Y subset | `format` subset | P | N |
| numeric min/max | Y | Y | P | N |
| definitions/recursive | Y | not selected for this contract | complexity-sensitive | N |
| tool/function alternative | Y strict functions | Y functions | Y strict tools | tools, but no proven strict input |
| refusal may violate schema | Y, explicit refusal path | safety/blocking path possible | Y, HTTP 200 and billed | possible |
| truncation may violate schema | Y/incomplete | Y at max output | Y at `max_tokens` | Y |
| output token cap | Y | Y | Y | Y |
| reasoning disable/minimize | model-dependent; Nano supports controls | thinking control | model controls | thinking/non-thinking modes |
| usage returned | Y | Y | Y | Y |
| schema rejection signal | API 4xx / invalid schema | API error for unsupported/large schema | 4xx grammar/schema error | n/a: schema not enforced |

## Candidate-specific reading

| Candidate | Provider mode | Contract suitability | Remaining proof |
| --- | --- | --- | --- |
| `gpt-5-nano-2025-08-07` | OpenAI strict response format/function | strongest cost/capability candidate | publish exact ID; four workload probes |
| `gpt-5.4-nano-2026-03-17` | same | suitable, pricier secondary | publish; probes |
| `gpt-4.1-nano-2025-04-14` | same, non-reasoning | strong literal/checksum candidate | explicit policy acceptance; publish; probes |
| `gpt-4o-mini-2024-07-18` | same | suitable fallback, output cost above Nano | policy acceptance; publish; probes |
| `models/gemini-2.5-flash-lite` | Gemini response schema | cheapest Gemini; likely clerical fit | publish; current projection and live probes |
| `models/gemini-3.1-flash-lite` | Gemini response schema | source route proven; financial canonical failed | minimal financial fixture and branch-shape diagnostic |
| `models/gemini-3.5-flash-lite` | Gemini response schema | source route proven | financial harness route missing |
| `claude-haiku-4-5-20251001` | native Anthropic structured output | provider feature exists | projection/schema rejection diagnosis |
| `deepseek-v4-flash` | JSON mode | not sufficient | only reconsider if strict tool route is officially proved |
| `deepseek-v4-pro` | JSON mode | not sufficient despite low price | same |

## Текущий adapter layer

### OpenAI

`Gate2OpenAIResponseFormatAdapter` передаёт strict response format через
existing OpenAI connection. Projection profile наиболее близок к canonical
schema. Риск остаётся на `const`/complex unions и exact contract size; это
проверяется schema-only dry build и provider probe.

### Gemini

`Gate2GeminiResponseFormatAdapter` использует Google OpenAI-compatible
connection. Текущая structural projection:

- сохраняет object/array shape;
- сохраняет `anyOf`/`oneOf` structure;
- удаляет `const`, descriptions, defaults и часть ограничений;
- сохраняет только выбранные enums;
- не заменяет canonical validation.

Поэтому финансовый reject Gemini 3.1
`financial_evidence_decision_unclassified_shape_invalid` — это
`model/API/projection/prompt` open question, а не доказанный
`MODEL_QUALITY_FAILURE`.

### Anthropic

Gate 2 не использует Anthropic OpenAI compatibility для strict output,
поскольку там `response_format` и strict tool flag игнорируются. Maintained
adapter вызывает native `/messages` и передаёт
`output_config.format.type=json_schema`.

`_project_anthropic_structural_schema` упрощает некоторые `anyOf` unions и
удаляет неподдерживаемые constraints. Полученный ранее
`gate2_model_schema_response_format_rejected` возник до canonical model
result. Класс пока `PROVIDER_SCHEMA_LIMITATION` или
`OPENWEBUI_ADAPTER_LIMITATION`; модель Haiku как таковая не проверена на
financial decision.

### DeepSeek

Текущий profile не имеет достаточного final response schema contract.
Официальный JSON mode требует упомянуть JSON в prompt, может вернуть пустой
ответ и не гарантирует conformance. Free JSON/repair запрещены, поэтому
DeepSeek не допускается к qualification по текущему contract.

## Canonical validator obligations

Независимо от provider success код повторно обязан проверить:

- exact root keys и schema version;
- одно из четырёх dispositions;
- Registry-owned type IDs;
- allowed source refs и role bindings;
- branch-specific required/forbidden fields;
- absence duplicates и invented values;
- literal sign, precision, currency and date;
- truncation/refusal/empty output как terminal failure;
- provider identity, exact model, usage и workload contract version.

Provider schema не является canonical authority. Projection разрешено только
сужать/перевыражать provider dialect; ей запрещено ослаблять canonical
validator или выполнять hidden repair.

## Фактический route evidence

| Exact model × route | Source | Domain | Financial evidence | Checksum |
| --- | --- | --- | --- | --- |
| `models/gemini-3.1-flash-lite` × Gemini maintained route | passed | route available, отдельный receipt отсутствует | provider call, canonical rejected | not run |
| `models/gemini-3.5-flash-lite` × Gemini maintained route | passed | route available, отдельный receipt отсутствует | `HARNESS_ROUTE_MISSING`, 0 calls | not run |
| `claude-haiku-4-5-20251001` × Anthropic native route | passed | route available, отдельный receipt отсутствует | schema rejected before usable result | not run |
| OpenAI Nano exact IDs × OpenAI route | 0 calls | 0 | 0 | 0 |
| Gemini 2.5 Flash-Lite × Gemini route | 0 calls | 0 | 0 | 0 |
| DeepSeek v4 × current route | 0 qualifying strict calls | 0 | 0 | 0 |

Source-only success сохраняется как workload-specific evidence, но не
порождает общий status модели.

## Provider limits, отказ и lifecycle

- OpenAI strict subset: root object, all fields required,
  `additionalProperties:false`; до 5,000 properties, nesting 10 и
  120,000 total schema string characters. Refusal/incomplete обрабатываются
  отдельно.
- Gemini: supported JSON Schema subset; слишком большая/глубокая schema
  может быть rejected. Syntax-valid JSON не снимает canonical semantic
  checks.
- Anthropic: native structured outputs доступны Haiku 4.5; refusal может
  вернуть HTTP 200 и нарушить schema, truncation возможен; grammar compile
  ограничена complexity/time.
- DeepSeek: JSON mode не является schema mode.

## Официальные источники

- OpenAI Structured Outputs:
  https://developers.openai.com/api/docs/guides/structured-outputs
- OpenAI model cards:
  https://developers.openai.com/api/docs/models
- Gemini structured output:
  https://ai.google.dev/gemini-api/docs/structured-output
- Gemini OpenAI compatibility:
  https://ai.google.dev/gemini-api/docs/openai
- Anthropic structured outputs:
  https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Anthropic OpenAI SDK compatibility:
  https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk
- DeepSeek JSON mode:
  https://api-docs.deepseek.com/guides/json_mode/

## Terminal assessment

- OpenAI strict API fit: `DOCUMENTED_NOT_LIVE_QUALIFIED`;
- Gemini 3.1 source: `ROUTE_PROVEN`;
- Gemini 3.1 financial: `CANONICAL_REJECT_UNCLASSIFIED_CAUSE`;
- Gemini 3.5 financial: `HARNESS_ROUTE_MISSING`;
- Haiku financial: `SCHEMA_ROUTE_REJECT_UNCLASSIFIED_CAUSE`;
- DeepSeek: `UNSUPPORTED_BY_CURRENT_STRICT_CONTRACT`;
- canonical validator weakening: `ZERO`.
