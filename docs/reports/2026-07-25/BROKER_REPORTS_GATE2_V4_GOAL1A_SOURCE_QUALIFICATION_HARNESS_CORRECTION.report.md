# Broker Reports — Gate 2 v4, Goal 1a: source qualification harness correction

Дата: 2026-07-25

Статус: `COMPLETED`

## Результат

До первого provider call Goal 2 обнаружен execution-boundary defect:
существующий live Source Pipe с hash
`d3ba38ed554d87e01a97d7dceaffee71eaa02c88375706477d819f4ccc83d503`
не содержит economy qualification policy и economy budget enforcement.

Старый Pipe не использован для квалификации. Provider calls: `0`.

Отдельным corrective slice добавлен bounded source qualification harness,
который:

- проверяет exact live qualification Action;
- требует exact model/workload/provider authorization;
- использует текущий provider route revision;
- использует существующий economy budget;
- выполняет ровно один strict-schema call на модель;
- сравнивает ответ с frozen synthetic secretary fixtures;
- не использует production Pipe, free JSON, repair или fallback.

Goal 2 должен быть начат заново только после merge этого PR.

## Git

- accepted base `main`:
  `b18bc6b7698634a9ec65d8cbe18f876dc5ed3949`;
- implementation revision:
  `3e90011c6d004e3d50b38e4930b034904a77cf54`;
- branch:
  `codex/broker-reports-gate2-v4-goal1a-source-qualification-harness`;
- PR: [#114](https://github.com/Kwentin3/corp-openweb-ui/pull/114).

Goal 2 audit branch была пустой, не публиковалась и удалена до создания
corrective branch.

## Изменённые контракты

Добавлены:

- request profile `source_qualification_v1`;
- package
  `broker_reports_gate2_source_economy_qualification_package_v1`;
- output
  `broker_reports_gate2_source_economy_qualification_output_v1`;
- prompt
  `broker_reports_gate2_source_economy_qualification_prompt_v1`;
- safe terminal receipt
  `broker_reports_gate2_source_economy_qualification_v1`;
- CLI harness
  `live_gate2_source_economy_qualification.py`.

Additive request profile связан с существующим workload budget
`gate2_source`. Для source error taxonomy он классифицируется как source
profile.

## Контракты, явно оставленные без изменений

Не менялись:

- `GATE2_REQUEST_PROFILES` production tuple;
- production source/domain/financial/checksum routes;
- production admissions;
- economy model policy `1.4.0`;
- workload policy `1.4.0`;
- live qualification Action;
- Gate 1/source/domain Functions и valves;
- bundled Pipe files;
- managed Prompts;
- provider profiles и connections;
- frozen secretary manifest;
- frozen secretary comparator;
- canonical production parser/validator;
- Financial Evidence Registry и four-disposition contract;
- Gate 1 visual behavior;
- Knowledge/RAG/vectorization boundary;
- Gate 3.

Stage mutations: `0`.

## Bounded harness

Источник fixtures:

- schema:
  `broker_reports_gate2_secretary_benchmark_manifest_v1`;
- manifest SHA-256:
  `830c78a7ae14175fde882a30ebcc1ee08c9715a230531c5cd5a73185a139ee81`;
- source cases: `5`;
- frozen: `true`;
- customer data: `false`.

Model package содержит только:

- case ID;
- clerical instruction;
- exact synthetic source ref;
- visible literal values;
- allowed fact types;
- allowed reason codes.

`expected_output` и `allowed_literal_values` модели не передаются.

Пять fixtures объединены в один strict root object. Это оставляет provider
call budget равным `1` на exact model subject.

Проверяются:

- literal copying;
- signed decimal и leading zeros;
- date/period absence;
- currency spelling;
- exact source ref;
- bounded classification;
- invented values = 0;
- duplicate refs = 0;
- strict JSON only;
- trailing prose rejection;
- extra-case rejection;
- fallback = 0;
- repair = 0.

## Exact contract identity

| Поле | Revision |
|---|---|
| provider route | `997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| input | `broker_reports_gate2_secretary_benchmark_manifest_v1:830c78a7ae14175fde882a30ebcc1ee08c9715a230531c5cd5a73185a139ee81` |
| output | `broker_reports_gate2_source_economy_qualification_output_v1` |
| prompt | `broker_reports_gate2_source_economy_qualification_prompt_v1` |
| adapter projection | `gemini_response_format:1.5.0:997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| canonical comparator | `broker_reports_gate2_secretary_benchmark_result_v1:b024c679f447e28389479555c68494992582acc5c837f70156760466355b5f58` |

Pending/stale registry route labels не используются как current
qualification identity.

## Read-only live preflight

Общие результаты:

- qualification Action live/exact: `true`;
- exact model published: `true`;
- canonical schema SHA-256:
  `4d820214a2da4e435ca8599b676ac2410bec49f27d877f575d01c3ca2641d4e9`;
- Gemini-adapted schema SHA-256:
  `74f2519b4c4e553cbdeade440e1697c8a431232f91605291d23f2b18130b5de4`;
- deterministic schema transforms: `5`;
- estimated input tokens: `1442`;
- maximum output tokens: `4096`;
- reasoning policy: `minimal`;
- paid tools: `false`;
- provider calls: `0`.

| Exact model | Authorization SHA-256 | Estimated maximum call cost |
|---|---|---|
| `models/gemini-3.1-flash-lite` | `2da1d9e878a93512ec275b45051758394c70622227e8767bf57e286dc9e60770` | `USD 0.006504500` |
| `models/gemini-3.5-flash-lite` | `28e4b69a108cfd51694afde41bc1a3486b4ac9d5bd997e3bf718d944f336468a` | `USD 0.010672600` |

Это schema/budget estimate, не фактическая стоимость. Actual cost:
`USD 0`.

## Tests

Focused:

- `65 passed in 1.16s`.

Full service suite:

- `1383 passed`;
- `20 skipped`;
- `5` существующих SWIG deprecation warnings;
- `95.30s`.

Дополнительно:

- Ruff check: passed;
- Ruff format check для новых harness/test файлов: passed;
- deterministic sealed-output comparator test: terminal passed;
- alias/free JSON/trailing prose/extra-case negative tests: terminal failed
  closed as expected.

## Calls, privacy и cost

- provider calls: `0`;
- customer calls: `0`;
- generated outputs: `0`;
- actual input/output tokens: `0 / 0`;
- actual cost: `USD 0`;
- expensive model calls: `0`;
- fallback calls: `0`;
- repair attempts: `0`;
- stage mutations: `0`;
- customer corpus read: `false`;
- raw provider output in Git: `false`;
- secrets in report/receipt: `false`;
- Knowledge/RAG/vector writes: `0`;
- Gate 3 execution: `0`.

## Terminal reporting

- status: `COMPLETED`;
- exact revision:
  `3e90011c6d004e3d50b38e4930b034904a77cf54`;
- branch:
  `codex/broker-reports-gate2-v4-goal1a-source-qualification-harness`;
- PR: `#114`;
- contracts changed: additive source qualification request/package/output/
  prompt/harness;
- contracts unchanged: production profiles, validators, policies, live
  Functions, Prompts, provider routes и frozen authorities;
- model IDs: Gemini 3.1/3.5 Flash-Lite preflight only;
- provider/customer calls: `0 / 0`;
- tokens/cost: `0 / USD 0`;
- fallback/repair: `0 / 0`;
- focused/full tests: `65 passed / 1383 passed, 20 skipped`;
- privacy: `PASSED`;
- stage mutations: `0`;
- next permitted Goal after merge PR #114:
  restart v4 Goal 2, Gemini source qualification.
