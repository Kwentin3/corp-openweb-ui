# Broker Reports Gate 2: native provider transport refactor

Дата: 2026-07-12

Итог: `GATE2_NATIVE_PROVIDER_TRANSPORT_PARTIAL`.

Единый Gate 2 contract, candidate-binding validator, source-fact validator и
deterministic stitcher сохранены. Native Anthropic Messages transport добавлен
в существующий factory/adapter слой и развёрнут как штатная OpenWebUI Pipe
Function. Provider credentials теперь разрешаются из единого административного
реестра Connections OpenWebUI; отдельных API-key Valve у Gate 2 нет. OpenAI и
Gemini post-deploy synthetic proof прошёл. Claude native call доступен, но
полный рабочий candidate-binding schema отклонён Anthropic. Real Gemini proof
прошёл для bounded native и PDF `cash_movement`, но второй typed domain не
подтверждён.

## 1. Архитектура

```text
Gate 2 source/domain runtime
  -> Gate2StructuredModelClientFactory.create
  -> Gate2ProviderProfile
  -> Gate2ProviderAdapterFactory.create
  -> OpenAI/Gemini OpenWebUI completion transport
     or Anthropic native Messages adapter inside OpenWebUI Pipe
  -> strict structured output
  -> unchanged candidate-binding materializer/validator
  -> unchanged source-fact validator
  -> deterministic stitcher
```

Pipe не знает vendor payload, endpoint, response shape или provider error
format. Anthropic URL, headers, `output_config.format`, native response parsing
и configuration validation принадлежат
`Gate2AnthropicNativeMessagesAdapter`. Общий model client различает только
OpenWebUI completion и adapter-owned native invocation.

OpenWebUI документирует Pipe Functions как штатный способ подключать API,
которые не следуют OpenAI protocol, включая Anthropic native. Core patch не
нужен: [OpenWebUI Functions](https://docs.openwebui.com/features/extensibility/plugin/functions/).

## 2. Provider capability matrix

| Profile | Capability | Availability | Transport | Gate 2 verdict |
| --- | --- | --- | --- | --- |
| `openai_gpt` | approved | available | OpenAI Chat Completions через OpenWebUI | approved для `gpt-5.6-sol` |
| `google_gemini` | approved | available | Gemini OpenAI compatibility через OpenWebUI, schema projection + canonical validation | approved для `models/gemini-3.5-flash` |
| `anthropic_claude` | probe required | available | native `/v1/messages` через OpenWebUI Pipe и admin Connection | qualification only: рабочий schema rejected |
| `deepseek` | unsupported | отдельно не квалифицировалась | compatibility | blocked |
| `zai_glm` | unsupported | отдельно не квалифицировалась | compatibility | blocked |
| `alibaba_qwen` | unsupported | отдельно не квалифицировалась | compatibility | blocked |

Capability, availability и suitability теперь отдельные поля profile. Quota,
rate limit, model catalog и missing credential не превращают модель в
`unsupported`. Exact model approval по-прежнему отделён от provider-family
capability.

### OpenAI

OpenAI Structured Outputs поддерживает strict JSON Schema в актуальных
моделях; официальная текущая family рекомендует `gpt-5.6-luna` для эффективной
массовой нагрузки и `gpt-5.6-sol` для максимальной сложности:
[latest model guide](https://developers.openai.com/api/docs/guides/latest-model),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

- live-approved: `gpt-5.6-sol`;
- extraction candidate requiring qualification: `gpt-5.6-luna`;
- complex fallback candidate: `gpt-5.6-sol`.

### Gemini

Google документирует `gemini-3.5-flash` как stable и Structured Outputs как
JSON Schema subset. Поэтому adapter-owned schema projection остаётся
наблюдаемой, а полный canonical contract проверяется после ответа:
[Gemini models](https://ai.google.dev/gemini-api/docs/models),
[Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output).

- live-approved extraction: `models/gemini-3.5-flash`;
- complex fallback candidate requiring qualification:
  `models/gemini-3.1-pro-preview`;
- raw Gemini-native REST transport не добавлялся: текущий approved compatibility
  route уже доказал strict bounded contract. Если архитектурная политика требует
  только raw native API, это остаётся отдельным blocker.

### Anthropic

Anthropic strict JSON output использует Messages API
`output_config.format`; OpenAI compatibility не является заменой этого
контракта. Structured Outputs доступны, в частности, для Claude Haiku 4.5 и
Claude Sonnet 5:
[Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
[Claude models](https://platform.claude.com/docs/en/about-claude/models/overview).

- extraction candidate: `claude-haiku-4-5-20251001`;
- complex fallback candidate: `claude-sonnet-5`;
- availability: `available`; endpoint и API key берутся из включённого
  Anthropic connection в административных настройках OpenWebUI;
- production approval: отсутствует до live exact candidate-binding proof.

## 3. Native adapter changes

- Добавлен `Gate2AnthropicNativeMessagesAdapter` в существующий adapter factory.
- Canonical `response_format.type=json_schema`, `strict=true` обязателен на
  входе; downgrade отсутствует.
- Adapter переносит только schema в `output_config.format`; canonical и adapted
  SHA-256 совпадают, transform count равен `0`.
- System/user messages преобразуются внутри adapter; Pipe не строит Messages
  payload.
- Native content blocks, usage, stop reason, response id и model разбираются
  внутри adapter.
- `Gate2OpenWebUIProviderConnectionResolver` выбирает ровно одно включённое
  admin Connection по profile URL prefix и fail-closed блокирует missing или
  ambiguous configuration.
- Credential не входит в Function Valve, execution metadata, safe report или
  request body Gate 2 и скрыт из `repr` connection DTO.
- Использована только Python standard library внутри bundled Function; новых
  runtime packages и OpenWebUI core patch нет.

## 4. Execution metadata and benchmark readiness

`gate2_provider_execution_metadata_v1` дополнен `transport_type`. Он сохраняет:

- provider/profile и profile revision;
- adapter id/version;
- requested/resolved model;
- actual transport type и structured-output mode;
- canonical/adapted schema hashes и transform count;
- duration, provider-reported usage и finish reason;
- private response id; safe projection хранит только presence + SHA-256;
- safe failure class.

Пример safe synthetic metadata:

```json
{
  "provider_profile_id": "google_gemini",
  "adapter_id": "gemini_response_format",
  "transport_type": "gemini_openai_compatibility_via_openwebui",
  "requested_model_id": "models/gemini-3.5-flash",
  "resolved_model_id": "models/gemini-3.5-flash",
  "structured_output_mode": "openwebui_response_format_json_schema",
  "canonical_request_schema_hash": "sha256_present",
  "adapted_request_schema_hash": "sha256_present",
  "schema_transform_count": 49,
  "provider_response_id_present": true
}
```

Safe run summary теперь агрегирует provider/profile/adapter/transport/model,
success/failure class, latency, token usage и schema transforms. API providers
не вернули cost field, поэтому стоимость не выдумывается и должна добавляться
внешним price snapshot при будущих benchmark runs.

## 5. Synthetic proof

Один и тот же bounded synthetic `cash_movement` candidate package:

| Provider/model | Result | Latency | Input/output tokens | Fallback |
| --- | --- | ---: | ---: | --- |
| OpenAI `gpt-5.6-sol` | 1 typed fact, validator passed, stitch complete | 15 891 ms | 14 181 / 866 | 0 |
| Gemini `models/gemini-3.5-flash` | 1 typed fact, validator passed, stitch complete | 28 384 ms | 16 673 / 762 | 0 |
| Anthropic `claude-sonnet-4-6` | admin Connection resolved; provider rejected full candidate schema, facts 0 | 2 148 ms | not reported | 0 |

У всех запусков Knowledge, vector, document и file deltas равны нулю. Synthetic
cases очищены. Claude result доказывает рабочие admin credential resolution,
native routing и provider reachability, но не strict-schema success полного
Gate 2 контракта.

## 6. Real bounded regression

Safe preflight нашёл bounded native HTML и PDF `cash_movement` targets; raw
customer values в этот отчёт не включены.

- Gemini `models/gemini-3.5-flash`: native target passed, 1 typed fact;
- Gemini `models/gemini-3.5-flash`: PDF target passed, 1 typed fact;
- оба: validator passed, stitch complete, fallback/repair 0, Knowledge/vector/
  document/file deltas 0;
- OpenAI повтор: native target завершился `gate2_model_provider_error`, PDF
  target дал только accepted `unknown_source_row`; typed proof не пройден;
- second domain `position_snapshot`: accepted `unknown_source_row`, typed fact 0;
- second domain `income`: eligible target отсутствует.

Следовательно, bounded real native/PDF cash proof есть для Gemini, но общий
`GATE2_NATIVE_PROVIDER_REAL_PROOF_PASSED` не заявляется: second-domain gate не
пройден.

## 7. Verification and deployment

- local: `python -m unittest discover -s tests -p "test_*.py"` -> 214 passed;
- bundle closed-world/import/factory anti-drift tests passed;
- `git diff --check` passed;
- repository/live bundle SHA parity passed:
  - Gate 1: `09fa2c6c785e20eb8d561c235596e88e336b4df917a00b9f83a4ad5daa689be9`;
  - Gate 2 source: `ec8edf6df345761ba1e3f03d18e9eeaeeb20575388c075191c52aac226d392d4`;
  - Gate 2 domain: `a52497523645a45d7585f437404b9e43106991a0db9d3995de2b899776b5f060`;
- 12 managed Prompts passed content/version/metadata readback;
- OpenWebUI core unchanged.

Customer-facing docs не менялись: transport refactor не изменяет пользовательский
workflow или обещания продукта.

## 8. Remaining blockers

1. Исследовать, какой участок полного candidate-binding schema Anthropic
   отклоняет, не ослабляя canonical validator и не вводя JSON fallback.
2. Повторить exact synthetic candidate-binding qualification через native
   Messages после допустимой provider-specific schema projection; только после
   validator pass добавить exact Claude model id в `approved_model_ids`.
3. Подтвердить второй real typed domain (`position_snapshot` или `income`) на
   подходящем bounded target.
4. Если требуется буквально raw Gemini native API, добавить отдельный native
   Gemini adapter/profile и квалифицировать его; текущий strict route остаётся
   compatibility transport.
5. Не вводить automatic failover или cost-based routing до репрезентативного
   benchmark. Routing metadata должен учитывать domain ambiguity,
   reconstruction quality, validation history, capability и policy, а не размер
   таблицы.

## 9. Final statuses

```text
GATE2_NATIVE_PROVIDER_ADAPTER_ARCHITECTURE_READY
OPENAI_NATIVE_STRICT_TRANSPORT_READY
GATE2_PROVIDER_CAPABILITY_MATRIX_READY
GATE2_EXECUTION_METADATA_READY
GATE2_PROVIDER_BENCHMARK_READY

GATE2_NATIVE_PROVIDER_TRANSPORT_PARTIAL
ANTHROPIC_NATIVE_CANDIDATE_SCHEMA_REJECTED
GEMINI_RAW_NATIVE_TRANSPORT_NOT_IMPLEMENTED
GATE2_REAL_SECOND_DOMAIN_TYPED_PROOF_BLOCKED
```

Не заявлены:

```text
GEMINI_NATIVE_STRICT_TRANSPORT_READY
ANTHROPIC_NATIVE_STRICT_TRANSPORT_READY
GATE2_MULTI_PROVIDER_SYNTHETIC_PROOF_PASSED
GATE2_NATIVE_PROVIDER_REAL_PROOF_PASSED
```
