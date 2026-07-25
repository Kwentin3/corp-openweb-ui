# Broker Reports — Gate 2 deterministic scope refactoring, Goal 1

Дата: 2026-07-25  
Статус: `GOAL_1_DETERMINISTIC_FINANCIAL_SCOPE_AUTHORITY: PASSED`

## Результат

Реализована чистая фабрика
`Gate2DeterministicFinancialScopeFromGate1Factory`. Она принимает готовые
authoritative Gate 1 source packages и без provider/model вызовов:

1. применяет существующий deterministic source-unit router;
2. полностью сегментирует вход существующим segmenter;
3. применяет router к derived units;
4. строит bounded domain projections существующим deterministic builder;
5. собирает connected Financial Evidence scopes;
6. запечатывает authoritative source package, Registry eligibility,
   terminal coverage boundary и integrity hash.

Новая explicit schema:
`broker_reports_gate2_deterministic_financial_scope_package_v1`.

Production runtime, OpenWebUI bundles и stage в Goal 1 не менялись.

## Authority boundary

Код владеет:

- stable package/scope identities;
- exact Gate 1 source-value refs и literal values;
- document/table/row/cell/text lineage;
- source-family resolution evidence;
- Registry snapshot и eligible type projection;
- allowed roles;
- deterministic no-fact closure;
- terminal coverage boundary;
- source-package и scope integrity.

Factory не импортирует и не принимает:

- structured model client;
- provider adapter;
- artifact store;
- materializer;
- production financial runtime.

Semantic decision, materialization, persistence и production routing этой
целью не выполняются.

## Coverage semantics

Модельный scope содержит только refs, для которых deterministic router
обозначил bounded decision workload. `deterministic_no_fact` refs не
теряются: они имеют отдельного terminal owner в batch coverage и не вызывают
Financial Evidence модель.

Factory fail-closed проверяет:

- duplicate package/unit/source identities;
- повторного terminal owner;
- cross-scope binding;
- cross-document или cross-normalization scope;
- конфликт authoritative literals/candidates/source family;
- отсутствующий literal, source ref или lineage locator;
- неполную segmentation/routing/decision coverage;
- scope limit;
- source-package, Registry, decision-contract и outer-package integrity.

## Versioned contract

| Contract | Version |
|---|---|
| scope package | `broker_reports_gate2_deterministic_financial_scope_package_v1` |
| batch safe summary | `broker_reports_gate2_deterministic_financial_scope_batch_v1` |
| scope policy | `gate2_deterministic_financial_scope_from_gate1_v1` |
| reused decision output | `broker_reports_gate2_financial_evidence_decision_v1` |
| reused source package | `broker_reports_financial_evidence_source_package_v1` |
| Registry | `broker_reports_gate2_financial_evidence_registry_v1` |

Существующие schema versions не переписывались.

## Deterministic synthetic proof

Безопасный synthetic probe:

- Gate 1 packages: 1;
- segmentation plans: 1;
- Financial Evidence scopes: 1;
- selected refs: 2;
- decision-scope refs: 1;
- deterministic no-fact refs: 1;
- unaccounted refs: 0;
- duplicate terminal owners: 0;
- provider/model calls: 0;
- persistence writes: 0;
- stable scope integrity:
  `caa06f0c178ca3f389dfd1ca1738c5275f80ea18fa6ab55811e46b16f8390297`.

Повтор с обратным порядком двух входных packages даёт exact одинаковые
scope packages и safe summary.

## Tests

- direct Goal 1 tests:
  `7 passed in 0.61s`;
- focused successor + reused segmentation/domain + legacy financial runtime:
  `29 passed in 0.89s`;
- full Broker Reports suite:
  `1407 passed, 20 skipped, 5 warnings in 96.21s`;
- Ruff:
  `All checks passed`;
- `git diff --check`:
  passed.

Тесты проверяют observable packages, literals, refs, lineage, Registry,
terminal coverage и integrity. Core factory не подменяется mock-объектом.
Негативные cases действительно завершаются fail-closed.

## Repository and Git boundary

- base revision:
  `175cb9e3abbcebfc0c33b4a50416714e5fb471e2`;
- branch:
  `codex/broker-reports-gate2-scope-refactor-goal1-deterministic-scope`;
- implementation revision:
  `00d7b074af4d7b30ab193225991226d529dfd01b`;
- PR: `https://github.com/Kwentin3/corp-openweb-ui/pull/127`;
- changed production/runtime files: 0;
- changed bundle files: 0;
- stage mutations: 0.

Implementation source SHA-256:
`0538023ecc80c715638a7cc5ebf8db425dc9bd24b833b1e3ac42eb5988ea46dc`.

Test source SHA-256:
`d1361d67ef27961b900b00c5cac7a648f3f78a40b96e1a9b65d2d55b7d1f9fcd`.

## Privacy and external effects

- customer corpus reads/calls: 0;
- provider calls: 0;
- browser/stage calls: 0;
- stage mutations: 0;
- raw provider output in Git: 0;
- customer values, filenames, paths or payloads in Git evidence: 0;
- safe summary содержит только агрегаты, booleans и hashes.

Private scope schema намеренно содержит literals и lineage, но никакой
runtime persistence этой целью не выполнялся и private package не добавлялся
в Git.

## Acceptance

- `SCOPE_FACTORY: PURE_AND_DETERMINISTIC`
- `SOURCE_VALUE_IDENTITY: EXACT`
- `PROVENANCE_IDENTITY: EXACT`
- `SELECTED_REF_COVERAGE: COMPLETE`
- `MODEL_CALLS: ZERO`
- `PRODUCTION_ROUTING_CHANGE: ZERO`

## Next permitted Goal

Только после merge этого отдельного PR разрешён Goal 2:
product-invariant successor comparator. Goal 1 не является production
admission или release.
