# Broker Reports — Gate 2 Goal 5: context projection

Дата: 2026-07-24

Статус: `COMPLETED`

## Итог

Добавлена минимальная model-facing projection:
`broker_reports_gate2_financial_context_v1`.

Это не accounting register, не answer UX и не Gate 3 implementation.
Projection строится только deterministic factory после валидации Goal 4
financial evidence artifacts и соответствующих integrity-sealed source
packages.

## Interpretation boundary

Каждый source scope получает ровно один `interpretation` representation:

- typed financial input;
- unclassified financial input;
- no-financial terminal closure;
- unsupported terminal closure.

Все source-level representations остаются отдельными
`provenance_only` identities. Они содержат только:

- representation ID;
- source ref;
- source-value refs;
- evidence refs;
- lineage.

Provenance-only representations не содержат literal values и не могут
конкурировать с interpretation entry.

Exact duplicate artifact code-level дедуплицируется до одного entry.
Два разных validated artifacts для одного source scope вызывают fail-closed
`financial_context_duplicate_interpretation_scope`. LLM не участвует в
deduplication.

## Model-facing fields

Interpretation representation содержит только:

- typed/unclassified/no-financial/unsupported status;
- Registry input type, title и semantic class для typed input;
- literal source labels;
- bound values, roles, value types и source sign;
- date/period;
- currency/unit;
- source document/page/scope refs;
- completeness, restrictions и issue refs;
- financial artifact, terminal object, source package, source-value и
  evidence identities;
- bounded terminal reason code.

Unbound source-package values не попадают в interpretation values и остаются
доступны только как provenance identities.

## Explicit aggregate semantics

- `printed_financial_metric_v1` получает
  `aggregate_semantics: source_printed`;
- `cash_balance_snapshot_v1` получает `not_aggregate`;
- unclassified content получает `unclassified`;
- no-financial/unsupported closure получает `not_applicable`;
- `calculated_aggregates_total` всегда `0`.

Calculated accounting/tax aggregates в текущей программе не создаются.

## Forbidden context content

Exact-shape validator и recursive forbidden-field check не допускают:

- raw PDF/PDF bytes;
- Gate 1 full text или raw representations;
- crop images;
- provider raw responses;
- internal audit noise;
- tax methodology;
- declaration mapping;
- answer instructions;
- calculated aggregate objects.

Projection не импортирует ArtifactStore, provider clients, customer state или
Gate 3 context.

## Deterministic synthetic proof

Синтетический five-scope fixture содержит:

- source scopes: `5`;
- interpretation representations: `5`;
- provenance-only representations: `35`;
- typed inputs: `2`;
- unclassified financial inputs: `1`;
- no-financial closures: `1`;
- unsupported closures: `1`;
- duplicate interpretation representations: `0`;
- calculated aggregates: `0`;
- Registry SHA-256:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- context integrity SHA-256:
  `bdd56d97c2af0c70c03f2d1f0d91c65b1c5aeccf7de4f655f0b596c59f35a557`.

Proof использует только synthetic labels/refs и не содержит customer values.

## Scope boundary

Goal 5 не подключает projection к production runtime и не меняет stage.
Legacy compatibility/replay остаётся отдельным Goal 6.

## Validation

- context projection tests: `16 passed`;
- context + materialization + decision + Registry + catalog tests:
  `80 passed`;
- full Broker Reports suite: `1227 passed`, `20 skipped`;
- context modules/tests ruff: `passed`;
- repository privacy guard: `3 passed`;
- private labels, values, filenames и provider output в Git: `ZERO`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL5_CONTEXT_PROJECTION.receipt.safe.json).

## Acceptance

`GATE2_CONTEXT: STRUCTURED_AND_SOURCE_BOUND`

`GATE1_RAW_REPRESENTATIONS_IN_CONTEXT: ZERO`

`DUPLICATE_INTERPRETATION_REPRESENTATIONS: ZERO`

`PRINTED_VS_CALCULATED: EXPLICIT`

`TAX_METHODOLOGY: ZERO`

`GOAL_5_CONTEXT_PROJECTION: COMPLETED`
