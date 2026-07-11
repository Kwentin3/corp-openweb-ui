# OpenWebUI Broker Reports Stage 2: live delivery и provider-factory acceptance

Дата: 2026-07-11

Репозиторий: `corp-openweb-ui`

Контур: Broker Reports Gate 1 / Gate 2

## 1. Итог

Текущая реализация нормализации таблиц, candidate binding и provider factory
доставлена в live OpenWebUI. Три Function bundle и двенадцать managed Prompts
перечитаны с сервера и совпадают с репозиторием по содержимому и версиям.

Новый bounded live contour дошёл до deployed factory и строгого
`response_format=json_schema`, но accepted candidate-binding fact не получен:
подключение GPT вернуло точный typed blocker
`gate2_model_provider_quota_exceeded`. DeepSeek был корректно остановлен до
provider call как профиль без подтверждённого strict final JSON Schema.

Таким образом:

- live deployment и repository/live parity прошли;
- provider capability и quota классифицируются раздельно;
- скрытого перехода на `json_object` или free-form JSON нет;
- post-deploy candidate-binding acceptance остаётся заблокирован внешней
  квотой GPT;
- ослаблять candidate-binding, provenance, validator или stitch контракт не
  требуется.

## 2. Какой дополнительный объём появился в Stage 2

В исходной рамке Broker Reports недооценивался объём подготовки документов до
LLM. Реализованный контур теперь включает:

1. извлечение текстового слоя PDF без автоматического OCR;
2. восстановление layout и механических table candidates;
3. единое представление native/PDF таблиц;
4. bounded rows, columns, cells и original-value refs;
5. deterministic source-value candidates и candidate relations;
6. доменные binding profiles;
7. provider-native strict structured output;
8. candidate-binding materialization;
9. строгий source-fact validator;
10. deterministic ownership, coverage и stitch;
11. provider capability registry, adapter и factory.

Сканы и страницы без текстового слоя не стали автоматически поддерживаться.
OCR/VLM остаётся отдельной будущей границей.

## 3. Что было доставлено

### 3.1 Functions

| Function | Repository/live SHA-256 | Результат |
| --- | --- | --- |
| `broker_reports_gate1_pipe` | `c1367dfa37c9017d838993e0c7204d81aabb890f4d5fbb759265368297be402b` | match, active |
| `broker_reports_gate2_source_fact_pipe` | `2796d3f2322e116061e95870f795e38d7a960cf186fdd5abb44cf09d7a38b67e` | match, active |
| `broker_reports_gate2_domain_source_fact_pipe` | `989a1d6d4674b694cd1de742a3e680c8e090335fe993de58e8e73652ebcd22a6` | match, active |

Gate 2 source/domain bundles содержат:

- `gate2_model_contracts`;
- `gate2_model_requests`;
- `gate2_model_clients`;
- `Gate2StructuredModelClientFactory`;
- source/domain runtime factories;
- candidate-binding kernel/runtime;
- validator и stitcher.

Обновление OpenWebUI core не выполнялось.

### 3.2 Managed Prompts

Independent readback проверил `12/12` активных Prompt contracts:

- Gate 1 document passport: `1`;
- Gate 1 clarification: `1`;
- Gate 2 source facts: `1`;
- Gate 2 domain prompts: `9`.

Версии Gate 2 после reconciliation:

```text
source: 2026-07-11-provider-factory-v0
domain: 2026-07-11-candidate-binding-provider-factory-v0
```

Для каждого Prompt сравнивались реально перечитанные DB content SHA-256,
command, version, active flag и безопасные contract metadata. Updater больше не
подтверждает Prompt hash переданным им же expected value.

## 4. Factory boundary

Production path:

```text
OpenWebUI Function
-> Gate2StructuredModelClientFactory.create
-> Gate2OpenWebUIStructuredModelClient
-> configured OpenWebUI model connection
```

Source и domain Pipe не импортируют completion functions и не содержат
собственных provider payload decoders. Candidate-binding acceptance scripts
вызывают Function ID и явно передают `provider_profile_id`.

Зарегистрированы шесть профилей:

| Profile | Текущий strict Gate 2 статус |
| --- | --- |
| `openai_gpt` | approved capability; availability проверяется отдельно |
| `anthropic_claude` | probe required |
| `google_gemini` | probe required |
| `deepseek` | unsupported для strict final JSON Schema |
| `zai_glm` | unsupported для strict final JSON Schema |
| `alibaba_qwen` | unsupported для strict final JSON Schema |

Factory не выполняет автоматический failover и не понижает контракт:

```text
json_schema strict
-> json_object
-> free-form JSON
```

## 5. Доказательство repository/live parity

До деплоя read-only baseline показал:

- все три live Function hashes отличались от текущих bundles;
- required factory modules отсутствовали в live bundles;
- Gate 2 source Prompt content отличался от контракта;
- девять domain Prompt contents совпадали, но version contract отставал.

После деплоя отдельный read-only verifier дал:

```text
all_function_bundles_match=true
all_managed_prompts_match=true
provider_profiles_complete=true
repository_factory_boundary_passed=true
status=passed
```

Verifier не выводит Prompt content, учётные данные, server/env values или
private source payload.

## 6. Bounded live acceptance

### 6.1 Approved real-case preflight

Повторный post-deploy preflight для `case_group_002` не дошёл до модели:

```text
active_records_total=0
domain_context_packets_total=0
blocker=case_group_gate2_dcp_count_invalid
```

Поэтому реальные native/PDF документы не загружались заново и не
обрабатывались. Ранее доказанные native/PDF `cash_movement` vertical остаются
историческим baseline предыдущего bundle, но не объявляются повторно
доказанными после этого deploy.

### 6.2 GPT strict candidate-binding canary

Был создан один synthetic bounded source unit и выбран только домен
`cash_movement`:

```text
case_id=synthetic_gate2_domain_20260711214005
extraction_run_id=sfdrun_5f4216a712d9381d867afac2
provider_profile_id=openai_gpt
model_id=gpt-5.6-sol
candidate_binding_enabled=true
domain_packages=1
strict_raw_outputs=1
fallback_raw_outputs=0
accepted_facts=0
error=gate2_model_provider_quota_exceeded
```

Фактический результат:

- deployed Function/factory path использован;
- candidate set и relation set созданы;
- provider request сохранил strict JSON Schema mode;
- provider вернул quota blocker до model-produced binding object;
- пакет отклонён;
- source facts не созданы;
- candidate-binding/source-fact validator не ослаблялись;
- `26` synthetic records очищены.

### 6.3 DeepSeek capability canary

Тот же one-domain contour был запущен с профилем `deepseek`:

```text
case_id=synthetic_gate2_domain_20260711214531
blocker=gate2_no_strict_structured_provider_available
domain_packages=0
raw_outputs=0
source_facts=0
fallback_outputs=0
```

Factory остановил путь до provider call. Это ожидаемое fail-closed поведение:
подключённый JSON mode не считается заменой strict final JSON Schema. `17`
synthetic records очищены.

### 6.4 Раздельная атрибуция результатов

| Категория | Post-deploy результат |
| --- | --- |
| Provider capability | DeepSeek отклонён до call: `gate2_no_strict_structured_provider_available` |
| Provider availability/quota | GPT: `gate2_model_provider_quota_exceeded=1` |
| Schema-format rejection | В post-deploy canary не возник; strict request не понижался. Исторический DeepSeek path ранее возвращал schema rejection до factory refactor |
| Candidate-binding validation | Не выполнялась: model binding object не получен |
| Source-fact validation | Accepted fact отсутствовал; validation contract не ослаблялся |

Provider outage или quota не интерпретируются как ошибка candidate-binding
контракта.

## 7. Contamination guards

Оба bounded canary показали:

```text
document_rows_delta=0
file_rows_delta=0
knowledge_rows_delta=0
vector_collections_delta=0
vector_files_delta=0
vector_size_delta=0
knowledge_backend_records=0
ordinary_upload_used=false
```

Raw provider error сохранился только как private ArtifactStore audit. Failed
attempt не создал accepted source facts. Synthetic artifacts были purged после
аудита.

## 8. Локальные и post-deploy проверки

Финальный локальный контур:

```text
full unittest discovery: 198 tests, OK
focused Closed World/factory/readback tests: 9 tests, OK
compileall: passed
double deterministic bundle build: passed
git diff --check: passed
changed-file trailing whitespace scan: 0
```

Closed World доказан isolated bundle imports без workspace package path.
Generated bundles не содержат абсолютных workspace paths или `sys.path.insert`
runtime hacks. Новых provider SDK/runtime dependencies не добавлено.

## 9. Документация

Техническая документация теперь явно разделяет:

- PDF text-layer normalization и отдельный OCR/VLM future path;
- deterministic structure restoration и LLM business interpretation;
- original-value refs и запрет свободной генерации source values;
- локальное доказательство, live delivery и live model acceptance;
- provider capability, provider availability и schema support;
- deployed candidate-binding/factory и незавершённый accepted-fact proof.

Customer-facing раздел простыми словами объясняет:

- почему визуальная PDF-таблица не является готовой электронной таблицей;
- как восстанавливаются строки, столбцы и ячейки;
- почему LLM получает только bounded fragments;
- как validator сверяет выбранные значения с исходными ячейками;
- почему OCR не включается из-за логотипов, подписей или изображений;
- почему поддержка нескольких provider profiles не означает поддержку всех
  providers или automatic failover.

## 10. Ограничения

Не доказаны и не заявляются:

- accepted live fact через новый candidate-binding contract;
- post-deploy native/PDF real-case regression;
- второй live domain;
- live `currency_fx` relational binding;
- all-domain/fan-out live completion;
- Claude/Gemini exact-schema compatibility;
- DeepSeek strict final JSON Schema support;
- automatic cross-provider failover;
- OCR/scanned-PDF support;
- full corpus-wide extraction;
- Gate 3, tax, declaration или XLS/XLSX readiness.

## 11. Следующий bounded шаг

1. Восстановить квоту approved GPT connection либо подтвердить другой provider
   через exact strict-schema canary.
2. Восстановить или заново создать только явно approved bounded real-case
   artifacts без Knowledge/RAG/ordinary upload.
3. Повторить один native `cash_movement` candidate-binding regression.
4. После его accepted terminal outcome повторить PDF target.
5. Только затем брать второй домен.

## 12. Финальные статусы

Доказано:

```text
STAGE2_ADDITIONAL_PDF_TABLE_EXTRACTION_SCOPE_DOCUMENTED
GATE2_PROVIDER_FACTORY_LIVE_DEPLOYED
GATE2_CANDIDATE_BINDING_LIVE_DEPLOYED
GATE2_MANAGED_PROMPTS_LIVE_RECONCILED
GATE2_LIVE_BUNDLE_REPOSITORY_PARITY_PROVEN
GATE2_STRICT_PROVIDER_CANARY_COMPLETED
STAGE2_CUSTOMER_PDF_PIPELINE_DOCUMENTATION_UPDATED
STAGE2_TECHNICAL_DOCUMENTATION_RECONCILED
STAGE2_POST_DEPLOY_TESTS_PASSED
GATE2_CANDIDATE_BINDING_LIVE_DEPLOYMENT_PASSED
LIVE_STRICT_PROVIDER_ACCEPTANCE_BLOCKED
gate2_model_provider_quota_exceeded
SYNTHETIC_BOUNDED_VECTOR_GUARD_PASSED
SYNTHETIC_BOUNDED_KNOWLEDGE_GUARD_PASSED
```

Не заявляются:

```text
GATE2_BOUNDED_LIVE_REGRESSION_COMPLETED
GATE2_CANDIDATE_BINDING_LIVE_ACCEPTANCE_PASSED
CASE_GROUP_002_VECTOR_GUARD_PASSED
CASE_GROUP_002_KNOWLEDGE_GUARD_PASSED
READY_FOR_NEXT_BOUNDED_MULTI_DOMAIN_PROOF
```

Текущая система готова к повтору одного bounded strict-provider proof после
восстановления квоты. К multi-domain expansion она пока не допущена.
