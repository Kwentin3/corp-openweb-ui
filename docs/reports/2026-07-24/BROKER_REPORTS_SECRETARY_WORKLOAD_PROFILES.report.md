# Broker Reports — Secretary workload profiles

Дата: 2026-07-24.

Статус: `COMPLETED`.

## Product boundary

Gate 2 model — не финансовый аналитик. Код владеет IDs, Registry,
provenance, candidate sets, validation, materialization и context projection.
Модель выполняет bounded clerical selection. Поэтому qualification разделена
на четыре workload, а не на общий “model intelligence” test.

## Профили

| Workload | Bounded task | Reasoning | Context/output | Schema complexity | Error tolerance | Provider strictness | Tool alternative | Target cost | Latency |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |
| `gate2_source` | скопировать полезные visible values, выбрать bounded fact/no-fact | none/minimal | measured `5,058 / 700`; hard `12k / 4,096` | medium, arrays+enums+source refs | invented/wrong literal = 0 | strict preferred; canonical mandatory | strict function acceptable | ≤0.004/package | high priority |
| `gate2_domain` | выбрать bounded domain hypothesis/candidates/roles, не делать финансовый вывод | minimal | expected not measured; planning `6k / 800`; hard `12k / 4,096` | high: dynamic enums, arrays, bindings, ambiguity | wrong ref/role/duplicate = 0 | strict required unless tool is equivalently strict | strict function is acceptable | ≤0.004/package provisional | high priority |
| `gate2_financial_evidence` | выбрать disposition, Registry type и bindings | none/minimal | average `1,219 / 182`; observed max output 506; hard `3,072 / 640` | high conditional branch shape | disposition/type/ref error = 0 | strict strongly required | strict function preferred if response schema projection fails | ≤0.001/scope | highest throughput |
| `gate2_financial_checksum` | найти три prepared context metrics и вернуть exact values/bindings | none | measured `117,555 / 783`; hard `130k / 1,024` | medium output, very long input | any mismatch/invention = 0 | strict required | strict function acceptable | ≤0.040/call | throughput secondary |

## `gate2_source`

Contract anchor: `broker_reports_source_fact_selection_v3`.

Required:

- literal copy without sign, separator, currency or date changes;
- only allowed source refs and fact types;
- explicit `unknown_source_row`/no-fact result;
- no financial interpretation, arithmetic or label-to-canonical promotion.

Best model shape: inexpensive non/frontier classifier with reliable strict
JSON. Large reasoning budget decreases cost predictability and is not a
quality requirement.

## `gate2_domain`

Contract anchor: `broker_reports_candidate_binding_output_v0`.

Required:

- choose only dynamically enumerated candidate IDs, relation IDs and roles;
- keep equal visible values bound to the selected source cell;
- surface ambiguity instead of guessing;
- never create a type, role, ref or relation.

This workload stresses schema complexity and binding more than reasoning.
Provider projection is a material part of qualification.

## `gate2_financial_evidence`

Contract anchor:
`broker_reports_gate2_financial_evidence_decision_v1`.

Only four dispositions are legal:

- `typed_input`;
- `unclassified_financial_input`;
- `no_financial_input`;
- `unsupported`.

`typed_input` may select only a Registry-owned type and allowed role
bindings. An exact type that is not proved must remain unclassified.
Header/promo/layout text must not be promoted into financial evidence.

The workload should first be tested with a minimal branch-specific secretary
fixture. Failure to express the conditional schema at provider boundary is
not model-quality failure.

## `gate2_financial_checksum`

Contract anchors:

- `broker_reports_gate2_financial_context_v1`;
- `broker_reports_gate2_financial_context_checksum_v1`;
- prompt `broker_reports_gate2_financial_context_checksum_prompt_v1`.

The input is long but already prepared. The model does not inspect PDF,
tax methodology or Gate 1 private graph. It locates bounded metrics,
preserves values and source binding, and emits one compact object.

Primary risk is context discipline/truncation, not complex reasoning.
128k models have insufficient safety margin around measured `117,555`
tokens plus prompt/schema; 200k+ is preferred.

## Synthetic secretary benchmark

Добавлен frozen non-customer benchmark:

- manifest:
  `services/broker-reports-gate1-proof/benchmarks/gate2_secretary_v1/manifest.json`;
- comparator/safe formatter:
  `broker_reports_gate1/gate2_secretary_benchmark.py`;
- tests:
  `tests/test_broker_reports_gate2_secretary_benchmark.py`.

`17` fixtures покрывают literal copy, bounded classification, source
binding, ambiguity, structured root и adversarial clerical cases. Есть
signed decimal, currency/date, repeated header, equal values with distinct
refs, subtotal/detail, adjacent currencies, missing nullable date, repeated
label, unresolved type, prompt-like cell text, все четыре dispositions и
checksum zeros.

Comparator terminally различает:

- provider schema rejection;
- refusal;
- truncation;
- invalid JSON/schema shape;
- literal mismatch;
- bounded classification error;
- source binding error;
- duplicate binding;
- invented value;
- expected-value mismatch.

Safe format содержит только exact qualification subject, case IDs,
failure codes и агрегированные metrics:

- provider schema/canonical acceptance rates;
- exact value/source binding/correct disposition rates;
- invented/duplicate/truncation counts;
- latency;
- input/output tokens;
- estimated cost.

Raw provider output, expected fixture body и customer data в safe report не
включаются. Comparator не вызывает provider и не заменяет production
canonical validators.

## Admission thresholds

Для перехода с synthetic к bounded non-customer live:

- provider schema acceptance: `100%`;
- parseable output: `100%`;
- canonical acceptance: `100%`;
- exact value accuracy: `100%`;
- source binding accuracy: `100%`;
- correct disposition: `100%`;
- invented values: `0`;
- duplicate bindings: `0`;
- truncations/refusals: `0`;
- hidden repair/retry/fallback: `0`.

Строгость намеренная: ошибки в bounded clerical work должны устраняться
до actual-corpus shadow, а не усредняться benchmark score.

## Explicit gaps

- domain actual token profile: `NOT_MEASURED`;
- workload latency SLO в миллисекундах: `NOT_YET_BASELINED`;
- model-specific benchmark runs: `NOT_RUN`;
- actual customer corpus: запрещён на первом этапе;
- production readiness: `NONE`.
