# Broker Reports — Gate 2 deterministic scope refactoring, Goal 4

Дата: 2026-07-25  
Статус: `GOAL_4_SUCCESSOR_ARTIFACT_COMPATIBILITY: PASSED`

## Результат

Добавлено отдельное explicit successor artifact family:

- `broker_reports_gate2_successor_package_artifact_v1`;
- `broker_reports_gate2_successor_run_artifact_v1`;
- `broker_reports_gate2_successor_execution_receipt_v1`;
- `broker_reports_gate2_successor_compatibility_projection_v1`.

Единственная точка построения family:
`Gate2SuccessorArtifactFamilyFactory.create`.

Family связывает только хеши и identity уже проверенных deterministic scope,
source package, существующего Financial Evidence decision/materialization,
financial context и provider execution metadata. Persisted payload и
production route не меняются.

## Compatibility boundary

Добавлен отдельный
`Gate2SuccessorCompatibilityReaderFactory.create`.
Reader выполняет explicit dispatch по `schema_version`:

- legacy `broker_reports_source_facts_v0` передаётся неизменённому pinned
  legacy reader;
- `broker_reports_financial_evidence_inputs_v1` передаётся существующему
  Financial Evidence reader;
- специализированный `broker_reports_fns_2ndfl_source_facts_v1`
  сохраняется отдельным FNS path;
- четыре новые successor schemas проверяются собственными validators.

Unknown schema отклоняется. Payload SHA-256 проверяется до и после read.
Silent conversion/upcast и rewrite отсутствуют.

Legacy schema constants, validators и readers не изменялись.

## Compatibility projection

Projection имеет собственные `schema_version`, `projection_ref` и
`integrity_hash`. Она содержит только однозначно вычислимые поля:

- terminal disposition;
- canonical financial input type IDs;
- source-value refs;
- bounded reason code.

Projection явно не создаёт:

- subtype;
- model confidence;
- legacy model output;
- legacy schema identity.

## Write and rollback policy

- legacy payloads immutable: `true`;
- legacy rewrite allowed: `false`;
- silent upcast allowed: `false`;
- successor single-write:
  `blocked_pending_production_admission`;
- production write admitted: `false`;
- rollback boundary: `future_routing_only`;
- FNS specialized path: `separate_unchanged`.

Прямая попытка successor write до admission завершается
`successor_single_write_not_admitted`.

## Closed-world and factory proof

Оба новых модуля включены в deterministic domain bundle после scope/runner
dependencies. Bundle повторно собирается с тем же SHA-256:
`485c80dbf3383cdb5add152e06be26b0516ab6c7fc4ceba3b67972748fe7ca32`.

Static boundary test подтверждает отсутствие imports artifact store,
source/domain production runtime и Financial Evidence production runtime.
Customer-facing routing и persistence path не активированы.

## Tests

- direct Goal 4: `9 passed`;
- focused successor/scope/legacy compatibility/bundle:
  `53 passed`;
- final Goal 4 + bundle smoke: `20 passed`;
- full Broker Reports suite:
  `1436 passed, 20 skipped, 5 warnings in 94.15s`;
- Ruff по изменённым source/test/builder files:
  `All checks passed`;
- `git diff --check`: passed;
- bundle rebuild exact: true.

## Repository and Git boundary

- base revision:
  `bfbc19124fd7ca76fa2e1067e38e03546f936a72`;
- branch:
  `codex/broker-reports-gate2-scope-refactor-goal4-successor-compatibility`;
- implementation revision:
  `1313c98c4314016fa8bcfb69c052667713cbc77c`;
- PR: `https://github.com/Kwentin3/corp-openweb-ui/pull/130`.

Source SHA-256:

- artifact family:
  `fec03cfb201c8ad89865be2ab6cf29d7cb6331a414361e29aae3d029383d5ce3`;
- compatibility reader:
  `ce2e61d619003225a3a7869d0d26b0d29b9faded65464e737a01d3c86109d93e`;
- tests:
  `43551c235e854c984c857bd1e9a79baedb77eaf1354aad1370ab0a2fbdb5cfee`.

## Privacy and external effects

- provider calls: 0;
- customer corpus reads/calls: 0;
- persistence writes: 0;
- production route activations: 0;
- stage/browser calls or mutations: 0;
- raw model output in Git: 0;
- customer/private values, refs or paths in Git evidence: 0.

## Acceptance

- `SUCCESSOR_SCHEMA: EXPLICIT`
- `LEGACY_READ: PRESERVED`
- `LEGACY_REWRITE: ZERO`
- `SILENT_CONVERSION: ZERO`
- `ROLLBACK_BOUNDARY: FUTURE_ROUTING_ONLY`

## Next permitted Goal

Только после merge этого PR разрешён Goal 5: local successor proof на frozen
synthetic fixtures без provider calls. Goal 4 не является production
admission, actual-corpus proof или live persistence.
