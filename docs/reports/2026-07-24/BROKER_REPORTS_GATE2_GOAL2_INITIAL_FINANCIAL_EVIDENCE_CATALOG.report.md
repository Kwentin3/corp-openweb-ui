# Broker Reports — Gate 2 Goal 2: initial financial evidence catalog

Дата: 2026-07-24

Статус: `COMPLETED_WITH_GAPS`

## Итог

Initial Registry ограничен двумя source-local financial input types:

1. `cash_balance_snapshot_v1`;
2. `printed_financial_metric_v1`.

Registry snapshot:

- catalog version:
  `broker_reports_gate2_initial_financial_catalog_v1`;
- registry version:
  `broker_reports_gate2_financial_evidence_registry_v1`;
- canonical SHA-256:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`;
- active types: `2`;
- experimental types: `0`;
- aliases: `0`.

## Основание каталога

Safe corpus research подтвердил:

- 6 документов;
- 9 bounded table crops;
- 3 evidence units для cash balance;
- 3 evidence units для printed metric;
- research receipt SHA-256:
  `f8862b9a2104a8b4f08b24b6ebe06fc784ce78bb27524e2dd67e8cce92eff1f5`.

Оба active type имеют:

- source-oriented definition;
- required/optional/forbidden roles;
- role value types и source-ref policy;
- date/period, currency/unit и sign policy;
- source-level identity material;
- synthetic positive examples и counterexamples;
- safe corpus evidence refs;
- deterministic test refs;
- pinned semantic fingerprints.

## Почему только два типа

Фактический корпус — в основном broker/dealer financial statements и
schedules, а не репрезентативный transaction feed. Поэтому широкие legacy
IDs не повышены до canonical types:

- `trade_operation`;
- `income`;
- `withholding_tax`;
- `fee_commission`;
- `cash_movement`;
- `currency_fx`;
- `position_snapshot`.

Не активированы и не объявлены experimental следующие research candidates:

- regulated/segregated asset balance;
- receivable balance;
- payable/liability balance;
- equity balance;
- security inventory balance;
- lease right-of-use asset;
- lease liability;
- credit-loss allowance snapshot;
- credit-loss allowance movement;
- lease payment schedule item.

Для них пока не закрыты definition, sign, class, scope, netting или movement
semantics. Объявлять их типами только потому, что source label похож, нельзя.

## Namespace separation

- `document_summary_evidence` остаётся evidence kind;
- `unknown_source_row` остаётся legacy technical disposition;
- router domains/extractor IDs не являются financial input type IDs;
- source labels не становятся canonical IDs;
- `broker_reports_fns_2ndfl_source_facts_v1` остаётся отдельной deterministic
  FNS schema family без silent mapping.

Совместимые Gate 1 source families:

- `broker_reports_normalized_table_projection_v0`;
- `semantic_visual_logical_table_v1`.

## Явные gaps

Пока остаются unclassified:

- десять перечисленных statement/schedule concept families;
- transaction-oriented broker rows, если их нельзя однозначно отнести к двум
  active types;
- специализированные FNS source facts вне принятого mapping.

Source values на этом этапе сохраняются в существующих Gate 1 source units,
normalized table projections, semantic visual logical tables и legacy
artifacts. Новый `unclassified_financial_input` terminal artifact будет
создан только после Goals 3–4; поэтому текущий catalog сам по себе ещё не
разрешает использовать новый контекст в Gate 3.

До materialization и qualification запрещено:

- приписывать deferred values active type;
- netting или aggregation между statement classes/scopes;
- считать printed metric вычисленным итогом;
- делать tax, declaration, cost-basis или P/L вывод;
- заявлять full-scope Gate 2 closure.

## Validation

- catalog + registry + FNS tests: `30 passed`;
- full Broker Reports suite: `1169 passed`, `20 skipped`;
- new module/test ruff: `passed`;
- repository privacy guard: `passed`;
- private labels, values, filenames и provider output в Git: `ZERO`.

Repository-safe evidence:
[receipt](./BROKER_REPORTS_GATE2_GOAL2_INITIAL_FINANCIAL_EVIDENCE_CATALOG.receipt.safe.json).

## Acceptance

`INITIAL_CATALOG: BOUNDED`

`EVERY_ACTIVE_TYPE: HAS_CORPUS_EVIDENCE`

`SOURCE_LABEL_AS_TYPE_ID: ZERO`

`ROUTER_OR_STATUS_AS_FINANCIAL_TYPE: ZERO`

`UNPROVEN_TYPES: DEFERRED`

`FNS_SPECIALIZED_PATH: PRESERVED`

`GOAL_2_INITIAL_CATALOG: COMPLETED_WITH_GAPS`
