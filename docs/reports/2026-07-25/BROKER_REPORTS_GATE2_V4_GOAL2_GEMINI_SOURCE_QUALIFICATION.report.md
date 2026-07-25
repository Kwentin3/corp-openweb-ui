# Broker Reports — Gate 2 v4, Goal 2: Gemini source qualification

Дата: 2026-07-25

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`

## Результат

Обе exact Gemini-кандидатуры формально проверены для workload
`gate2_source` в заданном порядке:

1. `models/gemini-3.1-flash-lite`;
2. `models/gemini-3.5-flash-lite`.

Итог:

- `GEMINI_3_1_SOURCE: NOT_QUALIFIED`;
- `GEMINI_3_5_SOURCE: NOT_QUALIFIED`;
- `CANONICAL_VALIDATOR_CHANGE: ZERO`;
- `EXPENSIVE_CALLS: ZERO`.

Обе модели приняли strict provider schema, вернули terminal output и точно
сохранили проверяемые literal values и source bindings. Однако неизменённый
frozen canonical comparator отклонил все 5 source cases с terminal code
`expected_value_mismatch`.

Ни одна модель не добавлена в production admissions. Source qualification
не переносится на domain или financial workloads.

## Git

- accepted execution revision:
  `943a496dcc33937404ee2d066cd71cf9b1b541ba`;
- branch:
  `codex/broker-reports-gate2-v4-goal2-gemini-source-qualification`;
- PR: [#115](https://github.com/Kwentin3/corp-openweb-ui/pull/115).

## Qualification identity

Для обеих моделей использована одна exact workload identity:

| Contract | Revision |
|---|---|
| exact workload | `gate2_source` |
| provider profile | `google_gemini` |
| provider route | `997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| input | `broker_reports_gate2_secretary_benchmark_manifest_v1:830c78a7ae14175fde882a30ebcc1ee08c9715a230531c5cd5a73185a139ee81` |
| output | `broker_reports_gate2_source_economy_qualification_output_v1` |
| prompt | `broker_reports_gate2_source_economy_qualification_prompt_v1` |
| adapter projection | `gemini_response_format:1.5.0:997bc0306756ddc127bf7d87b2a8e495af88f6fe03814414d1bf289eacdeeeba` |
| canonical comparator | `broker_reports_gate2_secretary_benchmark_result_v1:b024c679f447e28389479555c68494992582acc5c837f70156760466355b5f58` |
| canonical request schema SHA-256 | `4d820214a2da4e435ca8599b676ac2410bec49f27d877f575d01c3ca2641d4e9` |
| adapted request schema SHA-256 | `74f2519b4c4e553cbdeade440e1697c8a431232f91605291d23f2b18130b5de4` |

Frozen manifest:

- source cases: `5`;
- customer data: `false`;
- expected outputs sent to model: `false`;
- allowed literal values sent to model: `false`;
- deterministic schema transforms: `5`.

## Gemini 3.1 terminal receipt

Qualification subject:

- exact model:
  `models/gemini-3.1-flash-lite`;
- exact authorization SHA-256:
  `2da1d9e878a93512ec275b45051758394c70622227e8767bf57e286dc9e60770`;
- requested/resolved model exact: `true`;
- provider output generated: `true`;
- canonical validation ran: `true`;
- terminal status: `NOT_QUALIFIED`;
- terminal code: `expected_value_mismatch`;
- failure layer: unchanged frozen canonical comparator.

Quality:

- provider schema acceptance: `5/5`;
- canonical acceptance: `0/5`;
- exact literal value accuracy: `1.0`;
- source binding accuracy: `1.0`;
- invented values: `0`;
- duplicate bindings: `0`;
- truncations: `0`;
- fallback calls: `0`;
- repair attempts: `0`.

Usage:

- provider calls: `1`;
- input tokens: `655`;
- output tokens: `505`;
- total tokens: `1160`;
- actual cost: `USD 0.000921250`;
- duration: `4250 ms`;
- finish reason: `stop`;
- response ID present: `true`;
- safe response ID SHA-256:
  `3a79a37ac61ec40c18b3e8115f4700fd8cf4e61ac16fa4385a65d8d3d13296fd`;
- budget receipt integrity SHA-256:
  `19b14711e60e6b71325f727b381f34dd1a5ccf1a25af072ac6221d1fc5b254e3`;
- budget status: `within_budget`.

Все 5 cases завершились с единственным safe failure code
`expected_value_mismatch`.

## Gemini 3.5 terminal receipt

Qualification subject:

- exact model:
  `models/gemini-3.5-flash-lite`;
- exact authorization SHA-256:
  `28e4b69a108cfd51694afde41bc1a3486b4ac9d5bd997e3bf718d944f336468a`;
- requested/resolved model exact: `true`;
- provider output generated: `true`;
- canonical validation ran: `true`;
- terminal status: `NOT_QUALIFIED`;
- terminal code: `expected_value_mismatch`;
- failure layer: unchanged frozen canonical comparator.

Quality:

- provider schema acceptance: `5/5`;
- canonical acceptance: `0/5`;
- exact literal value accuracy: `1.0`;
- source binding accuracy: `1.0`;
- invented values: `0`;
- duplicate bindings: `0`;
- truncations: `0`;
- fallback calls: `0`;
- repair attempts: `0`.

Usage:

- provider calls: `1`;
- input tokens: `655`;
- output tokens: `417`;
- total tokens: `1072`;
- actual cost: `USD 0.001239000`;
- duration: `4032 ms`;
- finish reason: `stop`;
- response ID present: `true`;
- safe response ID SHA-256:
  `112cbfe64c9b77087f6ff780f2c42914eefd6816432fbe398a08e35c9aa112c6`;
- budget receipt integrity SHA-256:
  `e2553494c4e37dcd1938c9488f3cdbc5897b82eb9df60402a0e266ecc5208f4a`;
- budget status: `within_budget`.

Все 5 cases завершились с единственным safe failure code
`expected_value_mismatch`.

## Aggregate accounting

- provider calls: `2`;
- customer calls: `0`;
- input tokens: `1310`;
- output tokens: `922`;
- total tokens: `2232`;
- actual cost: `USD 0.002160250`;
- expensive model calls: `0`;
- fallback calls: `0`;
- repair attempts: `0`;
- paid tools: `0`;
- stage mutations: `0`;
- Knowledge/RAG/vector writes: `0`;
- Gate 3 executions: `0`.

## Contracts changed

`ZERO`.

Goal 2 создал только safe report/receipt. Runtime, stage и production policy
не менялись.

## Contracts explicitly unchanged

Без изменений оставлены:

- canonical parser/validator/comparator;
- frozen secretary manifest;
- production request profiles;
- source/domain/financial/checksum production routes;
- production admissions;
- economy model/workload/qualification policies;
- live qualification Action;
- Gate 1/source/domain Functions и valves;
- Pipes, Prompts, provider profiles и connections;
- Financial Evidence Registry и four-disposition contract;
- Gate 1 visual behavior;
- Knowledge/RAG/vectorization boundary;
- Gate 3.

## Failed qualification boundary

Exact terminal code для обеих моделей:
`expected_value_mismatch`.

Failure layer:
неизменённый canonical comparison после успешного provider transport,
strict-schema parsing и per-case comparison.

Safe receipt доказывает, что:

- provider generated an output: `true`;
- canonical validation ran: `true`;
- literal/source checks passed;
- один из остальных expected scalar fields не совпал в каждом case.

Safe receipt намеренно не сохраняет raw output и сейчас не называет
mismatched field path. Поэтому owner mismatch — prompt, allowed bounded
choice или model selection — не приписывается без доказательства.

Narrowest corrective slice перед любым будущим source requalification:
отдельно добавить value-free mismatch-path observability к safe comparator
report, не меняя acceptance behavior, frozen expected values или canonical
contract. После локализации допустима только отдельная prompt/fixture
diagnosis; новый provider call должен иметь отдельный receipt.

Явно запрещены:

- ослабление canonical validator/comparator;
- передача expected values модели;
- free JSON;
- repair или fallback;
- повторный call в рамках Goal 2;
- production admission любой из моделей;
- перенос source qualification на другой workload.

## Tests

Focused:

- `44 passed in 0.93s`.

Full service suite:

- `1383 passed`;
- `20 skipped`;
- `5` существующих SWIG deprecation warnings;
- `93.82s`.

## Privacy

- synthetic non-customer corpus only: `true`;
- customer corpus read: `false`;
- raw provider output in Git: `false`;
- response bodies in report/receipt: `false`;
- secrets in report/receipt: `false`;
- privacy status: `PASSED`.

## Terminal reporting

- status: `COMPLETED_WITH_EXPLICIT_GAPS`;
- exact execution revision:
  `943a496dcc33937404ee2d066cd71cf9b1b541ba`;
- branch:
  `codex/broker-reports-gate2-v4-goal2-gemini-source-qualification`;
- PR: `#115`;
- contracts changed: `ZERO`;
- contracts explicitly unchanged: listed above;
- model IDs:
  `models/gemini-3.1-flash-lite`,
  `models/gemini-3.5-flash-lite`;
- provider/customer calls: `2 / 0`;
- tokens/cost: `1310 input, 922 output / USD 0.002160250`;
- fallback/repair: `0 / 0`;
- focused/full tests:
  `44 passed / 1383 passed, 20 skipped`;
- privacy: `PASSED`;
- stage mutations: `0`;
- next permitted Goal after merge:
  `Goal 3 — Gemini domain qualification`.
