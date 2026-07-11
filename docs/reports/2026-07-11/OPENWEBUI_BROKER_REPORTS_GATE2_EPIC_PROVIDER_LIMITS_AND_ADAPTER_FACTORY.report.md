# OpenWebUI Broker Reports Gate 2: итог эпопеи, лимиты LLM API и provider factory

Актуализация после live delivery: provider-factory/candidate-binding bundles и
managed Prompts развёрнуты с repository/live parity. Текущий terminal status и
post-deploy canary зафиксированы в
`OPENWEBUI_BROKER_REPORTS_STAGE2_LIVE_DELIVERY_AND_PROVIDER_FACTORY_ACCEPTANCE.report.md`.
Ниже сохранён исторический pre-deploy срез и причины исходного blocker.

Дата: 2026-07-11

Репозиторий: `corp-openweb-ui`

Родительская задача: Gate 2 Live Agentic Table Analysis And Structured Source-Fact Extraction

Итог: ограниченный live typed vertical доказан; общий cross-domain runtime доказан локально; новый live cross-domain proof заблокирован доступностью и возможностями LLM-провайдеров, а не ошибкой candidate-binding контракта.

## 1. Коротко простыми словами

Мы прошли путь от структурного восстановления таблиц до реального LLM-извлечения типизированных фактов.

Сначала система научилась одинаково представлять CSV, HTML, XLSX и PDF-таблицы. Затем мы доказали bounded Gate 2 путь на локальном строгом model boundary. После этого реальная GPT-модель успешно извлекла по одному `cash_movement` факту из настоящей native HTML-таблицы и настоящей PDF-таблицы. Оба результата прошли неизменённый строгий validator и stitcher.

При расширении механизма на все девять доменов обнаружилось, что одного cash-specific решения недостаточно. Мы ввели общий candidate-binding контракт: runtime механически публикует точные value candidates и relations, а LLM выбирает только их идентификаторы и допустимые semantic roles. Этот механизм локально прошёл все девять доменов.

Новый live all-domain прогон не дошёл до проверки качества candidate binding. GPT-подключение вернуло provider errors; оператор подтвердил, что на GPT mini/API connection были исчерпаны лимиты. После этого был проверен `deepseek-v4-pro`: простой JSON mode работает, но обязательный strict `json_schema` текущим подключением отвергается.

Чтобы pipeline больше не был жёстко связан с одним LLM-вендором, добавлены единый OpenWebUI adapter, provider registry и factory. Поддерживаемые семейства: GPT, Claude, Gemini, DeepSeek, Z.AI/GLM и Qwen. Для строгого Gate 2 фабрика работает fail-closed и не подменяет `json_schema` простым `json_object`.

## 2. Хронология родительской задачи

| Этап | Что было доказано | Full-suite на том снимке |
| --- | --- | ---: |
| Unified table representation | Единый private table projection для native/PDF, coverage, source-value refs, PDF fallback, no-model Gate 2 packages | 165 тестов |
| Bounded table-domain extraction | Synthetic native/PDF дали по одному `income`; real native/PDF дали безопасный `unknown_source_row`; validator/stitch прошли | 168 тестов |
| Live agentic typed vertical | Реальный GPT strict structured output дал по одному `cash_movement` для native и PDF | 171 тест |
| Cross-domain candidate binding | Общий kernel, relations и profiles локально прошли все 9 доменов | 181 тест |
| Provider adapter/factory | Шесть provider profiles, один gateway/factory, anti-drift и Closed World проверки | 193 теста |

Это последовательные состояния репозитория. Числа не складываются между собой; актуальный итоговый suite содержит 193 теста.

## 3. Что родительская задача реально доказала

### 3.1 Структурная таблица до LLM

Добавлен `broker_reports_normalized_table_projection_v0`. Native и PDF таблицы теперь приходят в Gate 2 как bounded rows/columns/cells/source-value refs, а не как сырой текст или layout soup.

Approved preflight охватил:

- 16 документов;
- 81 table projection: 67 native и 14 PDF;
- 40 PDF table candidates;
- 54 939 строк и 275 259 ячеек;
- 52 построенных Gate 2 no-model packages;
- 24 package, заблокированных текущим row budget;
- 0 duplicate и 0 unaccounted refs.

Пять документов остались partial/blocked. Большие таблицы не объявлялись complete через усечение.

Источник: `OPENWEBUI_BROKER_REPORTS_TABLE_REPRESENTATION_AND_PDF_TABLE_HARDENING.report.md`.

### 3.2 Bounded runtime, validator и stitcher

До live LLM-прогона существующий production runtime был доказан на четырёх bounded сценариях:

- synthetic native: `income=1`;
- synthetic PDF: `income=1`;
- real native: `unknown_source_row=1`;
- real PDF: `unknown_source_row=1`.

Во всех сценариях coverage был полным, conflicts и uncovered refs равнялись нулю, raw output и accepted facts сохранялись в private ArtifactStore, Knowledge/RAG/vector не использовались.

Источник: `OPENWEBUI_BROKER_REPORTS_GATE2_BOUNDED_TABLE_DOMAIN_EXTRACTION.report.md`.

### 3.3 Реальный live typed fact

На модели `gpt-5.6-sol` прошли два настоящих однодоменных vertical:

| Target | Результат |
| --- | --- |
| Native HTML, medium quality | `cash_movement=1`, accepted/rejected `1/0`, uncovered/conflict `0/0` |
| PDF, high quality | `cash_movement=1`, accepted/rejected `1/0`, uncovered/conflict `0/0` |

Оба вызова использовали provider-native `response_format=json_schema`, `strict=true`, без fallback. Validator ошибок не вернул, stitch был complete, source-value refs воспроизвелись, issue linkage сохранился. Document/file/Knowledge/vector deltas были нулевыми.

Live all-domain synthetic на этой стадии принял 8 пакетов из 9. `currency_fx` был rejected и оставил один uncovered ref, поэтому all-domain/fan-out success тогда не заявлялся.

Источник: `OPENWEBUI_BROKER_REPORTS_GATE2_LIVE_AGENTIC_TABLE_ANALYSIS.report.md`.

## 4. Зачем понадобился общий candidate-binding контракт

Первый успешный `cash_movement` refinement решал конкретную проблему: под composite/unknown headers существовало несколько механически воспроизводимых значений, а модель должна была выбрать бизнес-релевантное значение без изобретения ref или свободного переписывания суммы.

Для остальных доменов этого было недостаточно. В частности:

- `currency_fx` требует связать base/quote amounts и currencies;
- `trade_operation` требует composite binding direction/instrument/quantity-or-amount;
- `withholding_tax` требует связанную пару amount/currency;
- equal-value candidates с разными refs должны оставаться неоднозначными до явного выбора.

Поэтому был введён общий поток:

```text
bounded source unit
-> deterministic candidate discovery
-> deterministic relation discovery
-> domain binding profile
-> package-bound strict provider schema
-> LLM selects candidate/relation ids and roles
-> deterministic materializer/finalizer
-> unchanged strict validator
-> deterministic stitcher
```

Локальный all-domain production-factory proof дал:

- binding accepted: `9/9`;
- strict facts accepted: `9/9`;
- complete stitch: `9/9`;
- conflicts: `0`;
- uncovered refs: `0`;
- FX four-part relation: passed locally;
- trade composite binding: passed locally;
- 14 негативных/repair cases: fail-closed.

Таким образом, общий контракт и deterministic runtime работают. Не завершена именно его новая live-проверка.

## 5. Почему live LLM-прогон упал

Важно разделять локальные тесты и live provider proof.

Локальные unit/integration/Closed World тесты не падали. Live прогон завершился typed provider errors до model-produced binding object и до candidate-binding validator.

### 5.1 GPT API limits / provider availability

All-domain candidate-binding run:

```text
run: sfdrun_7aebe1e364ecb97bcaff752c
accepted: 0
rejected: 9
safe error: gate2_model_provider_error=9
candidate validation errors: 0
```

Новый real cash regression на `gpt-5.6-sol` также дал:

```text
run: sfdrun_5bcd889970fe6c9479abb5d1
accepted: 0
rejected: 1
safe error: gate2_model_provider_error=1
```

Повторные проверки затронули `gpt-5.6-sol`, `gpt-5.4-mini-2026-03-17` и `gpt-5.6-luna`. В safe artifacts это отражено общим кодом `gate2_model_provider_error`. Оператор отдельно подтвердил фактическую причину: на выбранном GPT mini/API connection были исчерпаны лимиты.

Итого по этой группе: 10 provider-availability errors. По операторскому подтверждению их причиной были исчерпанные лимиты выбранного GPT API connection. Это не 10 ошибок схемы, validator или binding kernel.

### 5.2 DeepSeek control

Подключённая модель: `deepseek-v4-pro`.

Простой isolated control с `response_format=json_object` вернул HTTP 200, валидный JSON и ожидаемую трёхполевую/nested-binding форму. Это подтвердило, что соединение и базовый JSON mode работают.

Строгий Gate 2 control дал:

```text
run: sfdrun_a8981d85cc1b1625f33b9a8b
accepted: 0
rejected: 9
safe error: gate2_model_schema_response_format_rejected=9
model-produced binding objects: 0
fallback outputs: 0
```

Это отдельная причина, не GPT quota incident: текущий DeepSeek/OpenWebUI path отвергает `response_format=json_schema, strict=true` до генерации объекта. Переход на JSON mode не был использован, потому что он гарантирует только синтаксически валидный JSON, но не package-bound schema adherence.

### 5.3 Сводный live результат нового контракта

```text
accepted: 0
rejected: 19
provider availability errors, operator-attributed to exhausted GPT limits: 10
strict-schema capability rejections: 9
candidate-contract validation errors: 0
```

Поэтому live blocker нельзя исправлять ослаблением validator или candidate-binding контракта.

## 6. Что добавлено в adapter/factory refactor

### 6.1 Новая граница

Теперь production path выглядит так:

```text
Gate 2 runtime
-> Gate2StructuredModelClient protocol
-> Gate2StructuredModelClientFactory.create
-> one Gate2OpenWebUIStructuredModelClient
-> configured OpenWebUI model_id
```

Добавлены:

- `broker_reports_gate1/gate2_model_contracts.py` — общий protocol/result, provider profiles и typed config;
- `broker_reports_gate1/gate2_model_requests.py` — versioned `source_v0` и `domain_v0` request builders, включая candidate-binding mode;
- `broker_reports_gate1/gate2_model_clients.py` — единый OpenWebUI adapter и factory;
- `provider_profile_id` в source/domain Pipe Valves и runtime config;
- новые модули во всех трёх self-contained bundles;
- characterization, provider-matrix, anti-drift и Closed World tests.

Оба Pipe больше не импортируют OpenWebUI completion functions, не строят provider payload самостоятельно и не содержат отдельные response decoders/error classifiers.

### 6.2 Provider registry

| Profile | Семейство | Статус для strict Gate 2 |
| --- | --- | --- |
| `openai_gpt` | GPT / OpenAI | `approved` capability profile; runtime health проверяется отдельно |
| `anthropic_claude` | Claude / Anthropic | `probe_required` |
| `google_gemini` | Gemini / Google | `probe_required` |
| `deepseek` | DeepSeek | `unsupported` для strict final JSON Schema в текущем контракте |
| `zai_glm` | Z.AI / GLM | `unsupported` для strict final JSON Schema |
| `alibaba_qwen` | Qwen / Alibaba Model Studio | `unsupported` для strict final JSON Schema |

`approved` здесь означает технический capability profile, а не наличие текущей квоты. Именно поэтому capability и provider health должны оставаться разными состояниями.

Для неподходящего профиля factory возвращает `gate2_no_strict_structured_provider_available` до необратимого provider call. Скрытого downgrade `json_schema -> json_object` нет.

### 6.3 Устранён повторный provider call

Старые adapters выбирали совместимую OpenWebUI callable signature через `try/except TypeError`. Если provider function уже начала выполнение и сама выбросила `TypeError`, вызов мог повториться до трёх раз.

Новый adapter сначала проверяет callable signature, затем выполняет provider call ровно один раз. Тест отдельно подтверждает `calls=1` для трёх поддерживаемых OpenWebUI signatures и для внутреннего provider `TypeError`.

## 7. Итоговая проверка после refactor

PowerShell / Python 3.11:

```text
targeted provider/factory/runtime/bundle suite: 46 tests, OK
full unittest discovery: 193 tests, OK
compileall: passed
git diff --check: passed
deterministic bundle rebuild: passed
isolated bundle import without workspace path: passed
```

Provider matrix проверена для всех 12 комбинаций `6 provider families x 2 request profiles`:

- default production admission работает fail-closed;
- controlled capability probe делает один strict call;
- response schema не переписывается и не понижается;
- source/domain/candidate requests сохраняют прежние deterministic payloads;
- typed provider errors и private raw output сохраняются;
- unsupported/invalid paths останавливаются до completion resolver;
- factory anti-drift anchors проверены;
- новых provider SDK и runtime dependencies не добавлено.

Все три bundles содержат по 49 embedded modules и импортируются в isolated Python mode. Повторная сборка дала те же SHA-256:

```text
Gate 1 bundle: 9079D2BA406E6CEA0731E651969370C3F525119A835F7CDA54015614CECAB5C1
Gate 2 source bundle: 3BB55F437ED487F6339B6F45BE642346C05D87F6BE1C2CFADE6A39BA4CB693F4
Gate 2 domain bundle: C8A557D5E1322D7F78FE35D19390AEE9DFAA92A6B2ADEAB891B17087F795492D
```

Новый factory bundle пока не выкладывался на live-сервер. Текущие updater scripts одновременно reseed managed Prompts, поэтому их запуск без отдельного deploy scope изменил бы больше, чем этот структурный refactor.

## 8. Ограничение автоматического failover

Factory устранил provider-specific код в Pipe и ввёл capability routing, но скрытый cross-provider failover внутри одного model call пока не включён.

Причина контрактная: package и persisted audit заранее фиксируют `model_id`. Если adapter после provider error незаметно переключится на другую модель, accepted fact будет содержать недостоверный audit. Для честного automatic failover нужна отдельная миграция audit-контракта: provider/connection/model attempt chain должен стать частью package/raw-output/final audit.

До такой миграции безопасное поведение — typed terminal error и явный повтор полного bounded run с другим approved provider profile.

## 9. Общий итог родительской задачи

### Доказано

- единый native/PDF table representation и deterministic coverage;
- bounded table-domain package path;
- strict source-fact validator, source-value reproduction и deterministic stitch;
- private ArtifactStore persistence и zero Knowledge/RAG/vector/document writes;
- реальный native `cash_movement=1` через live GPT strict structured output;
- реальный PDF `cash_movement=1` через live GPT strict structured output;
- общий cross-domain candidate/relation/binding runtime;
- локальная production-factory матрица `9/9` доменов;
- локальный FX relational и trade composite proof;
- единый adapter/factory и provider registry для GPT, Claude, Gemini, DeepSeek, Z.AI и Qwen;
- актуальный full-suite `193 tests, OK`.

### Не доказано

- хотя бы один accepted live fact через новый cross-domain candidate-binding mode;
- новый native/PDF cash regression через candidate binding;
- второй реальный live domain;
- live `currency_fx` relational binding;
- live all-domain/fan-out stitch;
- Claude/Gemini exact-schema compatibility через текущее OpenWebUI connection;
- automatic audited provider failover;
- broad/default multi-domain activation;
- live deployment нового provider factory bundle.

## 10. Следующий правильный proof

1. Восстановить квоту GPT либо подключить provider/model, который принимает exact dynamic strict JSON Schema.
2. Через тот же factory path выполнить маленький exact-schema canary для Claude, затем Gemini.
3. Повторить synthetic all-domain candidate-binding run и получить accepted `9/9` без fallback.
4. Повторить native и PDF `cash_movement` regression через новый candidate-binding mode.
5. Выполнить доступный real PDF `position_snapshot` vertical.
6. Только после этого решать вопрос о live FX/fan-out и ограниченном multi-domain expansion.

Ни один из этих шагов не требует ослаблять validator или возвращаться к free-form/JSON-only extraction.

## 11. Финальные статусы

```text
TABLE_REPRESENTATION_CONTRACT_READY
TABLE_DOMAIN_AGENT_RUNTIME_READY
CASE_GROUP_002_NATIVE_REAL_TYPED_FACT_PASSED
CASE_GROUP_002_PDF_REAL_TYPED_FACT_PASSED
TABLE_SOURCE_FACT_VALIDATOR_PASSED
TABLE_ROW_COVERAGE_PROVEN
TABLE_SOURCE_VALUE_REFS_PROVEN
TABLE_ISSUE_CARRY_FORWARD_PROVEN
GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_RUNTIME_READY
GATE2_ALL_DOMAIN_BINDING_MATRIX_SYNTHETIC_PASSED
GATE2_PROVIDER_ADAPTER_FACTORY_LOCAL_PASSED
GATE2_PROVIDER_MATRIX_REGISTERED
GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_PARTIAL
LIVE_CROSS_DOMAIN_PROOF_NOT_COMPLETE provider_availability_or_strict_schema_capability_blocker
PROVIDER_FACTORY_LIVE_DEPLOY_NOT_PERFORMED
READY_FOR_STRICT_PROVIDER_CANARY_AND_BOUNDED_RERUN
```

Не заявляются:

```text
CASH_MOVEMENT_CANDIDATE_BINDING_REGRESSION_PASSED
SECOND_LIVE_DOMAIN_CANDIDATE_BINDING_PASSED
CURRENCY_FX_RELATIONAL_BINDING_PASSED
TABLE_DOMAIN_AGENT_SYNTHETIC_LIVE_PASSED
TABLE_AGENTIC_FANOUT_STITCH_PASSED
READY_FOR_MULTI_DOMAIN_LIVE_TABLE_EXTRACTION_PROOFS
```

## 12. Связанные отчёты

- `OPENWEBUI_BROKER_REPORTS_TABLE_REPRESENTATION_AND_PDF_TABLE_HARDENING.report.md`;
- `OPENWEBUI_BROKER_REPORTS_GATE2_BOUNDED_TABLE_DOMAIN_EXTRACTION.report.md`;
- `OPENWEBUI_BROKER_REPORTS_GATE2_LIVE_AGENTIC_TABLE_ANALYSIS.report.md`;
- `OPENWEBUI_BROKER_REPORTS_GATE2_CROSS_DOMAIN_CANDIDATE_BINDING_REFACTOR.report.md`.
