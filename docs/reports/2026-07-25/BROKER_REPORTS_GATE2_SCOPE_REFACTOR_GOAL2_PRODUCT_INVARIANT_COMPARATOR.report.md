# Broker Reports — Gate 2 deterministic scope refactoring, Goal 2

Дата: 2026-07-25  
Статус: `GOAL_2_PRODUCT_INVARIANT_SUCCESSOR_COMPARATOR: PASSED`

## Результат

Реализован `Gate2SuccessorProductComparatorFactory`. Comparator принимает:

- принятые deterministic Financial Evidence scopes Goal 1;
- наблюдённые model decisions;
- materialized artifacts;
- финальный Gate 2 financial context.

Он не сравнивает legacy candidate/relation graph. Вместо этого comparator
канонически валидирует model decision, повторно выполняет существующий
deterministic materializer, повторно строит existing financial context и
проверяет продуктовые инварианты.

Новая safe receipt schema:
`broker_reports_gate2_successor_product_comparator_v1`.

## Authoritative product invariants

Comparator проверяет:

1. disposition входит в четыре canonical disposition;
2. typed `input_type_id` входит в eligible Registry projection scope;
3. каждый binding ref принадлежит exact package;
4. роль совместима с allowed roles source value;
5. materialized literal совпадает с authoritative source literal;
6. invented refs/values отсутствуют;
7. duplicate bindings отсутствуют;
8. binding имеет ровно одного scope owner;
9. каждый authorized scope имеет ровно один terminal observation;
10. unclassified decision сохраняет все package candidates;
11. повторная deterministic materialization exact совпадает;
12. повторный final context exact совпадает и сохраняет integrity.

Optional product expectation поддерживает явно заданные допустимые
альтернативы. `acceptable_alternative` записывается как value-free mismatch,
но не блокирует pass.

## Exact equality boundary

Exact equality применяется только к:

- deterministic materialized Financial Evidence artifacts;
- deterministic final financial context.

Exact equality не применяется к:

- legacy candidate/relation graph;
- legacy fact paths;
- model confidence/completeness/uncertainty;
- audit/system metadata.

Ни один legacy benchmark, fixture или validator не изменён.

## Value-free diagnostics

Каждый mismatch содержит только:

- JSON-like ordinal path без source refs и literals;
- failure layer;
- bounded reason code;
- classification;
- affected source refs count;
- literal loss count;
- terminal ownership gap count;
- blocking flag.

Классификации:

- `model_wrong`;
- `acceptable_alternative`;
- `comparator_defect`;
- `contract_gap`;
- `actual_data_loss`;
- `unknown`.

Receipt validator fail-closed сканирует сериализованный receipt против
private package refs, scope refs, document refs, source-value refs и literal
values. Receipt также имеет deterministic integrity hash.

## Deterministic probes

Положительный unclassified probe:

- status: `passed`;
- 14/14 checks: true;
- mismatch paths: 0;
- affected refs: 0;
- literal loss: 0;
- ownership gaps: 0;
- invented values: 0;
- duplicate/cross-scope bindings: 0;
- receipt integrity:
  `1dfef8b1b8a05092517904cfd4d6fbde50cf3b9154e18275957ab410cbc4b403`.

Намеренный unclassified value-loss probe:

- status: `failed`;
- unique affected refs: 1;
- literal loss: 1;
- ownership gaps: 0;
- classification: `actual_data_loss`;
- value-free mismatch paths:
  `$.scopes[0].decision.value_bindings`,
  `$.scopes[0].materialized_artifact`,
  `$.final_context`.

Дополнительно доказаны:

- typed Registry-bound pass;
- accepted alternative non-blocking;
- tampered literal rejection;
- missing terminal ownership;
- out-of-package ref rejection;
- duplicate model binding accounting;
- wrong final context rejection.

## Tests

- direct Goal 2 tests:
  `10 passed in 0.63s`;
- focused scope/decision/materialization/context/shadow set:
  `87 passed in 1.14s`;
- full Broker Reports suite:
  `1417 passed, 20 skipped, 5 warnings in 93.25s`;
- Ruff:
  `All checks passed`;
- `git diff --check`:
  passed.

Core comparator/materializer/context не подменяются mock-объектами.

## Repository and Git boundary

- base revision:
  `8683f250350d1aa57a3a4867397ea1b18fe4867b`;
- branch:
  `codex/broker-reports-gate2-scope-refactor-goal2-comparator`;
- implementation revision:
  `43a315ff7c1d34f96b2811ab868deb4a129ef288`;
- PR: `PENDING`;
- production runtime files changed: 0;
- OpenWebUI bundle files changed: 0;
- legacy benchmark files changed: 0;
- stage mutations: 0.

Comparator source SHA-256:
`ea3a10a253e36e747c1ef8d11513acf4c785ecc3c5496bb72244eb3994599e6e`.

Test source SHA-256:
`f3637f851eb2143325226bf8e4fd954ce42a09ab8e66cdbb47d4d721e12598e9`.

## Privacy and external effects

- provider/model calls: 0;
- customer corpus reads/calls: 0;
- persistence writes: 0;
- browser/stage calls: 0;
- stage mutations: 0;
- raw provider output in Git: 0;
- private values/refs/paths in safe receipt: 0.

## Acceptance

- `PRODUCT_INVARIANTS: AUTHORITATIVE`
- `INTERNAL_GRAPH_EXACTNESS: NOT_PRIMARY`
- `VALUE_FREE_MISMATCH_PATHS: REQUIRED`
- `ACTUAL_DATA_LOSS: EXPLICITLY_MEASURED`
- `LEGACY_BENCHMARK_REWRITE: ZERO`

## Next permitted Goal

Только после merge этого отдельного PR разрешён Goal 3: подключение
deterministic scopes к существующему Financial Evidence decision contract.
Goal 2 не меняет production route.
