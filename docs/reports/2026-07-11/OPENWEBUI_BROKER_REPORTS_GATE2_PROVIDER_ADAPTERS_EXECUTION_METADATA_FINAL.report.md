# Broker Reports Gate 2: provider adapters и метаданные модели — финальный отчёт

Дата: 2026-07-11

Статус: `IMPLEMENTED_DEPLOYED_AND_LIVE_VERIFIED`

## Итог простыми словами

Pipeline больше не привязан к особенностям одного LLM-провайдера. Остальной
код передаёт одну и ту же задачу фабрике, фабрика выбирает профиль и адаптер, а
адаптер общается через штатный completion-маршрут OpenWebUI.

OpenAI и Gemini сейчас подтверждены живыми bounded-прогонами. Для Gemini в
production-профиль добавлена точная проверенная модель
`models/gemini-3.5-flash`. Claude намеренно не объявлен рабочим: текущее
OpenAI-compatible подключение Anthropic не гарантирует требуемый strict JSON
Schema. Система останавливает такой путь до provider call и не создаёт факты.

После каждого реального LLM-вызова теперь сохраняется, каким провайдером,
профилем, адаптером и моделью выполнен разбор, сколько он занял, какие usage
вернул провайдер и был ли response id. Это позволяет собирать статистику
качества, стоимости и стабильности по моделям.

## Что изменено

```text
Gate 2 Pipe
  -> Gate2StructuredModelClientFactory
     -> provider profile
     -> Gate2ProviderAdapterFactory
        -> OpenAI response-format adapter
        -> Gemini response-format adapter
     -> штатный OpenWebUI completion
     -> provider execution metadata
     -> private raw output
     -> deterministic validator
     -> safe validation + run aggregate
```

- Добавлен отдельный `gate2_provider_adapters.py`.
- Provider factory остаётся единственной production-точкой выбора маршрута.
- Pipes не знают о vendor payload, decoder или error taxonomy.
- Прямые HTTP/SDK-вызовы OpenAI, Gemini или Claude отсутствуют.
- Новых runtime-зависимостей нет.
- Ядро OpenWebUI не патчилось.
- Скрытого переключения на другого провайдера нет.
- Downgrade `json_schema -> json_object` отсутствует.
- Gemini получает provider-safe structural JSON Schema, а неизменённый
  canonical contract повторно и полностью проверяется детерминированным
  validator до сохранения факта.
- Provider call выполняется не более одного раза на attempt; повтор возможен
  только как явно учтённый bounded validation repair.
- Provider-reported model обязан совпасть с requested exact model/version alias;
  скрытая маршрутизация на другую модель завершается fail-closed.
- До private persistence действует лимит ответа по bytes/nodes/depth/string;
  oversized content заменяется компактным hash/length diagnostic.

## Поддерживаемые профили

| Профиль | Состояние strict Gate 2 | Адаптер / причина |
| --- | --- | --- |
| `openai_gpt` | `approved` | `openai_response_format` |
| `google_gemini` | `approved` для exact model id | `gemini_response_format` v1.5; live подтверждена `models/gemini-3.5-flash` |
| `anthropic_claude` | `unsupported` | текущему маршруту нужен нативный Claude Messages transport |
| `deepseek` | `unsupported` | strict final JSON Schema не доказан |
| `zai_glm` | `unsupported` | strict final JSON Schema не доказан |
| `alibaba_qwen` | `unsupported` | strict final JSON Schema не доказан |

Production allowlist намеренно узкий: OpenAI — только `gpt-5.6-sol`, Gemini —
только `models/gemini-3.5-flash`. `models/gemini-2.5-pro` исчез из live-каталога,
а `models/gemini-2.5-flash` на финальном полном schema contract упёрся в лимит
сложности Gemini. Неподтверждённая модель не наследует approval от провайдера.

## Почему Claude пока заблокирован

Live OpenWebUI 0.9.6 ведёт Anthropic connection через
`/chat/completions` и пересылает OpenAI-compatible payload. Это видно в
[dispatcher OpenWebUI](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/utils/chat.py#L274-L299)
и [OpenAI router](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/openai.py#L1190-L1205).

Anthropic документирует, что в OpenAI compatibility `response_format`
игнорируется, а strict tool schema не гарантируется:
[Anthropic OpenAI compatibility](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk).
Настоящий strict structured output у Claude использует нативный Messages API и
`output_config.format`:
[Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

Поэтому добавлять в текущий `/chat/completions` payload поле Claude
`output_config` было бы ложной поддержкой: endpoint всё равно останется
неправильным. Разрешённые будущие варианты — штатный Anthropic transport в
OpenWebUI или отдельно согласованный translating gateway. Прямой обход
OpenWebUI не использован.

## Контракт статистики модели

Добавлен `gate2_provider_execution_metadata_v1` со следующими полями:

- `provider_id`, `provider_profile_id`, profile revision;
- `adapter_id`, adapter version;
- requested и provider-reported resolved model id отдельно;
- structured-output и response-format mode;
- monotonic duration;
- input/output/total tokens, только если их сообщил провайдер;
- finish reason;
- provider/OpenWebUI response body id;
- SHA-256 canonical schema и реально отправленной provider schema;
- число adapter-owned schema transforms;
- safe failure class для ранних исключений.

Хранение разделено по уровню чувствительности:

| Артефакт | Что хранится |
| --- | --- |
| private raw output | exact response id, raw model output или raw provider error, полный execution snapshot |
| safe raw metadata | allowlist execution fields, response-id presence и SHA-256 вместо exact id |
| safe validation | ссылка на raw attempt и та же безопасная execution-проекция |
| safe extraction run | агрегаты по provider/profile/adapter/model, schema hashes/transforms, errors, tokens и latency |
| source facts | только существующие raw/validation refs; transport telemetry не дублируется |

Если провайдер не сообщил resolved model или usage, сохраняется `null`, а не
выдуманное значение и не ноль. Ноль сохраняется только как реально сообщённый
ноль.

## Live-проверки

### Финальная Gemini qualification

- case: `synthetic_gate2_domain_20260712005643`;
- profile: `google_gemini`;
- model: `models/gemini-3.5-flash`;
- qualification probe: `true`;
- strict raw attempts: `1`;
- fallback: `0`;
- accepted `cash_movement` facts: `1`;
- validator: `passed`;
- stitch: `complete`;
- provider execution metadata:
  - requested/resolved model совпали;
  - duration `53644 ms`;
  - input tokens `9746`;
  - output tokens `3320`;
  - provider total tokens `21053`;
  - schema transforms `101`;
  - canonical/adapted schema SHA присутствуют и различаются;
  - response id присутствовал, exact id не попал в safe audit.

Gemini OpenAI compatibility официально поддерживает structured outputs:
[Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).

Google отдельно предупреждает, что Structured Outputs поддерживает подмножество
JSON Schema и может отклонять слишком сложные схемы:
[Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output).

### Gemini normal production profile — финальный код

- case: `synthetic_gate2_domain_20260712013044`;
- capability probe: `false`;
- terminal status: `completed`;
- accepted facts: `1`;
- raw attempts: `1`;
- fallback: `0`;
- uncovered/conflict: `0/0`;
- schema transforms: `101`;
- requested/resolved model: `models/gemini-3.5-flash`;
- provider usage: input `9763`, output `3368`, total `17662`;
- duration: `37056 ms`;
- Knowledge/vector/document/file deltas: `0`.

### OpenAI normal production profile

- case: `synthetic_gate2_domain_20260711233713`;
- profile/model: `openai_gpt` / `gpt-5.6-sol`;
- capability probe: `false`;
- raw attempts: `1`;
- accepted facts: `1`;
- validator/stitch: `passed/complete`;
- fallback: `0`;
- Knowledge/vector/document/file deltas: `0`.

### Claude fail-closed proof

- case: `synthetic_gate2_domain_20260711233820`;
- profile/model: `anthropic_claude` / `claude-sonnet-5`;
- terminal result: `blocked`;
- blocker: `gate2_no_strict_structured_provider_available`;
- domain packages/raw outputs/source facts: `0/0/0`;
- provider call не выполнялся;
- Knowledge/vector/document/file deltas: `0`.

### Что произошло с Gemini 2.5 и зачем понадобился профиль

Первый post-refactor запрос к ранее проверенной
`models/gemini-2.5-pro` завершился `gate2_model_unavailable` за `3 ms` до
provider response. Повторная проверка `/api/models` показала, что эта модель
исчезла из текущего каталога; были доступны:

- `models/gemini-2.5-flash`;
- `models/gemini-3-flash-preview`;
- `models/gemini-3.1-flash-lite`;
- `models/gemini-3.5-flash`.

На раннем варианте `2.5-flash` проходил bounded canary. Финальный contract
research показал, что прямое превращение всех `const` в enum создаёт слишком
много schema states, а полный package-bound contract превышает complexity budget
2.5. Ошибка была типизирована как `gate2_model_schema_response_format_rejected`,
не как плохой ответ модели.

Gemini adapter v1.5 поэтому сохраняет строгую структуру и малые статические
semantic enums, но убирает из provider schema динамические refs/value enums,
`const`, ranges, formats и annotations. Полный исходный schema contract не
ослаблен: canonical validator проверяет его после ответа и только затем разрешает
persist. `3.5-flash` прошёл и capability probe, и обычный production profile.

## Локальные проверки и доставка

- Final full suite: `211 tests`, `passed`.
- Отдельно проверены provider matrix, one-call invariant, private/safe boundary,
  requested/resolved model mismatch, successful/error response budgets,
  null-vs-zero usage,
  response-id redaction, реальные source/domain/candidate-binding schema
  projections, source/domain runtime persistence, Closed World bundles и
  factory anti-drift.
- Все три Function bundles активны и совпадают repo/live по SHA-256:
  - Gate 1: `05352edb4a0d62dcb6ca1673f0da28b2edc83a1bfb98a18926eebe5c3c53ee8e`;
  - Gate 2 source: `7206a45c813662717006051506f00edd9dee8696c605a18d3493e7679b87d88e`;
  - Gate 2 domain: `71c1ccc1d687882a0ea9532d9be41030cee0c7a6a502071b446c9c66f8a81f59`.
- Все `12` managed Prompts прошли content/version/metadata readback.
- Все временно retained synthetic cases очищены; активных synthetic Gate 2
  cases после проверки не осталось.

## Что доказано и что не доказано

Доказано:

- изоляция provider-особенностей за profile/adapter factory;
- штатный OpenWebUI transport без core patch;
- строгий bounded путь OpenAI и Gemini;
- фактическая модель и execution metadata доступны для будущей статистики;
- private/safe граница и fail-closed validator сохранены;
- Claude не вызывается по заведомо недостоверному strict-маршруту.

Не доказано:

- strict Claude через текущий connection;
- automatic cross-provider failover;
- все модели Gemini/OpenAI и все девять доменов;
- качество на полном customer corpus;
- OCR/scanned PDF и Gate 3 tax/declaration flow.

Итоговый статус:

```text
PROVIDER_ADAPTER_FACTORY_DEPLOYED
PROVIDER_EXECUTION_METADATA_DEPLOYED
OPENAI_BOUNDED_ACCEPTANCE_PASSED
GEMINI_3_5_FLASH_QUALIFIED_AND_PRODUCTION_PASSED
CLAUDE_STRICT_ROUTE_BLOCKED_BEFORE_CALL
OPENWEBUI_CORE_UNCHANGED
REPO_LIVE_PARITY_PASSED
```
