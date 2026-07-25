# Broker Reports — Gate 2 v4, Goal 5: Gemini financial secondary

Дата: 2026-07-25

Статус: `COMPLETED_WITH_EXPLICIT_GAPS`

## Результат

Gemini 3.5 выполнил полный four-disposition financial route:

- `GEMINI_3_5_FINANCIAL_ROUTE: EXECUTED`;
- `GEMINI_3_5_FINANCIAL: NOT_QUALIFIED`;
- passed: `3/4`;
- terminal failure:
  `financial_evidence_decision_unclassified_shape_invalid`;
- repair: `0`;
- fallback: `0`.

Gemini 3.1 получил ровно один narrow unclassified diagnostic call.
Исторический reject не воспроизведён:

- current root/decision shape: exact;
- missing decision keys: `0`;
- extra decision keys: `0`;
- current canonical parser: `passed`;
- `GEMINI_3_1_PREVIOUS_FAILURE: NOT_LOCALIZED`.

Ни одна Gemini-модель не активирована для financial workload. Primary
GPT-5.4 Nano остаётся независимо qualified `4/4`.

## Git

- accepted execution revision:
  `b296eed61e4f923b275fd9567d6ece04c8280040`;
- branch:
  `codex/broker-reports-gate2-v4-goal5-gemini-financial-secondary`;
- PR: будет закреплён после открытия evidence-only PR.

## Exact financial identity

Общие contracts:

| Contract | Revision |
|---|---|
| workload | `gate2_financial_evidence` |
| provider profile | `google_gemini` |
| input | `broker_reports_gate2_financial_evidence_source_package_v1` |
| output | `broker_reports_gate2_financial_evidence_decision_v1` |
| prompt | `gate2_financial_evidence_shadow_prompt_v1` |
| adapter | `gate2_gemini_schema_projection_v1` |
| canonical validator | `sha256:747d83552f394f4bd56249820e9630adc97a4d2435da60cbd9b2b376685eb5be` |

Authorization:

- Gemini 3.1 diagnostic:
  `5c723cf8b49cd6ea216f166361c1bc927e4cb921f009612ae194fb39b10cdc46`;
- Gemini 3.5:
  `ff256b7362da6dabe7b51b020bbba5cc572a46236e42ecb01d7bd157b66a5402`.

## Gemini 3.5 result

| Case | Expected | Result | Terminal |
|---|---|---|---|
| typed | `typed_input` | passed | canonical/materialization passed |
| unclassified | `unclassified_financial_input` | failed | `financial_evidence_decision_unclassified_shape_invalid` |
| no financial | `no_financial_input` | passed | canonical/materialization passed |
| unsupported | `unsupported` | passed | canonical/materialization passed |

Usage:

- provider calls: `4`;
- input tokens: `1848`;
- output tokens: `253`;
- total tokens: `2101`;
- actual cost: `USD 0.001186900`;
- total duration: `8328 ms`;
- requested/resolved exact model: `4/4`;
- finish reason `stop`: `4/4`;
- strict JSON schema: `4/4`;
- fallback: `0`;
- repair: `0`;
- private safe receipt SHA-256:
  `b47c52e2a9b3c0762d3300ee7c00d70f423fea50b7e14f7ef9c3f832f53a931a`.

Failed qualification boundary:

- exact model: `models/gemini-3.5-flash-lite`;
- exact workload: `gate2_financial_evidence`;
- provider generated output: `true`;
- canonical validation ran: `true`;
- terminal code:
  `financial_evidence_decision_unclassified_shape_invalid`;
- failure layer: unchanged canonical branch-shape validation after successful
  provider transport.

## Gemini 3.1 narrow diagnosis

Current one-call result:

- provider generated output: `true`;
- disposition: `unclassified_financial_input`;
- root keys: exact `decision`;
- decision keys: exact
  `disposition`, `reason_code`, `value_bindings`;
- value bindings: array of exact
  `role_id`, `source_value_ref` objects;
- missing keys: `0`;
- extra keys: `0`;
- canonical validation: `passed`;
- fallback: `0`;
- repair: `0`;
- input/output tokens: `361 / 86`;
- actual cost: `USD 0.000219250`;
- private safe receipt SHA-256:
  `fc988076a2367fed5e20a3ca9c6efea9bd087026aa40fc17d9657ab2b3023e56`.

Исторический raw/shape receipt не сохранялся. Поэтому old failure owner —
prompt, provider dialect или stochastic model output — не назначается без
доказательства.

## Projection finding

Для unclassified schema:

- canonical schema:
  `3b4a6204d15acee98c444eb5a196ee023e78e53d0dee1b223f39e7b5d9f11a42`;
- adapted schema:
  `c34971081249a19f0ea0098aa2c2d0d950ec07a63e36a1f59dc391998b419ea1`;
- transforms: `8`;
- canonical branch disposition enum present: `true`;
- adapted branch disposition enum present: `false`;
- required/property branch shapes otherwise retained.

Это independently proven adapter risk, но текущий Gemini 3.1 output прошёл
и exact Gemini 3.5 response shape не был сохранён стандартным runner.
Причинность historical reject поэтому не заявляется.

Adapter correction не выполнялась:

- GPT-5.4 Nano primary уже qualified `4/4`;
- Gemini 3.5 secondary failure не блокирует Gate 2;
- новый projection revision потребовал бы отдельный PR и новые receipts;
- программа не продолжает поиск идеальной secondary-модели.

## Aggregate accounting

- provider calls: `5`;
- customer calls: `0`;
- input tokens: `2209`;
- output tokens: `339`;
- total tokens: `2548`;
- actual cost: `USD 0.001406150`;
- expensive model calls: `0`;
- fallback calls: `0`;
- repair attempts: `0`;
- paid tools: `0`;
- stage mutations: `0`;
- Knowledge/RAG/vector writes: `0`;
- Gate 3 executions: `0`.

## Contracts changed

`ZERO`.

Goal 5 добавляет только safe report/receipt. Adapter, prompt, schema,
canonical validator, runtime и stage не менялись.

## Contracts explicitly unchanged

- Financial Evidence Registry;
- four-disposition decision contract;
- deterministic materializer;
- financial context and checksum contracts;
- Gemini adapter/provider route;
- production workload routing/admissions;
- Gate 1 visual behavior;
- stage Functions/Pipes/Prompts;
- Knowledge/RAG/vectorization;
- Gate 3.

## Tests

- focused: `65 passed in 1.61s`;
- full: `1400 passed, 20 skipped, 5 existing warnings in 102.08s`;
- preflight provider calls: `0`;
- live stderr bytes: `0`.

## Privacy

`PASSED`.

- synthetic non-customer fixtures only;
- customer corpus read: `false`;
- raw provider output in Git: `false`;
- diagnostic receipt contains keys/types only;
- full safe receipts remain under ignored `local/`;
- secrets in Git: `false`.

## Next permitted goal

Goal 6 — checksum closure:

- Haiku 4.5 formal current requalification;
- Nano prior dimension mismatch diagnosis;
- no comparator weakening.
